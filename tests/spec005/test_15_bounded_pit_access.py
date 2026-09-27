"""TEST 15 -- BoundedPITAccess facade (Spec #005 v1.0 SS3/SS6, Batch 2).

Every #001 PIT read #005 performs must go through this facade, never a
direct `data_foundation.pit.access` import elsewhere under
`src/backtest/` -- the boundary check runs BEFORE delegating, so a
rejected query never reaches #001 at all and leaves no trace in
`access_log`.
"""
import pytest

from backtest.data.pit_access import BoundedPITAccess
from backtest.models.entities import FORMATION_SELECTION, OutOfScopeAccessError, StageAccessBoundary

from spec005.conftest import PIT_FORMATION_END
from spec005.fixtures.pit_universe import insert_corporate_action, insert_listing_status


def test_bounded_access_returns_real_price_bars_within_scope(conn, pit_universe):
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    bars = access.get_price_series_as_of(pit_universe["sec_a"], PIT_FORMATION_END)
    assert bars
    assert all(b.date <= PIT_FORMATION_END for b in bars)


def test_bounded_access_rejects_a_query_past_the_boundary(conn, pit_universe):
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    with pytest.raises(OutOfScopeAccessError):
        access.get_price_series_as_of(pit_universe["sec_a"], "2024-02-15")


def test_rejected_query_is_never_logged(conn, pit_universe):
    """The "access spy" property: a rejected query leaves no trace in
    access_log -- the boundary check runs BEFORE delegating to #001, so
    the underlying gateway is never even called."""
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    with pytest.raises(OutOfScopeAccessError):
        access.get_price_series_as_of(pit_universe["sec_a"], "2024-02-15")
    assert access.access_log == []


def test_accepted_queries_across_all_four_pit_functions_are_logged(conn, pit_universe):
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    sid = pit_universe["sec_a"]
    access.get_price_series_as_of(sid, PIT_FORMATION_END)
    access.get_corporate_actions_as_of(sid, PIT_FORMATION_END)
    access.get_listing_status_as_of(sid, PIT_FORMATION_END)
    access.get_ticker_as_of(sid, PIT_FORMATION_END)
    kinds = {kind for kind, _sid, _as_of in access.access_log}
    assert kinds == {"PRICE_BARS", "CORPORATE_ACTIONS", "LISTING_STATUS", "SYMBOL_HISTORY"}
    assert all(as_of == PIT_FORMATION_END for _kind, _sid, as_of in access.access_log)


def test_corporate_actions_pass_through_real_pit_derivation_not_a_raw_read(conn, pit_universe, now):
    sid = pit_universe["sec_a"]
    insert_corporate_action(conn, sid, "ca_test15", "SPLIT", "2024-01-15", 2.0, now)
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    actions = access.get_corporate_actions_as_of(sid, PIT_FORMATION_END)
    assert len(actions) == 1
    assert actions[0].pit_status == "EFFECTIVE"


def test_listing_status_pass_through_real_pit_derivation_not_a_raw_read(conn, pit_universe, now):
    sid = pit_universe["sec_b"]
    insert_listing_status(conn, sid, "ACTIVE", "2023-01-01", now)
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    listing = access.get_listing_status_as_of(sid, PIT_FORMATION_END)
    assert listing is not None
    assert listing.entry.status == "ACTIVE"


def test_ticker_as_of_returns_none_for_a_security_with_no_symbol_history(conn, pit_universe):
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    assert access.get_ticker_as_of(pit_universe["sec_a"], PIT_FORMATION_END) is None


def test_boundary_cannot_be_reassigned_after_construction(conn, pit_universe):
    """A plain public `boundary` attribute could be swapped for a wider
    one post-construction, silently defeating the whole guarantee this
    object exists to provide -- `boundary` is a read-only property."""
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of=PIT_FORMATION_END)
    access = BoundedPITAccess(conn, boundary)
    wider = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of="2099-12-31")
    with pytest.raises(AttributeError):
        access.boundary = wider
