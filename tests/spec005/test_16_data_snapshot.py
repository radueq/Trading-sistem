"""TEST 16 -- canonical scoped data snapshot (Spec #005 v1.0 SS5/SS6,
Batch 2).

"Freeze or open a consistent read snapshot for the entire run. Hash
exactly that snapshot." "Reject NaN/infinite prices and inconsistent
duplicate keys." Covers the SS23 Snapshot acceptance family: "one
relevant fact correction changes hash; input order does not; concurrent
ingestion cannot mix states."
"""
from types import SimpleNamespace

import pytest

from data_foundation.model import repository as repo
from data_foundation.model.entities import PriceBar

from backtest.data.pit_access import BoundedPITAccess
from backtest.data.snapshot import _price_bar_record, build_data_snapshot
from backtest.models.entities import (
    FORMATION_SELECTION,
    NOT_REPLAYABLE_FROM_RETAINED_DATA,
    StageAccessBoundary,
    verify_snapshot_content_address,
)

from spec005.conftest import PIT_FORMATION_END


def _snapshot(conn, pit_universe, security_ids=None):
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    ids = security_ids or pit_universe["priced_security_ids"]
    return build_data_snapshot(access, ids, pit_universe["benchmark_security_id"], trading_calendar_id="cal_test")


def test_snapshot_passes_its_own_content_address_verification(conn, pit_universe):
    manifest = _snapshot(conn, pit_universe)
    ok, errors = verify_snapshot_content_address(manifest)
    assert ok, errors
    assert manifest.replayable == NOT_REPLAYABLE_FROM_RETAINED_DATA
    assert manifest.replay_artifact_reference is None


def test_repeated_snapshots_of_unchanged_data_produce_the_identical_hash(conn, pit_universe):
    a = _snapshot(conn, pit_universe)
    b = _snapshot(conn, pit_universe)
    assert a.snapshot_id == b.snapshot_id
    assert a.content_digest == b.content_digest


def test_input_order_does_not_affect_the_snapshot_hash(conn, pit_universe):
    """SS23 Snapshot family: "input order does not [change the hash]." """
    ids = pit_universe["priced_security_ids"]
    a = _snapshot(conn, pit_universe, security_ids=ids)
    b = _snapshot(conn, pit_universe, security_ids=tuple(reversed(ids)))
    assert a.snapshot_id == b.snapshot_id
    assert a.security_ids == b.security_ids  # sorted identically regardless of input order


def test_one_relevant_fact_correction_changes_the_hash(conn, pit_universe):
    """SS23 Snapshot family: "one relevant fact correction changes
    hash." `insert_price_bar`'s INSERT OR IGNORE would silently no-op on
    an existing (security_id, date, source_provider) key, so the
    correction is applied via a direct UPDATE -- exactly what "a
    correction" means at the storage level."""
    before = _snapshot(conn, pit_universe)
    sid = pit_universe["sec_a"]
    conn.execute(
        "UPDATE price_history SET raw_close = ? WHERE security_id = ? AND date = ? AND source_provider = 'manual'",
        (999.0, sid, PIT_FORMATION_END),
    )
    conn.commit()
    after = _snapshot(conn, pit_universe)
    assert before.snapshot_id != after.snapshot_id
    assert before.content_digest != after.content_digest


def test_correcting_a_fact_outside_the_universe_does_not_affect_the_hash(conn, pit_universe):
    """Sanity check for the fact-sensitivity test above: a change to a
    security NOT included in this snapshot's own scope must not affect
    its hash -- isolation is scoped by `security_ids`, not by "any DB
    write happened.\""""
    before = _snapshot(conn, pit_universe, security_ids=(pit_universe["sec_a"],))
    conn.execute(
        "UPDATE price_history SET raw_close = ? WHERE security_id = ? AND date = ? AND source_provider = 'manual'",
        (999.0, pit_universe["sec_b"], PIT_FORMATION_END),
    )
    conn.commit()
    after = _snapshot(conn, pit_universe, security_ids=(pit_universe["sec_a"],))
    assert before.snapshot_id == after.snapshot_id


def test_two_providers_reporting_the_same_date_is_rejected_as_an_inconsistent_duplicate_key(conn, pit_universe, now):
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
        _snapshot(conn, pit_universe)


def test_infinite_price_is_rejected(conn, pit_universe):
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
        _snapshot(conn, pit_universe)


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


def test_a_single_synchronous_pass_reads_every_security_at_the_identical_as_of(conn, pit_universe):
    """Proxy for SS23's "concurrent ingestion cannot mix states": every
    logged access shares the SAME as_of, proving there is no moving
    window across which a partial ingestion for one security could be
    picked up while another security reflects an earlier or later
    state."""
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    build_data_snapshot(access, pit_universe["priced_security_ids"], pit_universe["benchmark_security_id"], "cal_test")
    as_of_values = {as_of for _kind, _sid, as_of in access.access_log}
    assert as_of_values == {PIT_FORMATION_END}
