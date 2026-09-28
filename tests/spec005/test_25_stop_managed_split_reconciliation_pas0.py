"""TEST 25 -- Pas 0 split reconciliation for an already-open
STOP_MANAGED_INVALIDATION position (docs/spec005_exit_amendment_v1.0.md,
ACCEPTED, section 6)."""
import pytest

from backtest.exits.costs import net_return_for_tranche
from backtest.exits.entities import StopManagedPosition, Tranche, EXIT_REASON_STOP, EXIT_REASON_TARGET
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


def test_split_effective_before_entry_is_never_pas0s_concern(conn, now):
    """GPT review round 3, finding #1: a split effective BEFORE the
    position's own entry_date was already fully reflected in the
    position's opening basis (section 5) -- Pas 0 must never re-encounter
    it as "new" on some later session and wrongly mark the position
    incomplete. The position must remain fully evaluable."""
    sec = make_security(conn, "spec005:SPLIT_PREENTRY", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-15"])
    insert_corporate_action(
        conn, sec, "act_preentry", "SPLIT", effective_date="2024-01-09", value=2.0, now=now, available_at="2024-01-09",
    )
    pos = _open_position(security_id=sec, entry_date="2024-01-11")
    pit = _UnboundedAccess(conn)

    new_pos = reconcile_split_for_open_position(pit, pos, "2024-01-15")
    assert new_pos == pos  # completely untouched
    assert new_pos.split_reconciliation_incomplete is False
    assert "act_preentry" not in new_pos.processed_split_action_ids


def test_split_effective_exactly_on_entry_day_is_never_pas0s_concern(conn, now):
    """Same as above, for a split effective ON the entry day itself
    (section 5: "Pozițiile nou deschise azi pornesc DIRECT pe baza
    intrării... post orice split cunoscut") -- also never Pas 0's concern."""
    sec = make_security(conn, "spec005:SPLIT_ENTRYDAY", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-15"])
    insert_corporate_action(
        conn, sec, "act_entryday", "SPLIT", effective_date="2024-01-11", value=2.0, now=now, available_at="2024-01-11",
    )
    pos = _open_position(security_id=sec, entry_date="2024-01-11")
    pit = _UnboundedAccess(conn)

    new_pos = reconcile_split_for_open_position(pit, pos, "2024-01-15")
    assert new_pos == pos
    assert new_pos.split_reconciliation_incomplete is False
    assert "act_entryday" not in new_pos.processed_split_action_ids


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


def test_late_known_split_reconciled_but_permanently_incomplete(conn, now):
    """(b), corrected per GPT review round 2 finding #2: a split effective
    2024-01-15 becomes knowable only on 2024-01-25 (retroactive
    disclosure). Once known, Pas 0 still catches up the GOING-FORWARD
    state via the ratio -- but the position stays PERMANENTLY
    `split_reconciliation_incomplete`, because sessions between the
    split's own effective_date and the day it was actually reconciled
    were necessarily simulated on the stale basis. The position still
    being open proves nothing about whether those intervening sessions'
    stop/target checks were correct."""
    sec = make_security(conn, "spec005:SPLIT_B", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-25"])
    insert_corporate_action(
        # available_at (2024-01-24) is itself STRICTLY BEFORE the
        # reconciliation session (2024-01-25) -- auto-authorized at open,
        # no same-day evidence needed, isolating the "late relative to
        # effective_date" behavior under test from fix #1's separate
        # same-day-evidence rule.
        conn, sec, "act_b", "SPLIT", effective_date="2024-01-15", value=2.0, now=now, available_at="2024-01-24",
    )
    pos = _open_position(security_id=sec)
    pit = _UnboundedAccess(conn)

    # Sessions before the split becomes knowable: no change (genuinely
    # not yet known -- not the same as "incomplete").
    unaffected = reconcile_split_for_open_position(pit, pos, "2024-01-20")
    assert unaffected == pos
    assert unaffected.split_reconciliation_incomplete is False

    # Once known (2024-01-25): caught up via the ratio for future
    # sessions, but PERMANENTLY marked incomplete -- effective_date
    # (01-15) is strictly before the reconciliation session (01-25).
    reconciled = reconcile_split_for_open_position(pit, pos, "2024-01-25")
    assert reconciled.active_stop == 45.0  # 90 * 0.5 -- still correctly caught up
    assert reconciled.target_price == 60.0
    assert reconciled.initial_risk == 5.0
    assert reconciled.entry_fill_price == 50.0
    assert reconciled.remaining_quantity == 2.0
    assert reconciled.applied_factor == 0.5
    assert "act_b" in reconciled.processed_split_action_ids
    assert reconciled.split_reconciliation_incomplete is True


def test_on_time_reconciliation_same_session_as_effective_date_is_not_flagged(conn, now):
    """Contrast case: when reconciliation happens on the SAME session as
    the split's own effective_date (its rightful session), there is no
    gap -- not flagged incomplete."""
    sec = make_security(conn, "spec005:SPLIT_ONTIME", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-20"])
    insert_corporate_action(conn, sec, "act_ontime", "SPLIT", effective_date="2024-01-20", value=2.0, now=now, available_at="2024-01-20")
    pos = _open_position(security_id=sec)
    pit = _UnboundedAccess(conn)

    new_pos = reconcile_split_for_open_position(pit, pos, "2024-01-20", same_day_evidence=frozenset({"act_ontime"}))
    assert new_pos.split_reconciliation_incomplete is False
    assert new_pos.active_stop == 45.0


def test_closed_position_is_never_touched_no_retroactive_repair(conn, now):
    """A position already closed (a fill already simulated) is returned
    completely unchanged -- the structural guarantee behind "deciziile/
    fill-urile deja simulate NU se repară retroactiv"."""
    sec = make_security(conn, "spec005:SPLIT_C", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-20"])
    insert_corporate_action(conn, sec, "act_c", "SPLIT", effective_date="2024-01-15", value=2.0, now=now, available_at="2024-01-15")
    closed_tranche = Tranche(
        kind="REMAINDER", exit_reason="STOP", fraction_of_original=1.0,
        exit_date="2024-01-12", exit_fill_price=90.0, holding_days=1, entry_fill_price_reference=100.0,
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


def test_two_same_day_actions_only_the_authorized_one_enters_the_factor(conn, now):
    """GPT review round 2, finding #4: two DIFFERENT splits both become
    known+effective the SAME session. One has same-day evidence
    (authorized), the other does not (blocked). The applied factor must
    reflect ONLY the authorized action -- #001's own PIT facade would
    otherwise silently combine BOTH (it has no notion of this position's
    own same-day-authorization distinction)."""
    sec = make_security(conn, "spec005:SPLIT_TWO", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-20"])
    insert_corporate_action(conn, sec, "act_x", "SPLIT", effective_date="2024-01-20", value=2.0, now=now, available_at="2024-01-20")
    insert_corporate_action(conn, sec, "act_y", "SPLIT", effective_date="2024-01-20", value=3.0, now=now, available_at="2024-01-20")
    pos = _open_position(security_id=sec)
    pit = _UnboundedAccess(conn)

    new_pos = reconcile_split_for_open_position(pit, pos, "2024-01-20", same_day_evidence=frozenset({"act_x"}))

    # ONLY act_x's factor (1/2.0 = 0.5) -- NOT the combined (1/2.0)*(1/3.0)
    # a naive #001-facade-driven computation would have produced.
    assert new_pos.applied_factor == pytest.approx(0.5)
    assert new_pos.active_stop == pytest.approx(45.0)
    assert "act_x" in new_pos.processed_split_action_ids
    assert "act_y" not in new_pos.processed_split_action_ids
    assert new_pos.split_reconciliation_incomplete is True  # act_y still blocked


def test_split_after_partial_profit_preserves_the_closed_tranches_own_economics(conn, now):
    """(c) + GPT review round 2, finding #5: the partial-profit tranche's
    own recorded fill/date are historical facts, fixed at their moment --
    only the still-active remainder's quantity/levels rescale. Verifies
    the AGGREGATE RETURN and commission term before and after the split,
    not just object equality: combining the tranche's OWN entry_fill_
    price_reference (100, pre-split) with its OWN historical fill (120)
    must reproduce the correct +20% (minus costs) -- NOT +140%, which is
    what naively combining the position's POST-split entry_fill_price
    (50) with the pre-split 120 fill would wrongly produce."""
    sec = make_security(conn, "spec005:SPLIT_G", now)
    _insert_flat_bars(conn, sec, now, ["2024-01-11", "2024-01-20"])
    insert_corporate_action(conn, sec, "act_g", "SPLIT", effective_date="2024-01-20", value=2.0, now=now, available_at="2024-01-20")
    partial = Tranche(
        kind="PARTIAL_PROFIT", exit_reason=EXIT_REASON_TARGET, fraction_of_original=0.5,
        exit_date="2024-01-12", exit_fill_price=120.0, holding_days=1, entry_fill_price_reference=100.0,
    )
    pos = _open_position(
        security_id=sec, target_consumed=True, partial_tranche=partial, remaining_quantity=0.5,
    )
    pit = _UnboundedAccess(conn)

    # Return computed from the tranche's OWN reference, BEFORE the split
    # reconciliation runs at all -- the baseline correct answer.
    return_before_split = net_return_for_tranche(
        partial, "LONG", commission_entry_rate=0.0, commission_exit_rate=0.0, borrow_annual_rate=0.0,
    )
    assert return_before_split == pytest.approx(0.20)  # (120-100)/100

    new_pos = reconcile_split_for_open_position(pit, pos, "2024-01-20", same_day_evidence=frozenset({"act_g"}))

    # The closed tranche object itself, and its own economics, are
    # completely untouched by the split -- same object, same reference.
    assert new_pos.partial_tranche == partial
    assert new_pos.partial_tranche.entry_fill_price_reference == 100.0
    assert new_pos.partial_tranche.exit_fill_price == 120.0

    return_after_split = net_return_for_tranche(
        new_pos.partial_tranche, "LONG", commission_entry_rate=0.0, commission_exit_rate=0.0, borrow_annual_rate=0.0,
    )
    assert return_after_split == pytest.approx(0.20)  # UNCHANGED -- never +140%

    # With commissions, also unaffected by the split (rate-based, not
    # price-level-based).
    return_with_costs_before = net_return_for_tranche(
        partial, "LONG", commission_entry_rate=0.001, commission_exit_rate=0.002, borrow_annual_rate=0.0,
    )
    return_with_costs_after = net_return_for_tranche(
        new_pos.partial_tranche, "LONG", commission_entry_rate=0.001, commission_exit_rate=0.002, borrow_annual_rate=0.0,
    )
    assert return_with_costs_before == pytest.approx(return_with_costs_after)

    # The still-active remainder DOES rescale.
    assert new_pos.remaining_quantity == 1.0  # 0.5 / 0.5
    assert new_pos.active_stop == 45.0
    assert new_pos.target_price == 60.0
