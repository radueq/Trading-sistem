"""TEST 21 -- STOP_MANAGED_INVALIDATION initial protection formulas
(docs/spec005_exit_amendment_v1.0.md, ACCEPTED, section 3): S_initial,
risc_inițial, țintă for LONG and SHORT, and INVALID_PROTECTIVE_LEVELS
rejection (section 2, rule #4) when the computed levels are economically
impossible."""
from backtest.exits.entities import ENTRY_INVALID_PROTECTIVE_LEVELS
from backtest.exits.protection import compute_initial_protection


def test_long_control_variant_no_target():
    stop, risk, target, rejection = compute_initial_protection("LONG", 100.0, atr_reexpressed=5.0, k=2.0, r_multiple=None)
    assert rejection is None
    assert stop == 100.0 - 2.0 * 5.0 == 90.0
    assert risk == 100.0 - 90.0 == 10.0
    assert target is None


def test_long_partial_profit_variant():
    stop, risk, target, rejection = compute_initial_protection("LONG", 100.0, atr_reexpressed=5.0, k=2.0, r_multiple=2.0)
    assert rejection is None
    assert stop == 90.0
    assert risk == 10.0
    assert target == 100.0 + 2.0 * 10.0 == 120.0


def test_short_control_variant_no_target():
    stop, risk, target, rejection = compute_initial_protection("SHORT", 100.0, atr_reexpressed=5.0, k=2.0, r_multiple=None)
    assert rejection is None
    assert stop == 100.0 + 2.0 * 5.0 == 110.0
    assert risk == 110.0 - 100.0 == 10.0
    assert target is None


def test_short_partial_profit_variant():
    stop, risk, target, rejection = compute_initial_protection("SHORT", 100.0, atr_reexpressed=5.0, k=2.0, r_multiple=2.0)
    assert rejection is None
    assert stop == 110.0
    assert risk == 10.0
    assert target == 100.0 - 2.0 * 10.0 == 80.0


def test_long_stop_above_entry_is_rejected():
    """A pathological (negative or absurd) ATR value driving the stop
    above the entry price is economically impossible for a LONG."""
    stop, risk, target, rejection = compute_initial_protection("LONG", 100.0, atr_reexpressed=-5.0, k=2.0, r_multiple=None)
    assert rejection == ENTRY_INVALID_PROTECTIVE_LEVELS
    assert stop is None and risk is None and target is None


def test_short_stop_below_entry_is_rejected():
    stop, risk, target, rejection = compute_initial_protection("SHORT", 100.0, atr_reexpressed=-5.0, k=2.0, r_multiple=None)
    assert rejection == ENTRY_INVALID_PROTECTIVE_LEVELS


def test_long_target_at_or_below_entry_is_rejected():
    stop, risk, target, rejection = compute_initial_protection("LONG", 100.0, atr_reexpressed=5.0, k=2.0, r_multiple=-1.0)
    assert rejection == ENTRY_INVALID_PROTECTIVE_LEVELS


def test_invalid_direction_raises():
    import pytest
    with pytest.raises(ValueError):
        compute_initial_protection("SIDEWAYS", 100.0, atr_reexpressed=5.0, k=2.0, r_multiple=None)
