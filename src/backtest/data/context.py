"""Spec #005 v1.0 SS3/SS5/SS6/SS7 -- the stage read context (Batch 2
patch, round 4).

Batch 2 patch round-2 review, findings #1 and #3: a snapshot built from
successive unprotected reads can mix pre- and post-write state across
two connections; a cache call taking a bare `(conn, snapshot_id)` pair
has nothing tying that string to `conn`'s actual live state. `StageReadContext`
closes both by being the ONE object that derives and verifies the
`StageAccessBoundary` from a validated `ResearchPlan` (finding #4), and
is the only way to reach `_ObservationCacheStore.get_or_compute()`.

Batch 2 patch round-4 review -- the single flow GPT's review recommended
("plan and config validated -> strictly authorized extraction -> subset
read-only -> fingerprint and computations on that SAME subset"), replacing
round-3's two-connection design (raw source for the snapshot, a separate
subset only for Discovery) with one:

1. `__enter__()` opens ONE SAVEPOINT on the SOURCE connection just long
   enough to extract an authorized subset (see `backtest.data.pit_access.
   build_authorized_subset_connection()`) -- an EMPTY schema populated
   with only rows that were already in scope, never a full copy followed
   by deletion (round-3's P1 finding #1). The SOURCE's own `query_only`
   pragma is saved, forced ON for the extraction, and restored to
   whatever it was before -- never unconditionally forced OFF (round-3's
   P1 finding #2's second half).
2. The SOURCE's SAVEPOINT is released immediately once extraction
   completes -- nothing downstream ever reads the source connection
   again, so there is no reason to hold it, or its transaction, open any
   longer than the extraction itself takes.
3. The SUBSET connection's OWN `query_only` is set ON right after it is
   populated, BEFORE it is used for anything -- round-3 only protected
   the source, while the connection actually handed to Discovery
   (`_subset_conn`) was left writable (P1 finding #2's first half).
4. `self.conn` becomes the SUBSET connection itself (never the source)
   once the context is open -- `build_data_snapshot()` and every
   `get_or_compute_observations()` call read through this SAME,
   read-only, physically isolated copy, so nothing reached through this
   context can ever observe two different database states, or a write
   the source connection made after extraction.

Finding #3 (calendar covers the zone but not necessarily the run's own
warm-up): `__init__()` now requires an explicit `warmup_start` and
verifies the calendar covers `[warmup_start, max_as_of]`, not just
`[zone_start, max_as_of]` -- see `backtest.data.snapshot.build_data_snapshot()`'s
own `min_as_of` parameter, which this threads through.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from discovery.config.loader import DiscoveryConfig

from backtest.data.cache import _ObservationCacheStore
from backtest.data.calendar import require_calendar_covers_window
from backtest.data.pit_access import BoundedPITAccess, build_authorized_subset_connection
from backtest.data.snapshot import build_data_snapshot
from backtest.models.entities import (
    DEVELOPMENT_VALIDATION,
    FORMATION_SELECTION,
    DataSnapshotManifest,
    HistoricalObservationCache,
    ResearchPlan,
    StageAccessBoundary,
    TradingCalendar,
    parse_iso_date,
    verify_calendar_content_address,
)
from backtest.zones.boundaries import build_stage_access_boundary_from_plan

_SAVEPOINT_NAME = "backtest_stage_read_context"


class StageReadContext:
    """Use as a context manager:

        with StageReadContext(
            conn, plan, zone, security_ids, benchmark_security_id, trading_calendar, warmup_start,
        ) as ctx:
            entry = ctx.get_or_compute_observations(security_ids, as_of, discovery_config)

    Entering extracts a strictly-authorized, read-only subset from
    `conn` and builds the snapshot from it; exiting closes that subset.
    `ctx.conn` is that subset -- never the original source connection --
    for the entire time the context is open (see module docstring)."""

    def __init__(
        self, conn, plan: ResearchPlan, zone: str, security_ids: tuple[str, ...],
        benchmark_security_id: str, trading_calendar: TradingCalendar, warmup_start: str,
    ):
        self._source_conn = conn
        self.plan = plan
        self.boundary: StageAccessBoundary = build_stage_access_boundary_from_plan(plan, zone)
        if trading_calendar.calendar_id != plan.trading_calendar_id:
            raise ValueError(
                f"trading_calendar.calendar_id={trading_calendar.calendar_id!r} does not match "
                f"plan.trading_calendar_id={plan.trading_calendar_id!r} -- the plan and the calendar "
                f"actually supplied must be the same one"
            )
        ok, errors = verify_calendar_content_address(trading_calendar)
        if not ok:
            raise ValueError(f"trading_calendar failed content-address verification: {errors}")

        if zone == FORMATION_SELECTION:
            zone_start = plan.formation_start
        elif zone == DEVELOPMENT_VALIDATION:
            zone_start = plan.validation_start
        else:
            raise ValueError(f"unreachable: build_stage_access_boundary_from_plan() already rejected zone={zone!r}")
        if parse_iso_date(warmup_start) is None:
            raise ValueError(f"warmup_start is not a valid ISO date: {warmup_start!r}")
        if warmup_start > zone_start:
            raise ValueError(
                f"warmup_start={warmup_start!r} must not be after this zone's own start {zone_start!r} -- "
                f"warm-up, by definition, precedes (or coincides with) the zone it prepares"
            )
        require_calendar_covers_window(trading_calendar, warmup_start, self.boundary.max_as_of)

        if benchmark_security_id != plan.benchmark_security_id:
            raise ValueError(
                f"benchmark_security_id={benchmark_security_id!r} does not match "
                f"plan.benchmark_security_id={plan.benchmark_security_id!r}"
            )
        self.security_ids = tuple(sorted(set(security_ids)))
        self.benchmark_security_id = benchmark_security_id
        self.trading_calendar = trading_calendar
        self.warmup_start = warmup_start
        self._all_ids = tuple(sorted(set(self.security_ids) | {benchmark_security_id}))
        self._observation_store = _ObservationCacheStore()
        self.conn = None
        self._open = False
        self.manifest: Optional[DataSnapshotManifest] = None

    def __enter__(self) -> "StageReadContext":
        source_query_only_before = bool(self._source_conn.execute("PRAGMA query_only").fetchone()[0])
        self._source_conn.execute(f"SAVEPOINT {_SAVEPOINT_NAME}")
        try:
            self._source_conn.execute("PRAGMA query_only = ON")
            subset_conn = build_authorized_subset_connection(self._source_conn, self.boundary, self._all_ids)
        except Exception:
            self._source_conn.execute(f"ROLLBACK TO {_SAVEPOINT_NAME}")
            self._source_conn.execute(f"RELEASE {_SAVEPOINT_NAME}")
            self._source_conn.execute(f"PRAGMA query_only = {'ON' if source_query_only_before else 'OFF'}")
            raise
        self._source_conn.execute(f"RELEASE {_SAVEPOINT_NAME}")
        self._source_conn.execute(f"PRAGMA query_only = {'ON' if source_query_only_before else 'OFF'}")

        try:
            subset_conn.execute("PRAGMA query_only = ON")
            bounded_access = BoundedPITAccess(subset_conn, self.boundary)
            self.manifest = build_data_snapshot(
                bounded_access, self.security_ids, self.benchmark_security_id, self.trading_calendar,
                self.warmup_start,
            )
        except Exception:
            subset_conn.close()
            raise
        self.conn = subset_conn
        self._open = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._open:
            return
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        self._open = False

    def get_or_compute_observations(
        self, security_ids: tuple[str, ...], as_of: str, discovery_config: DiscoveryConfig,
        config_dir: Optional[Path] = None,
    ) -> HistoricalObservationCache:
        if not self._open:
            raise RuntimeError("StageReadContext is not open -- use it as a context manager")
        return self._observation_store.get_or_compute(
            self.conn, self.boundary, self.manifest, security_ids, as_of, discovery_config, config_dir,
        )
