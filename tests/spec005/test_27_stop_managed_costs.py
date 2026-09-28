"""TEST 27 -- cost/return formulas for STOP_MANAGED_INVALIDATION
(docs/spec005_exit_amendment_v1.0.md, ACCEPTED, section 9)."""
import pytest

from backtest.exits.costs import (
    aggregate_position_return,
    apply_exit_slippage,
    compute_w,
    net_return_for_tranche_with_slippage,
    open_remainder_net_return,
    slippage_rate_from_bps,
    tranche_net_return,
)
from backtest.exits.entities import EXIT_REASON_INVALIDATION, EXIT_REASON_STOP, EXIT_REASON_TARGET, StopManagedPosition, Tranche


def test_long_closed_tranche_no_costs():
    r = tranche_net_return("LONG", 100.0, 110.0, 0.0, 0.0, 0.0, holding_days=10)
    assert r == pytest.approx(0.10)


def test_short_closed_tranche_profits_on_price_drop():
    r = tranche_net_return("SHORT", 100.0, 90.0, 0.0, 0.0, 0.0, holding_days=10)
    assert r == pytest.approx(0.10)


def test_long_closed_tranche_with_commissions_and_borrow():
    r = tranche_net_return("LONG", 100.0, 110.0, commission_entry_rate=0.001, commission_exit_rate=0.002,
                            borrow_annual_rate=0.0365, holding_days=100)
    # 0.10 - 0.001 - 0.002*(110/100) - (0.0365*100/365) = 0.10 - 0.001 - 0.0022 - 0.01
    assert r == pytest.approx(0.0868)


def test_open_remainder_net_return_has_no_exit_cost():
    r = open_remainder_net_return("LONG", 100.0, 105.0, commission_entry_rate=0.001, borrow_annual_rate=0.0, holding_days=30)
    assert r == pytest.approx(0.049)


def test_aggregate_weighted_when_partial_executed():
    partial = tranche_net_return("LONG", 100.0, 110.0, 0.001, 0.002, 0.0365, holding_days=100)
    rest = open_remainder_net_return("LONG", 100.0, 105.0, 0.001, 0.0, holding_days=30)
    result = aggregate_position_return(0.5, partial, rest)
    assert result == pytest.approx(0.5 * partial + 0.5 * rest)
    assert result == pytest.approx(0.0679)


def test_aggregate_ignores_partial_return_when_w_is_zero():
    result = aggregate_position_return(0.0, partial_return=None, rest_return=0.03)
    assert result == 0.03


def test_aggregate_raises_if_w_nonzero_and_partial_return_missing():
    with pytest.raises(ValueError):
        aggregate_position_return(0.5, partial_return=None, rest_return=0.03)


def _base_position(**overrides) -> StopManagedPosition:
    fields = dict(
        security_id="SEC_X", direction="LONG", entry_date="2024-01-11", signal_date="2024-01-10",
        entry_fill_price=100.0, k=2.0, r_multiple=2.0, fraction=0.5,
        active_stop=90.0, initial_risk=10.0, target_price=120.0,
    )
    fields.update(overrides)
    return StopManagedPosition(**fields)


def test_compute_w_is_zero_before_target_ever_triggers():
    pos = _base_position(target_consumed=False)
    assert compute_w(pos) == 0.0


def test_compute_w_is_the_configured_fraction_once_target_triggers():
    pos = _base_position(target_consumed=True)
    assert compute_w(pos) == 0.5


def test_compute_w_is_zero_for_control_variant():
    pos = _base_position(fraction=None, target_price=None, r_multiple=None)
    assert compute_w(pos) == 0.0


# --------------------------------------------------------------------------
# Amendment section 9 (base spec SS13, restated there in full) -- the
# exit-side slippage formula: F_x = nivel_fill for the partial-profit
# tranche ("fara slippage advers", section 4), F_x = nivel_fill*(1-d*s_x)
# for any tranche closed via stop or trend invalidation.
# --------------------------------------------------------------------------

def test_slippage_rate_from_bps_is_a_plain_division():
    assert slippage_rate_from_bps(100.0) == pytest.approx(0.01)
    assert slippage_rate_from_bps(0.0) == 0.0


def test_target_tranche_never_receives_adverse_slippage():
    assert apply_exit_slippage("LONG", 120.0, EXIT_REASON_TARGET, slippage_exit_rate=0.05) == 120.0
    assert apply_exit_slippage("SHORT", 80.0, EXIT_REASON_TARGET, slippage_exit_rate=0.05) == 80.0


def test_long_stop_slippage_makes_the_fill_worse_lower():
    # d=+1: F_x = 95*(1 - 1*0.01) = 94.05 -- a worse (lower) sale price.
    assert apply_exit_slippage("LONG", 95.0, EXIT_REASON_STOP, slippage_exit_rate=0.01) == pytest.approx(94.05)


def test_short_stop_slippage_makes_the_fill_worse_higher():
    # d=-1: F_x = 105*(1 - (-1)*0.01) = 106.05 -- a worse (higher) buy-back price.
    assert apply_exit_slippage("SHORT", 105.0, EXIT_REASON_STOP, slippage_exit_rate=0.01) == pytest.approx(106.05)


def test_invalidation_tranche_gets_the_same_adverse_slippage_as_a_stop():
    assert apply_exit_slippage("LONG", 95.0, EXIT_REASON_INVALIDATION, slippage_exit_rate=0.01) == pytest.approx(94.05)


def test_net_return_for_tranche_with_slippage_applies_the_worse_fill_before_the_return_formula():
    tranche = Tranche(
        kind="REMAINDER", exit_reason=EXIT_REASON_STOP, fraction_of_original=1.0,
        exit_date="2024-02-01", exit_fill_price=95.0, holding_days=10, entry_fill_price_reference=100.0,
    )
    # F_x = 95*(1-0.01) = 94.05 -> d*(94.05-100)/100 = -0.0595, no other costs.
    r = net_return_for_tranche_with_slippage(
        tranche, "LONG", commission_entry_rate=0.0, commission_exit_rate=0.0, borrow_annual_rate=0.0,
        slippage_exit_rate=0.01,
    )
    assert r == pytest.approx(-0.0595)


def test_net_return_for_tranche_with_slippage_leaves_a_target_tranche_unslipped():
    tranche = Tranche(
        kind="PARTIAL_PROFIT", exit_reason=EXIT_REASON_TARGET, fraction_of_original=0.5,
        exit_date="2024-02-01", exit_fill_price=120.0, holding_days=10, entry_fill_price_reference=100.0,
    )
    r = net_return_for_tranche_with_slippage(
        tranche, "LONG", commission_entry_rate=0.0, commission_exit_rate=0.0, borrow_annual_rate=0.0,
        slippage_exit_rate=0.01,
    )
    assert r == pytest.approx(0.20)
