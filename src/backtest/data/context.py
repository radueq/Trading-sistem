"""Spec #005 v1.0 SS3/SS5/SS6/SS7 -- the stage read context (Batch 2
patch, round 3).

Batch 2 patch round-2 review, findings #1 and #3: a snapshot built from
successive unprotected reads can mix pre- and post-write state across
two connections; a cache call taking a bare `(conn, snapshot_id)` pair
has nothing tying that string to `conn`'s actual live state, so it can
compute against changed data while still labeling the result under a
stale snapshot's identity. `StageReadContext` closes both gaps by being
the ONE object that: derives and verifies the `StageAccessBoundary` from
a validated `ResearchPlan` (finding #4), opens ONE SQLite SAVEPOINT held
for its entire lifetime, builds the `DataSnapshotManifest` once inside
that SAVEPOINT, and is the only way to reach
`_ObservationCacheStore.get_or_compute()` -- always with the SAME
connection/transaction the manifest itself was built from and
`self.manifest` (never a caller-supplied snapshot_id). A caller cannot
construct a mismatched (conn, snapshot_id, boundary) combination through
this object; the only way to get a `HistoricalObservationCache` at all
is through a `StageReadContext` that has already verified all of it.

Batch 2 patch round-3 review (three more P1 findings closed here):

2. Nothing previously stopped a caller from mutating `ctx.conn` while
   the context was open -- a write on the SAME connection is visible
   INSIDE its own still-open SAVEPOINT (a SAVEPOINT only isolates
   against OTHER connections, see `backtest.data.snapshot`'s module
   docstring), so the manifest's own hash could silently stop matching
   the data a later `get_or_compute_observations()` call in the same
   context would see. `__enter__` now sets `PRAGMA query_only = ON` on
   `self.conn` right after the snapshot is built, for the rest of the
   context's open lifetime; `__exit__` restores it to `OFF`.
3. `get_or_compute_observations()` used to hand Discovery the raw stage
   connection -- supervising only the RETURNED `as_of` label (see
   `backtest.data.cache`) cannot catch a substitute that reads
   out-of-scope data internally and reports an honest label anyway.
   `__enter__` now also builds one `_subset_conn` via
   `backtest.data.pit_access.build_authorized_price_subset_connection()`
   -- a copy with every `price_history` row beyond `self.boundary.
   max_as_of` physically absent -- and `get_or_compute_observations()`
   passes THAT connection to the cache store instead of `self.conn`.
   `__exit__` closes it.
4. The calendar's own declared coverage must actually contain this
   zone's real start date, not just this snapshot's own upper
   `max_as_of` (checked separately inside `build_data_snapshot()`
   itself) -- `__init__` now calls `backtest.data.calendar.
   require_calendar_covers_window()` with the plan's own zone start
   (`formation_start`/`validation_start`) through `boundary.max_as_of`,
   fail-closed before anything is ever read.
"""
from __future__ import annotations

from typing import Optional

from discovery.config.loader import DiscoveryConfig

from backtest.data.cache import _ObservationCacheStore
from backtest.data.calendar import require_calendar_covers_window
from backtest.data.pit_access import BoundedPITAccess, build_authorized_price_subset_connection
from backtest.data.snapshot import build_data_snapshot
from backtest.models.entities import (
    DEVELOPMENT_VALIDATION,
    FORMATION_SELECTION,
    DataSnapshotManifest,
    HistoricalObservationCache,
    ResearchPlan,
    StageAccessBoundary,
    TradingCalendar,
    verify_calendar_content_address,
)
from backtest.zones.boundaries import build_stage_access_boundary_from_plan

_SAVEPOINT_NAME = "backtest_stage_read_context"


class StageReadContext:
    """Use as a context manager:

        with StageReadContext(conn, plan, zone, security_ids, benchmark_security_id, trading_calendar) as ctx:
            entry = ctx.get_or_compute_observations(security_ids, as_of, discovery_config)

    Entering opens one SAVEPOINT and builds the snapshot inside it;
    exiting releases it (or rolls back to it on an exception). Every
    read this context performs -- the snapshot's own reads AND every
    `compute_discovery_observations()` call `get_or_compute_observations()`
    makes (including that function's OWN indirect PIT reads) -- shares
    this single connection and this single open transaction, so nothing
    reached through this context can ever observe two different
    database states."""

    def __init__(
        self, conn, plan: ResearchPlan, zone: str, security_ids: tuple[str, ...],
        benchmark_security_id: str, trading_calendar: TradingCalendar,
    ):
        self.conn = conn
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
        require_calendar_covers_window(trading_calendar, zone_start, self.boundary.max_as_of)
        if benchmark_security_id != plan.benchmark_security_id:
            raise ValueError(
                f"benchmark_security_id={benchmark_security_id!r} does not match "
                f"plan.benchmark_security_id={plan.benchmark_security_id!r}"
            )
        self.security_ids = tuple(sorted(set(security_ids)))
        self.benchmark_security_id = benchmark_security_id
        self.trading_calendar = trading_calendar
        self._bounded_access = BoundedPITAccess(conn, self.boundary)
        self._observation_store = _ObservationCacheStore()
        self._subset_conn = None
        self._open = False
        self.manifest: Optional[DataSnapshotManifest] = None

    def __enter__(self) -> "StageReadContext":
        self.conn.execute(f"SAVEPOINT {_SAVEPOINT_NAME}")
        self._open = True
        try:
            self.manifest = build_data_snapshot(
                self._bounded_access, self.security_ids, self.benchmark_security_id, self.trading_calendar,
            )
            # Round-3 fix (finding #2): no write on this SAME connection
            # may become visible inside our own still-open SAVEPOINT for
            # the rest of this context's lifetime -- a SAVEPOINT only
            # isolates against OTHER connections' writes, never this
            # one's own.
            self.conn.execute("PRAGMA query_only = ON")
            # Round-3 fix (finding #3): hand Discovery a connection with
            # every out-of-scope price_history row physically absent,
            # not the raw stage connection -- closes the gap where only
            # the RETURNED as_of label was ever checked.
            self._subset_conn = build_authorized_price_subset_connection(self.conn, self.boundary)
        except Exception:
            self.conn.execute("PRAGMA query_only = OFF")
            self.conn.execute(f"ROLLBACK TO {_SAVEPOINT_NAME}")
            self.conn.execute(f"RELEASE {_SAVEPOINT_NAME}")
            self._open = False
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._open:
            return
        if self._subset_conn is not None:
            self._subset_conn.close()
            self._subset_conn = None
        self.conn.execute("PRAGMA query_only = OFF")
        if exc_type is None:
            self.conn.execute(f"RELEASE {_SAVEPOINT_NAME}")
        else:
            self.conn.execute(f"ROLLBACK TO {_SAVEPOINT_NAME}")
            self.conn.execute(f"RELEASE {_SAVEPOINT_NAME}")
        self._open = False

    def get_or_compute_observations(
        self, security_ids: tuple[str, ...], as_of: str, discovery_config: DiscoveryConfig,
    ) -> HistoricalObservationCache:
        if not self._open:
            raise RuntimeError("StageReadContext is not open -- use it as a context manager")
        return self._observation_store.get_or_compute(
            self._subset_conn, self.boundary, self.manifest, security_ids, as_of, discovery_config,
        )
