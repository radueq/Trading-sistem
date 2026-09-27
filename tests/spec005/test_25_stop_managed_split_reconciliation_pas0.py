"""TEST 25 -- Pas 0 split reconciliation for an already-open
STOP_MANAGED_INVALIDATION position (docs/spec005_exit_amendment_v1.0.md,
ACCEPTED, section 6)."""
import dataclasses

from backtest.exits.entities import StopManagedPosition, Tranche, EXIT_REASON_TARGET
from backtest.exits.session import reconcile_split_for_open_position

from spec005.fixtures.pit_universe import insert_corporate_action, make_security
from data_foundation.model import repository as repo
from data_foundation.model.entities import PriceBar


class _UnboundedAccess:
    def __init__(self, conn):
        self.conn = conn

    def get_price_series_as_of(self, security_id, as_of):
        from data_foundation.pit import access as pit
        return pit.get_price_series_as_of(self.conn, security_id, as_of)

    def get_corporate_actions_as_of(self, security_id, as_of):
        from data_foundation.pit import access as pit
        return pit.get_corporate_actions_as_of(self.conn, security_id, as_of)


def _insert_flat_bars(conn, security_id, now, dates, price=100.0):
    repo.insert_price_bars(conn, [
        PriceBar(
            security_id=security_id, date=d, raw_open=price, raw_high=price + 1, raw_low=price - 1,
            raw_close=price, raw_volume=1000, source_provider="manual", ingestion_timestamp=now,
        )
        for d in dates
    ])


def _open_position(entry_date="2024-01-11", **overrides) -> StopManagedPosition:
    fields = dict(
        security_id="SEC_X", direction="LONG", entry_date=entry_date, signal_date="2024-01-10",
        entry_fill_price=100.0, k=2.0, r_multiple=2.0, fraction=0.5,
        active_stop=90.0, initial_risk=10.0, target_price=120.0,
    )
    fields.update(overrides)
    return StopManagedPosition(**fields)


def test_announcement_only_produces_zero_change(conn, now):
    """(a): available_at known, effective_date not yet reached -> not
    even known-for-adjustment yet -- nothing changes."""
    sec = make_security(conn, "spec005:SPLIT_A", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-20"])
    insert_corporate_action(
        conn, sec, "act_a", "SPLIT", effective_date="2024-02-01", value=2.0, now=now, available_at="2024-01-15",
    )
    pos = _open_position(security_id=sec)
    pit = _UnboundedAccess(conn)

    new_pos = reconcile_split_for_open_position(pit, pos, "2024-01-20")
    assert new_pos == pos


def test_late_known_split_still_open_position_catches_up_via_ratio(conn, now):
    """(b), the "still open, not yet fatally late" branch: a split
    effective 2024-01-15 becomes knowable only on 2024-01-25 (retroactive
    disclosure) -- once known, Pas 0 still correctly catches up via the
    ratio, for a position that never filled on the stale basis."""
    sec = make_security(conn, "spec005:SPLIT_B", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-25"])
    insert_corporate_action(
        conn, sec, "act_b", "SPLIT", effective_date="2024-01-15", value=2.0, now=now, available_at="2024-01-25",
    )
    pos = _open_position(security_id=sec)
    pit = _UnboundedAccess(conn)

    # Sessions before the split becomes knowable: no change (genuinely
    # not yet known -- not the same as "incomplete").
    unaffected = reconcile_split_for_open_position(pit, pos, "2024-01-20")
    assert unaffected == pos
    assert unaffected.split_reconciliation_incomplete is False

    # Once known (2024-01-25): caught up via the ratio, exactly like an
    # on-time reconciliation would have produced.
    reconciled = reconcile_split_for_open_position(pit, pos, "2024-01-25")
    assert reconciled.active_stop == 45.0  # 90 * 0.5
    assert reconciled.target_price == 60.0  # 120 * 0.5
    assert reconciled.initial_risk == 5.0  # 10 * 0.5
    assert reconciled.entry_fill_price == 50.0  # 100 * 0.5
    assert reconciled.remaining_quantity == 2.0  # 1.0 / 0.5
    assert reconciled.applied_factor == 0.5
    assert "act_b" in reconciled.processed_split_action_ids
    assert reconciled.split_reconciliation_incomplete is False


def test_closed_position_is_never_touched_no_retroactive_repair(conn, now):
    """A position already closed (a fill already simulated) is returned
    completely unchanged -- the structural guarantee behind "deciziile/
    fill-urile deja simulate NU se repară retroactiv"."""
    sec = make_security(conn, "spec005:SPLIT_C", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-20"])
    insert_corporate_action(conn, sec, "act_c", "SPLIT", effective_date="2024-01-15", value=2.0, now=now, available_at="2024-01-15")
    closed_tranche = Tranche(
        kind="REMAINDER", exit_reason="STOP", fraction_of_original=1.0,
        exit_date="2024-01-12", exit_fill_price=90.0, holding_days=1,
    )
    pos = _open_position(security_id=sec, closed=True, close_tranche=closed_tranche, remaining_quantity=0.0)
    pit = _UnboundedAccess(conn)

    new_pos = reconcile_split_for_open_position(pit, pos, "2024-01-20")
    assert new_pos == pos
    assert new_pos.close_tranche == closed_tranche


def test_same_day_no_evidence_marks_split_reconciliation_incomplete(conn, now):
    """Section 3/6's temporal-access rule, applied identically at Pas 0:
    a split effective THE SAME DAY as this session, with no explicit
    evidence, is neither applied nor ignored -- the session's own
    reconciliation is marked incomplete."""
    sec = make_security(conn, "spec005:SPLIT_D", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-20"])
    insert_corporate_action(conn, sec, "act_d", "SPLIT", effective_date="2024-01-20", value=2.0, now=now, available_at="2024-01-20")
    pos = _open_position(security_id=sec)
    pit = _UnboundedAccess(conn)

    new_pos = reconcile_split_for_open_position(pit, pos, "2024-01-20", same_day_evidence=frozenset())
    assert new_pos.split_reconciliation_incomplete is True
    assert new_pos.active_stop == pos.active_stop  # not applied on a guess
    assert "act_d" not in new_pos.processed_split_action_ids


def test_same_day_with_evidence_applies_normally(conn, now):
    sec = make_security(conn, "spec005:SPLIT_E", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-20"])
    insert_corporate_action(conn, sec, "act_e", "SPLIT", effective_date="2024-01-20", value=2.0, now=now, available_at="2024-01-20")
    pos = _open_position(security_id=sec)
    pit = _UnboundedAccess(conn)

    new_pos = reconcile_split_for_open_position(pit, pos, "2024-01-20", same_day_evidence=frozenset({"act_e"}))
    assert new_pos.split_reconciliation_incomplete is False
    assert new_pos.active_stop == 45.0
    assert "act_e" in new_pos.processed_split_action_ids


def test_idempotent_reconciliation_is_not_applied_twice(conn, now):
    sec = make_security(conn, "spec005:SPLIT_F", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-20", "2024-01-21"])
    insert_corporate_action(conn, sec, "act_f", "SPLIT", effective_date="2024-01-15", value=2.0, now=now, available_at="2024-01-15")
    pos = _open_position(security_id=sec)
    pit = _UnboundedAccess(conn)

    once = reconcile_split_for_open_position(pit, pos, "2024-01-20")
    twice = reconcile_split_for_open_position(pit, once, "2024-01-21")
    assert once == twice  # second pass, same day's known state -- no further change


def test_split_after_partial_profit_leaves_the_closed_tranche_intact_and_rescales_remainder(conn, now):
    """(c): the partial-profit tranche's own recorded economics (value,
    implicitly its own fraction/fill/date) are historical facts, fixed at
    their moment -- only the still-active remainder's quantity/levels
    rescale."""
    sec = make_security(conn, "spec005:SPLIT_G", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-20"])
    insert_corporate_action(conn, sec, "act_g", "SPLIT", effective_date="2024-01-15", value=2.0, now=now, available_at="2024-01-15")
    partial = Tranche(
        kind="PARTIAL_PROFIT", exit_reason=EXIT_REASON_TARGET, fraction_of_original=0.5,
        exit_date="2024-01-12", exit_fill_price=120.0, holding_days=1,
    )
    pos = _open_position(
        security_id=sec, target_consumed=True, partial_tranche=partial, remaining_quantity=0.5,
    )
    pit = _UnboundedAccess(conn)

    new_pos = reconcile_split_for_open_position(pit, pos, "2024-01-20")
    assert new_pos.partial_tranche == partial  # completely untouched
    assert new_pos.remaining_quantity == 1.0  # 0.5 / 0.5
    assert new_pos.active_stop == 45.0
    # target_price is rescaled too (section 6's formula conditions this
    # only on "partial_profit configured", not on consumption status) --
    # harmless, since Pas 3' never reads it again once target_consumed.
    assert new_pos.target_price == 60.0
