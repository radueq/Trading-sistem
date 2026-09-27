"""TEST 18 -- Isolation: validation/OOS mutations cannot affect
Formation/Selection or Development Validation outputs (Spec #005 v1.0
SS23, Batch 2).

"Mutating validation data cannot alter selection; mutating OOS cannot
alter any #005 output or hash; access spy forbids OOS queries."
"""
import pytest

from backtest.data.pit_access import BoundedPITAccess
from backtest.data.snapshot import build_data_snapshot
from backtest.models.entities import (
    DEVELOPMENT_VALIDATION,
    FORMATION_SELECTION,
    LOCKED_OOS,
    LockedOOSAccessError,
    OutOfScopeAccessError,
    StageAccessBoundary,
)

from spec005.conftest import PIT_FORMATION_END, PIT_LOCKED_OOS_START, PIT_VALIDATION_END, PIT_WARMUP_START


def _mutate_price(conn, security_id: str, date: str, value: float) -> None:
    conn.execute(
        "UPDATE price_history SET raw_close = ? WHERE security_id = ? AND date = ? AND source_provider = 'manual'",
        (value, security_id, date),
    )
    conn.commit()


def _formation_selection_snapshot(conn, pit_universe, pit_calendar):
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    return build_data_snapshot(
        access, pit_universe["priced_security_ids"], pit_universe["benchmark_security_id"], pit_calendar,
        PIT_WARMUP_START,
    )


def test_mutating_validation_range_data_does_not_alter_a_formation_selection_snapshot(conn, pit_universe, pit_calendar):
    before = _formation_selection_snapshot(conn, pit_universe, pit_calendar)
    _mutate_price(conn, pit_universe["sec_a"], PIT_VALIDATION_END, 12345.0)
    after = _formation_selection_snapshot(conn, pit_universe, pit_calendar)
    assert before.snapshot_id == after.snapshot_id
    assert before.content_digest == after.content_digest


def test_mutating_locked_oos_range_data_does_not_alter_a_formation_selection_snapshot(conn, pit_universe, pit_calendar):
    before = _formation_selection_snapshot(conn, pit_universe, pit_calendar)
    _mutate_price(conn, pit_universe["sec_a"], PIT_LOCKED_OOS_START, 99999.0)
    after = _formation_selection_snapshot(conn, pit_universe, pit_calendar)
    assert before.snapshot_id == after.snapshot_id


def test_mutating_locked_oos_range_data_does_not_alter_a_development_validation_snapshot(conn, pit_universe, pit_calendar):
    """The same guarantee generalizes one zone forward: a
    DEVELOPMENT_VALIDATION snapshot (bounded at validation_end) is
    equally unaffected by a Locked-OOS-range mutation."""
    boundary = StageAccessBoundary(zone=DEVELOPMENT_VALIDATION, max_as_of=PIT_VALIDATION_END)
    access = BoundedPITAccess(conn, boundary)
    before = build_data_snapshot(
        access, pit_universe["priced_security_ids"], pit_universe["benchmark_security_id"], pit_calendar,
        PIT_WARMUP_START,
    )

    _mutate_price(conn, pit_universe["sec_a"], PIT_LOCKED_OOS_START, 88888.0)

    access_after = BoundedPITAccess(conn, boundary)
    after = build_data_snapshot(
        access_after, pit_universe["priced_security_ids"], pit_universe["benchmark_security_id"], pit_calendar,
        PIT_WARMUP_START,
    )
    assert before.snapshot_id == after.snapshot_id


def test_formation_selection_facade_cannot_query_the_locked_oos_range(conn, pit_universe):
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    with pytest.raises(OutOfScopeAccessError):
        access.get_price_series_as_of(pit_universe["sec_a"], PIT_LOCKED_OOS_START)
    assert access.access_log == []  # the rejected query left no trace


def test_development_validation_facade_cannot_query_the_locked_oos_range(conn, pit_universe):
    boundary = StageAccessBoundary(zone=DEVELOPMENT_VALIDATION, max_as_of=PIT_VALIDATION_END)
    access = BoundedPITAccess(conn, boundary)
    with pytest.raises(OutOfScopeAccessError):
        access.get_price_series_as_of(pit_universe["sec_a"], PIT_LOCKED_OOS_START)
    assert access.access_log == []


def test_no_boundary_can_ever_be_constructed_for_locked_oos():
    """The strongest form of "access spy forbids OOS queries": there is
    no code path through which a Locked OOS read could even be
    attempted, since the object required to attempt one cannot exist."""
    with pytest.raises(LockedOOSAccessError):
        StageAccessBoundary(zone=LOCKED_OOS, max_as_of=PIT_LOCKED_OOS_START)
