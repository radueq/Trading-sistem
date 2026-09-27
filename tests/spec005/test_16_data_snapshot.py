"""TEST 16 -- canonical scoped data snapshot (Spec #005 v1.0 SS5/SS6,
Batch 2, patched round 2).

"Freeze or open a consistent read snapshot for the entire run. Hash
exactly that snapshot." "Reject NaN/infinite prices and inconsistent
duplicate keys." Covers the SS23 Snapshot acceptance family: "one
relevant fact correction changes hash; input order does not; concurrent
ingestion cannot mix states." The genuine multi-connection version of
the "concurrent ingestion" guarantee lives in
`test_19_stage_read_context.py` -- this file covers the calendar
binding, full ticker/listing history sensitivity, and everything else
`build_data_snapshot()` itself is responsible for.
"""
import dataclasses
from types import SimpleNamespace

import pytest

from data_foundation.model import repository as repo
from data_foundation.model.entities import ListingStatusEntry, PriceBar, SymbolHistoryEntry

from backtest.data.calendar import build_trading_calendar
from backtest.data.pit_access import BoundedPITAccess
from backtest.data.snapshot import _price_bar_record, build_data_snapshot
from backtest.models.entities import (
    FORMATION_SELECTION,
    NOT_REPLAYABLE_FROM_RETAINED_DATA,
    CalendarSource,
    StageAccessBoundary,
    verify_snapshot_content_address,
)

from spec005.conftest import PIT_FORMATION_END, PIT_WARMUP_START


def _snapshot(conn, pit_universe, pit_calendar, security_ids=None, min_as_of=PIT_WARMUP_START):
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    ids = security_ids or pit_universe["priced_security_ids"]
    return build_data_snapshot(access, ids, pit_universe["benchmark_security_id"], pit_calendar, min_as_of)


def test_snapshot_passes_its_own_content_address_verification(conn, pit_universe, pit_calendar):
    manifest = _snapshot(conn, pit_universe, pit_calendar)
    ok, errors = verify_snapshot_content_address(manifest)
    assert ok, errors
    assert manifest.replayable == NOT_REPLAYABLE_FROM_RETAINED_DATA
    assert manifest.replay_artifact_reference is None
    assert manifest.trading_calendar_id == pit_calendar.calendar_id


def test_snapshot_rejects_a_calendar_that_fails_its_own_content_address(conn, pit_universe, pit_calendar):
    """SS11/SS21: a snapshot may not bind to a calendar reference that
    doesn't match its own claimed identity -- Batch 2 patch round-2
    review, finding #2."""
    tampered = dataclasses.replace(pit_calendar, session_dates=pit_calendar.session_dates[:-1])
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    with pytest.raises(ValueError, match="content-address"):
        build_data_snapshot(
            access, pit_universe["priced_security_ids"], pit_universe["benchmark_security_id"], tampered,
            PIT_WARMUP_START,
        )


def test_repeated_snapshots_of_unchanged_data_produce_the_identical_hash(conn, pit_universe, pit_calendar):
    a = _snapshot(conn, pit_universe, pit_calendar)
    b = _snapshot(conn, pit_universe, pit_calendar)
    assert a.snapshot_id == b.snapshot_id
    assert a.content_digest == b.content_digest


def test_input_order_does_not_affect_the_snapshot_hash(conn, pit_universe, pit_calendar):
    """SS23 Snapshot family: "input order does not [change the hash]." """
    ids = pit_universe["priced_security_ids"]
    a = _snapshot(conn, pit_universe, pit_calendar, security_ids=ids)
    b = _snapshot(conn, pit_universe, pit_calendar, security_ids=tuple(reversed(ids)))
    assert a.snapshot_id == b.snapshot_id
    assert a.security_ids == b.security_ids  # sorted identically regardless of input order


def test_one_relevant_fact_correction_changes_the_hash(conn, pit_universe, pit_calendar):
    """SS23 Snapshot family: "one relevant fact correction changes
    hash." `insert_price_bar`'s INSERT OR IGNORE would silently no-op on
    an existing (security_id, date, source_provider) key, so the
    correction is applied via a direct UPDATE -- exactly what "a
    correction" means at the storage level."""
    before = _snapshot(conn, pit_universe, pit_calendar)
    sid = pit_universe["sec_a"]
    conn.execute(
        "UPDATE price_history SET raw_close = ? WHERE security_id = ? AND date = ? AND source_provider = 'manual'",
        (999.0, sid, PIT_FORMATION_END),
    )
    conn.commit()
    after = _snapshot(conn, pit_universe, pit_calendar)
    assert before.snapshot_id != after.snapshot_id
    assert before.content_digest != after.content_digest


def test_correcting_a_fact_outside_the_universe_does_not_affect_the_hash(conn, pit_universe, pit_calendar):
    """Sanity check for the fact-sensitivity test above: a change to a
    security NOT included in this snapshot's own scope must not affect
    its hash -- isolation is scoped by `security_ids`, not by "any DB
    write happened.\""""
    before = _snapshot(conn, pit_universe, pit_calendar, security_ids=(pit_universe["sec_a"],))
    conn.execute(
        "UPDATE price_history SET raw_close = ? WHERE security_id = ? AND date = ? AND source_provider = 'manual'",
        (999.0, pit_universe["sec_b"], PIT_FORMATION_END),
    )
    conn.commit()
    after = _snapshot(conn, pit_universe, pit_calendar, security_ids=(pit_universe["sec_a"],))
    assert before.snapshot_id == after.snapshot_id


def test_a_historical_ticker_change_invisible_at_max_as_of_still_changes_the_hash(conn, pit_universe, pit_calendar, now):
    """Batch 2 patch round-2 review, finding #2 (the exact case
    reproduced): the CURRENT ticker as of max_as_of can stay the same
    while an EARLIER era's ticker changes -- a later, session-level read
    at that earlier date would see a different answer. The snapshot
    must be sensitive to that even though its own single `max_as_of`
    answer is unaffected."""
    sid = pit_universe["sec_a"]
    repo.insert_symbol_history(conn, SymbolHistoryEntry(
        security_id=sid, ticker="OLDTICK", exchange=None, valid_from=PIT_WARMUP_START,
        valid_to="2024-01-01", source_provider="manual",
    ))
    repo.insert_symbol_history(conn, SymbolHistoryEntry(
        security_id=sid, ticker="NEWTICK", exchange=None, valid_from="2024-01-01",
        valid_to=None, source_provider="manual",
    ))
    before = _snapshot(conn, pit_universe, pit_calendar)

    # Correct the EARLIER era's ticker only -- the max_as_of (current)
    # answer for `sid` is still "NEWTICK", completely unaffected. A raw
    # UPDATE (not close_symbol_history(), which only ever touches an
    # OPEN row where valid_to IS NULL) mirrors the same "correction"
    # pattern already used for price_history/listing_status_history.
    conn.execute(
        "UPDATE symbol_history SET ticker = ? WHERE security_id = ? AND valid_from = ?",
        ("CORRECTEDTICK", sid, PIT_WARMUP_START),
    )
    conn.commit()
    after = _snapshot(conn, pit_universe, pit_calendar)
    assert before.snapshot_id != after.snapshot_id


def test_a_historical_listing_status_change_invisible_at_max_as_of_still_changes_the_hash(conn, pit_universe, pit_calendar, now):
    sid = pit_universe["sec_b"]
    repo.upsert_listing_status(conn, ListingStatusEntry(
        security_id=sid, status="HALTED", effective_from="2023-11-01", effective_to="2023-11-05",
        source_provider="manual", delisting_reason=None, available_at=None, last_updated_timestamp=now,
    ))
    repo.upsert_listing_status(conn, ListingStatusEntry(
        security_id=sid, status="ACTIVE", effective_from="2023-11-05", effective_to=None,
        source_provider="manual", delisting_reason=None, available_at=None, last_updated_timestamp=now,
    ))
    before = _snapshot(conn, pit_universe, pit_calendar)

    # Correct only the now-closed HALTED entry's window -- the current
    # (max_as_of) status is still "ACTIVE", unaffected.
    conn.execute(
        "UPDATE listing_status_history SET effective_to = '2023-11-06' "
        "WHERE security_id = ? AND effective_from = '2023-11-01'",
        (sid,),
    )
    conn.commit()
    after = _snapshot(conn, pit_universe, pit_calendar)
    assert before.snapshot_id != after.snapshot_id


def test_two_providers_reporting_the_same_date_is_rejected_as_an_inconsistent_duplicate_key(conn, pit_universe, pit_calendar, now):
    """SS6: "Reject... inconsistent duplicate keys." `price_history`'s
    actual primary key is (security_id, date, source_provider) --
    get_price_history() returns every provider's row for a date, never
    deduplicated across providers. A second provider reporting a bar
    for a date `sec_a` already has (under "manual") is a real,
    reachable case through this schema, not a theoretical one."""
    sid = pit_universe["sec_a"]
    repo.insert_price_bars(conn, [PriceBar(
        security_id=sid, date=PIT_FORMATION_END, raw_open=1.0, raw_high=1.0, raw_low=1.0, raw_close=1.0,
        raw_volume=1, source_provider="other_provider", ingestion_timestamp=now,
    )])
    with pytest.raises(ValueError, match="duplicate price bar date"):
        _snapshot(conn, pit_universe, pit_calendar)


def test_infinite_price_is_rejected(conn, pit_universe, pit_calendar):
    """SS6: "Reject NaN/infinite prices" -- `inf` round-trips through
    SQLite's REAL storage unchanged (unlike NaN, which SQLite's driver
    silently coerces to NULL on write -- see
    `test_nan_value_is_rejected_at_the_record_builder_level` below for
    why that case is unit-tested at the record-builder level instead)."""
    sid = pit_universe["sec_a"]
    conn.execute(
        "UPDATE price_history SET raw_close = ? WHERE security_id = ? AND date = ? AND source_provider = 'manual'",
        (float("inf"), sid, PIT_FORMATION_END),
    )
    conn.commit()
    with pytest.raises(ValueError, match="infinite"):
        _snapshot(conn, pit_universe, pit_calendar)


def test_nan_value_is_rejected_at_the_record_builder_level():
    """SQLite's own driver coerces a NaN REAL to NULL on write (verified
    empirically: inserting float('nan') and reading it back yields
    None), so a genuine end-to-end DB round-trip can never exercise this
    branch -- the record builder's own defense is unit-tested directly
    instead, e.g. against a bar constructed in-process (not yet
    persisted) or a future non-SQLite backend."""
    bar = SimpleNamespace(date="2024-01-15", raw_open=1.0, raw_high=1.0, raw_low=1.0, raw_close=float("nan"), raw_volume=100)
    with pytest.raises(ValueError, match="NaN"):
        _price_bar_record("sec_x", bar)


def test_snapshot_rejects_a_calendar_whose_coverage_end_is_before_max_as_of(conn, pit_universe, pit_calendar):
    """Batch 2 patch round-3 review, finding #4: a calendar too SHORT at
    the top end would silently omit real session dates from the
    ticker/listing history loop while the observation cache could still
    be asked about dates in that omitted range -- a genuinely
    self-consistent (content-addressed) calendar whose own declared
    `coverage_end` falls before this stage's `max_as_of` must be
    rejected outright, never silently truncated."""
    short_dates = tuple(d for d in pit_calendar.session_dates if d <= "2024-01-15")
    short_calendar = build_trading_calendar(
        source=CalendarSource.SYNTHETIC_TEST_FIXTURE.value, calendar_identifier="TOO_SHORT_CALENDAR",
        calendar_version="v1", market=pit_calendar.market, timezone=pit_calendar.timezone,
        coverage_start=pit_calendar.coverage_start, coverage_end="2024-01-15", session_dates=short_dates,
        session_open_time=pit_calendar.session_open_time, session_close_time=pit_calendar.session_close_time,
    )
    with pytest.raises(ValueError, match="coverage_end"):
        _snapshot(conn, pit_universe, short_calendar)


def test_snapshot_rejects_a_structurally_invalid_calendar(conn, pit_universe, pit_calendar):
    """Finding #4: content-address verification alone only proves the
    calendar's fields match its OWN claimed hash -- a calendar with
    `session_open_time` after `session_close_time` can still be
    perfectly self-consistent. `verify_calendar_structure()` must run
    too, before anything is read."""
    backwards_calendar = build_trading_calendar(
        source=CalendarSource.SYNTHETIC_TEST_FIXTURE.value, calendar_identifier="BACKWARDS_TIMES_CALENDAR",
        calendar_version="v1", market=pit_calendar.market, timezone=pit_calendar.timezone,
        coverage_start=pit_calendar.coverage_start, coverage_end=pit_calendar.coverage_end,
        session_dates=pit_calendar.session_dates, session_open_time="16:00", session_close_time="09:30",
    )
    with pytest.raises(ValueError, match="structural verification"):
        _snapshot(conn, pit_universe, backwards_calendar)


def test_snapshot_rejects_a_calendar_covering_the_zone_but_omitting_part_of_the_warmup(conn, pit_universe, pit_calendar):
    """Batch 2 patch round-4 review, finding #3: `require_calendar_covers_
    window()` at the context level checks `[warmup_start, max_as_of]`,
    but `build_data_snapshot()` itself must independently enforce the
    same thing -- a calendar whose `coverage_start` only reaches back to
    the ZONE's own start (never as far as the declared `min_as_of`/
    warm-up start) must be rejected, even though it fully covers
    `[zone_start, max_as_of]`."""
    from spec005.conftest import PIT_FORMATION_START

    short_warmup_dates = tuple(d for d in pit_calendar.session_dates if d >= PIT_FORMATION_START)
    short_warmup_calendar = build_trading_calendar(
        source=CalendarSource.SYNTHETIC_TEST_FIXTURE.value, calendar_identifier="SHORT_WARMUP_CALENDAR",
        calendar_version="v1", market=pit_calendar.market, timezone=pit_calendar.timezone,
        coverage_start=PIT_FORMATION_START, coverage_end=pit_calendar.coverage_end, session_dates=short_warmup_dates,
        session_open_time=pit_calendar.session_open_time, session_close_time=pit_calendar.session_close_time,
    )
    with pytest.raises(ValueError, match="warm-up"):
        _snapshot(conn, pit_universe, short_warmup_calendar, min_as_of=PIT_WARMUP_START)


def test_correcting_the_security_master_changes_the_hash(conn, pit_universe, pit_calendar):
    """Finding #4/Security Master: `security_type`/`primary_exchange`/
    `currency`/`source_provider`/`source_security_id` are now part of
    the fingerprint via the licensed direct read (Spec #005 SS6) -- a
    correction to any of them must change the snapshot's own digest,
    exactly like a price or corporate-action correction does."""
    before = _snapshot(conn, pit_universe, pit_calendar)
    sid = pit_universe["sec_a"]
    # `insert_security_master()` is INSERT OR IGNORE (same gotcha as
    # price_history/listing_status_history above) -- a correction to an
    # EXISTING row is a direct UPDATE, mirroring those tests' pattern.
    conn.execute("UPDATE security_master SET currency = 'EUR' WHERE security_id = ?", (sid,))
    conn.commit()
    after = _snapshot(conn, pit_universe, pit_calendar)
    assert before.snapshot_id != after.snapshot_id


def test_price_and_corporate_action_reads_use_the_single_max_as_of(conn, pit_universe, pit_calendar):
    """PRICE_BARS/CORPORATE_ACTIONS still use the single `max_as_of`
    (SS6's snapshot-at-the-boundary reading) -- only SYMBOL_HISTORY/
    LISTING_STATUS iterate every session date, per finding #2's fix."""
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    build_data_snapshot(
        access, pit_universe["priced_security_ids"], pit_universe["benchmark_security_id"], pit_calendar,
        PIT_WARMUP_START,
    )
    price_and_action_as_ofs = {
        as_of for kind, _sid, as_of in access.access_log if kind in ("PRICE_BARS", "CORPORATE_ACTIONS")
    }
    assert price_and_action_as_ofs == {PIT_FORMATION_END}
    history_as_ofs = {
        as_of for kind, _sid, as_of in access.access_log if kind in ("SYMBOL_HISTORY", "LISTING_STATUS")
    }
    assert len(history_as_ofs) > 1  # spans many session dates, not just max_as_of
