"""Spec #005 v1.0 SS5/SS6 -- canonical scoped data snapshot (Batch 2).

"Freeze or open a consistent read snapshot for the entire run. Hash
exactly that snapshot; concurrent ingestion must not produce a digest
from one state and trades from another." "Use streaming SHA-256 over
canonical typed records... stable primary-key ordering... no ambiguous
concatenation. Reject NaN/infinite prices and inconsistent duplicate
keys."

Batch 2 patch round-2 review (two P1 findings closed): (1) the whole
read+hash loop runs inside one SQLite SAVEPOINT, held open for its
entire duration -- verified empirically (two real file-backed
connections): once this connection's SAVEPOINT has done its first read,
a concurrent writer's COMMIT on another connection BLOCKS until this
SAVEPOINT is released, so every read inside this function observes one
single, unchanging database state; (2) `security/symbol history` and
`listing status` are hashed at EVERY one of the verified
`TradingCalendar`'s own session dates up to `max_as_of`, not just the
"current" answer -- a correction to historical ticker/listing data now
changes the digest even if the CURRENT-as-of-max_as_of answer is
unaffected.

Batch 2 patch round-3 review (two more P1 findings closed):

3. `trading_calendar` was verified for content-address only, never
   structure or coverage -- a calendar too SHORT at the top end (its
   own `coverage_end` before `max_as_of`) would silently omit real
   session dates from the ticker/listing history loop above, while the
   observation cache could still be asked about dates in that omitted
   range. Both `verify_calendar_structure()` and an explicit
   `coverage_end >= max_as_of` check now run before anything is read.
4. Security Master (`security_type`/`primary_exchange`/`currency`/
   `source_provider`/`source_security_id`) is now included in the
   fingerprint via a DIRECT `data_foundation.model.repository.
   get_security_by_id()` read -- confirmed as the exact case Spec #005
   SS6 already licenses: "A separate read-only fingerprint/snapshot
   operation may read underlying facts inside the stage's authorized
   scope" (distinct from "never query raw tables as an alternative
   feature/fill engine", which is about decision/signal computations,
   not this operation). This table has no knowledge-time field at all
   in the Spec #001 schema -- these facts are recorded as plain,
   un-dated identity facts, never presented as PIT-validated history,
   and this read stays confined to `build_data_snapshot()`; nothing
   feeds it into any signal/execution computation.
"""
from __future__ import annotations

import hashlib

from data_foundation.model import repository as repo

from backtest.data.pit_access import BoundedPITAccess
from backtest.models.entities import (
    CANONICALIZATION_VERSION_V1,
    NOT_REPLAYABLE_FROM_RETAINED_DATA,
    SNAPSHOT_FACT_CATEGORIES_V1,
    DataSnapshotManifest,
    TradingCalendar,
    build_snapshot_id,
    canonical_json,
    snapshot_manifest_fingerprint,
    verify_calendar_content_address,
    verify_calendar_structure,
)

_NON_FINITE = (float("inf"), float("-inf"))
_SAVEPOINT_NAME = "backtest_snapshot_read"


def _require_finite_or_none(value, label: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} is not a number: {value!r}")
    if value != value or value in _NON_FINITE:  # value != value is the NaN check
        raise ValueError(f"{label} is NaN/infinite -- Spec #005 SS6 requires rejecting this before hashing")


def _price_bar_record(security_id: str, bar) -> dict:
    for field_name, value in (
        ("raw_open", bar.raw_open), ("raw_high", bar.raw_high),
        ("raw_low", bar.raw_low), ("raw_close", bar.raw_close),
    ):
        _require_finite_or_none(value, f"{security_id}/{bar.date}.{field_name}")
    return {
        "kind": "PRICE_BAR", "security_id": security_id, "date": bar.date,
        "raw_open": bar.raw_open, "raw_high": bar.raw_high, "raw_low": bar.raw_low,
        "raw_close": bar.raw_close, "raw_volume": bar.raw_volume,
    }


def _corporate_action_record(security_id: str, pit_action) -> dict:
    a = pit_action.action
    _require_finite_or_none(a.value, f"{security_id}/{a.action_id}.value")
    return {
        "kind": "CORPORATE_ACTION", "security_id": security_id, "action_id": a.action_id,
        "action_type": a.action_type, "announcement_date": a.announcement_date,
        "effective_date": a.effective_date, "value": a.value, "source_provider": a.source_provider,
        "source_status": a.source_status, "source_status_date": a.source_status_date,
        "available_at": a.available_at, "pit_status": pit_action.pit_status,
        "knowledge_time_status": pit_action.knowledge_time_status,
    }


def _listing_status_record(security_id: str, as_of: str, pit_listing) -> dict:
    if pit_listing is None:
        return {"kind": "LISTING_STATUS", "security_id": security_id, "as_of": as_of, "status": None}
    e = pit_listing.entry
    return {
        "kind": "LISTING_STATUS", "security_id": security_id, "as_of": as_of, "status": e.status,
        "effective_from": e.effective_from, "effective_to": e.effective_to,
        "source_provider": e.source_provider, "delisting_reason": e.delisting_reason,
        "available_at": e.available_at, "knowledge_time_status": pit_listing.knowledge_time_status,
    }


def _symbol_record(security_id: str, as_of: str, ticker) -> dict:
    return {"kind": "SYMBOL", "security_id": security_id, "as_of": as_of, "ticker_as_of": ticker}


def _security_master_record(security_id: str, master) -> dict:
    if master is None:
        return {"kind": "SECURITY_MASTER", "security_id": security_id, "security_type": None}
    return {
        "kind": "SECURITY_MASTER", "security_id": security_id, "security_type": master.security_type,
        "primary_exchange": master.primary_exchange, "currency": master.currency,
        "source_provider": master.source_provider, "source_security_id": master.source_security_id,
    }


def build_data_snapshot(
    bounded_access: BoundedPITAccess, security_ids: tuple[str, ...], benchmark_security_id: str,
    trading_calendar: TradingCalendar,
) -> DataSnapshotManifest:
    """`security_ids` order never affects the result -- the universe and
    benchmark are merged, deduplicated and sorted before anything is
    read or hashed (SS23 Snapshot family: "input order does not
    [change the hash]"). `trading_calendar` is verified against its own
    content address first (SS11/SS21 discipline) -- a snapshot may not
    bind to a calendar reference that doesn't match its own claimed
    identity -- and its `calendar_id` (not a bare caller-supplied
    string) becomes the manifest's `trading_calendar_id`. Every read
    happens inside one held-open SAVEPOINT (see module docstring)."""
    ok, errors = verify_calendar_content_address(trading_calendar)
    if not ok:
        raise ValueError(f"trading_calendar failed content-address verification: {errors}")
    structure_ok, structure_errors = verify_calendar_structure(trading_calendar)
    if not structure_ok:
        raise ValueError(f"trading_calendar failed structural verification: {structure_errors}")

    max_as_of = bounded_access.boundary.max_as_of
    if trading_calendar.coverage_end < max_as_of:
        raise ValueError(
            f"trading_calendar's coverage_end={trading_calendar.coverage_end!r} is before this stage's own "
            f"max_as_of={max_as_of!r} -- the calendar does not cover the full authorized window, and the "
            f"observation cache could still be asked about dates this snapshot never hashed"
        )
    all_ids = tuple(sorted(set(security_ids) | {benchmark_security_id}))
    session_dates_in_scope = tuple(d for d in trading_calendar.session_dates if d <= max_as_of)

    conn = bounded_access.conn
    conn.execute(f"SAVEPOINT {_SAVEPOINT_NAME}")
    try:
        hasher = hashlib.sha256()
        for sid in all_ids:
            bars = bounded_access.get_price_series_as_of(sid, max_as_of)
            seen_dates: set[str] = set()
            for bar in sorted(bars, key=lambda b: b.date):
                # price_history's actual primary key is (security_id,
                # date, source_provider) -- get_price_history() returns
                # every provider's row for a date, never deduplicated
                # across providers. Two rows for the same (security_id,
                # date) from different providers is exactly the
                # "inconsistent duplicate keys" SS6 says to reject, not
                # a theoretical case.
                if bar.date in seen_dates:
                    raise ValueError(f"{sid}: duplicate price bar date in snapshot scope: {bar.date!r}")
                seen_dates.add(bar.date)
                hasher.update(canonical_json(_price_bar_record(sid, bar)).encode("utf-8"))
                hasher.update(b"\n")

            actions = bounded_access.get_corporate_actions_as_of(sid, max_as_of)
            for pit_action in sorted(actions, key=lambda a: a.action.action_id):
                hasher.update(canonical_json(_corporate_action_record(sid, pit_action)).encode("utf-8"))
                hasher.update(b"\n")

            # Security Master has no knowledge-time field in the #001
            # schema at all -- there is no "as_of" to bound here. This
            # is the licensed "separate read-only fingerprint operation"
            # (SS6, see module docstring point 4), reading through
            # `conn` directly rather than through `bounded_access` --
            # still inside the same held-open SAVEPOINT, so it observes
            # the identical consistent state as every other read above.
            master = repo.get_security_by_id(conn, sid)
            hasher.update(canonical_json(_security_master_record(sid, master)).encode("utf-8"))
            hasher.update(b"\n")

            # Full PIT-safe history across every session in scope, not
            # just the answer at max_as_of (see module docstring, point
            # 2) -- a later, session-level read can query ANY of these
            # dates, so the snapshot must be sensitive to every one of
            # them.
            for d in session_dates_in_scope:
                listing = bounded_access.get_listing_status_as_of(sid, d)
                hasher.update(canonical_json(_listing_status_record(sid, d, listing)).encode("utf-8"))
                hasher.update(b"\n")

                ticker = bounded_access.get_ticker_as_of(sid, d)
                hasher.update(canonical_json(_symbol_record(sid, d, ticker)).encode("utf-8"))
                hasher.update(b"\n")

        content_digest = hasher.hexdigest()
    except Exception:
        conn.execute(f"ROLLBACK TO {_SAVEPOINT_NAME}")
        conn.execute(f"RELEASE {_SAVEPOINT_NAME}")
        raise
    conn.execute(f"RELEASE {_SAVEPOINT_NAME}")

    fp = snapshot_manifest_fingerprint(
        bounded_access.boundary.zone, all_ids, benchmark_security_id, max_as_of, trading_calendar.calendar_id,
        SNAPSHOT_FACT_CATEGORIES_V1, CANONICALIZATION_VERSION_V1, content_digest,
        NOT_REPLAYABLE_FROM_RETAINED_DATA, None,
    )
    snapshot_id, snapshot_hash = build_snapshot_id(fp)
    return DataSnapshotManifest(
        snapshot_id=snapshot_id, snapshot_hash=snapshot_hash, stage=bounded_access.boundary.zone,
        security_ids=all_ids, benchmark_security_id=benchmark_security_id, max_as_of=max_as_of,
        trading_calendar_id=trading_calendar.calendar_id, table_field_manifest=SNAPSHOT_FACT_CATEGORIES_V1,
        canonicalization_version=CANONICALIZATION_VERSION_V1, content_digest=content_digest,
        replayable=NOT_REPLAYABLE_FROM_RETAINED_DATA, replay_artifact_reference=None,
    )
