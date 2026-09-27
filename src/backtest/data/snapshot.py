"""Spec #005 v1.0 SS5/SS6 -- canonical scoped data snapshot (Batch 2).

"Freeze or open a consistent read snapshot for the entire run. Hash
exactly that snapshot; concurrent ingestion must not produce a digest
from one state and trades from another." "Use streaming SHA-256 over
canonical typed records... stable primary-key ordering... no ambiguous
concatenation. Reject NaN/infinite prices and inconsistent duplicate
keys."

`build_data_snapshot()` reads every security ONCE, at the single
`as_of = bounded_access.boundary.max_as_of` -- never a moving window
across sessions. Because #001's PIT gateway always returns full history
up to `as_of`, this ONE read at the stage's own upper bound already
captures everything any later, smaller-`as_of` session read within the
same stage could see (warm-up included); it is what SS6 means by "a
separate read-only fingerprint/snapshot operation", distinct from the
session-scoped decision-time reads later batches perform through the
same `BoundedPITAccess` object.
"""
from __future__ import annotations

import hashlib

from backtest.data.pit_access import BoundedPITAccess
from backtest.models.entities import (
    CANONICALIZATION_VERSION_V1,
    NOT_REPLAYABLE_FROM_RETAINED_DATA,
    SNAPSHOT_FACT_CATEGORIES_V1,
    DataSnapshotManifest,
    build_snapshot_id,
    canonical_json,
    snapshot_manifest_fingerprint,
)

_NON_FINITE = (float("inf"), float("-inf"))


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


def _listing_status_record(security_id: str, pit_listing) -> dict:
    if pit_listing is None:
        return {"kind": "LISTING_STATUS", "security_id": security_id, "status": None}
    e = pit_listing.entry
    return {
        "kind": "LISTING_STATUS", "security_id": security_id, "status": e.status,
        "effective_from": e.effective_from, "effective_to": e.effective_to,
        "source_provider": e.source_provider, "delisting_reason": e.delisting_reason,
        "available_at": e.available_at, "knowledge_time_status": pit_listing.knowledge_time_status,
    }


def _symbol_record(security_id: str, ticker) -> dict:
    return {"kind": "SYMBOL", "security_id": security_id, "ticker_as_of": ticker}


def build_data_snapshot(
    bounded_access: BoundedPITAccess, security_ids: tuple[str, ...], benchmark_security_id: str,
    trading_calendar_id: str,
) -> DataSnapshotManifest:
    """`security_ids` order never affects the result -- the universe and
    benchmark are merged, deduplicated and sorted before anything is
    read or hashed (SS23 Snapshot family: "input order does not
    [change the hash]"). Every security is read at the SAME single
    `as_of`, in one synchronous pass, which is what rules out mixing a
    partially-ingested state for one security with a different state
    for another (SS23: "concurrent ingestion cannot mix states")."""
    max_as_of = bounded_access.boundary.max_as_of
    all_ids = tuple(sorted(set(security_ids) | {benchmark_security_id}))

    hasher = hashlib.sha256()
    for sid in all_ids:
        bars = bounded_access.get_price_series_as_of(sid, max_as_of)
        seen_dates: set[str] = set()
        for bar in sorted(bars, key=lambda b: b.date):
            # price_history's actual primary key is (security_id, date,
            # source_provider) -- get_price_history() returns every
            # provider's row for a date, never deduplicated across
            # providers. Two rows for the same (security_id, date) from
            # different providers is exactly the "inconsistent duplicate
            # keys" SS6 says to reject, not a theoretical case.
            if bar.date in seen_dates:
                raise ValueError(f"{sid}: duplicate price bar date in snapshot scope: {bar.date!r}")
            seen_dates.add(bar.date)
            hasher.update(canonical_json(_price_bar_record(sid, bar)).encode("utf-8"))
            hasher.update(b"\n")

        actions = bounded_access.get_corporate_actions_as_of(sid, max_as_of)
        for pit_action in sorted(actions, key=lambda a: a.action.action_id):
            hasher.update(canonical_json(_corporate_action_record(sid, pit_action)).encode("utf-8"))
            hasher.update(b"\n")

        listing = bounded_access.get_listing_status_as_of(sid, max_as_of)
        hasher.update(canonical_json(_listing_status_record(sid, listing)).encode("utf-8"))
        hasher.update(b"\n")

        ticker = bounded_access.get_ticker_as_of(sid, max_as_of)
        hasher.update(canonical_json(_symbol_record(sid, ticker)).encode("utf-8"))
        hasher.update(b"\n")

    content_digest = hasher.hexdigest()
    fp = snapshot_manifest_fingerprint(
        bounded_access.boundary.zone, all_ids, benchmark_security_id, max_as_of, trading_calendar_id,
        SNAPSHOT_FACT_CATEGORIES_V1, CANONICALIZATION_VERSION_V1, content_digest,
        NOT_REPLAYABLE_FROM_RETAINED_DATA, None,
    )
    snapshot_id, snapshot_hash = build_snapshot_id(fp)
    return DataSnapshotManifest(
        snapshot_id=snapshot_id, snapshot_hash=snapshot_hash, stage=bounded_access.boundary.zone,
        security_ids=all_ids, benchmark_security_id=benchmark_security_id, max_as_of=max_as_of,
        trading_calendar_id=trading_calendar_id, table_field_manifest=SNAPSHOT_FACT_CATEGORIES_V1,
        canonicalization_version=CANONICALIZATION_VERSION_V1, content_digest=content_digest,
        replayable=NOT_REPLAYABLE_FROM_RETAINED_DATA, replay_artifact_reference=None,
    )
