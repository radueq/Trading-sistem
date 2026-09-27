"""TEST 27 -- cost/return formulas for STOP_MANAGED_INVALIDATION
(docs/spec005_exit_amendment_v1.0.md, ACCEPTED, section 9)."""
import pytest

from backtest.exits.costs import aggregate_position_return, compute_w, open_remainder_net_return, tranche_net_return
from backtest.exits.entities import StopManagedPosition


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
