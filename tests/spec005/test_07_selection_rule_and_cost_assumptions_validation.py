"""TEST 7 -- SelectionRule and CostAssumptions validation (Spec #005
v1.0 SS13/SS18, Batch 1). V1's ranking metric/operator/tie-break/borrow
convention are fixed constants, never tunable knobs; cost rates must be
finite and nonnegative, and slippage must never be large enough to
flip a fill's sign."""
import dataclasses

from backtest.models.entities import CostAssumptions, SelectionRule, validate_cost_assumptions, validate_selection_rule


def _valid_rule(**overrides) -> SelectionRule:
    return dataclasses.replace(
        SelectionRule(minimum_executed_trades=30, minimum_evaluable_trades=25, minimum_evaluable_ratio=0.8),
        **overrides,
    )


def test_valid_selection_rule_passes():
    ok, errors = validate_selection_rule(_valid_rule())
    assert ok, errors


def test_non_positive_minimum_executed_trades_is_rejected():
    ok, errors = validate_selection_rule(_valid_rule(minimum_executed_trades=0))
    assert not ok
    assert any("minimum_executed_trades" in e for e in errors)


def test_ratio_out_of_range_is_rejected():
    ok, errors = validate_selection_rule(_valid_rule(minimum_evaluable_ratio=1.5))
    assert not ok
    assert any("minimum_evaluable_ratio" in e for e in errors)


def test_ratio_of_exactly_one_is_allowed():
    ok, errors = validate_selection_rule(_valid_rule(minimum_evaluable_ratio=1.0))
    assert ok, errors


def test_non_median_ranking_metric_is_rejected():
    ok, errors = validate_selection_rule(_valid_rule(ranking_metric="SHARPE_LIKE"))
    assert not ok
    assert any("ranking_metric" in e for e in errors)


def test_nonzero_minimum_selection_metric_is_rejected():
    ok, errors = validate_selection_rule(_valid_rule(minimum_selection_metric=0.01))
    assert not ok
    assert any("minimum_selection_metric" in e for e in errors)


def test_non_strict_threshold_operator_is_rejected():
    ok, errors = validate_selection_rule(_valid_rule(threshold_operator="GREATER_OR_EQUAL"))
    assert not ok


def test_non_lexicographic_tie_break_is_rejected():
    ok, errors = validate_selection_rule(_valid_rule(tie_break="HIGHEST_SHARPE"))
    assert not ok


def _valid_costs(**overrides) -> CostAssumptions:
    return dataclasses.replace(
        CostAssumptions(
            commission_entry_rate=0.0005, commission_exit_rate=0.0005,
            slippage_entry_bps=5.0, slippage_exit_bps=5.0, borrow_annual_rate=0.0,
        ),
        **overrides,
    )


def test_valid_cost_assumptions_pass():
    ok, errors = validate_cost_assumptions(_valid_costs())
    assert ok, errors


def test_negative_commission_rate_is_rejected():
    ok, errors = validate_cost_assumptions(_valid_costs(commission_entry_rate=-0.001))
    assert not ok
    assert any("commission_entry_rate" in e for e in errors)


def test_nan_slippage_is_rejected():
    ok, errors = validate_cost_assumptions(_valid_costs(slippage_entry_bps=float("nan")))
    assert not ok


def test_infinite_borrow_rate_is_rejected():
    ok, errors = validate_cost_assumptions(_valid_costs(borrow_annual_rate=float("inf")))
    assert not ok


def test_slippage_at_or_above_100_percent_is_rejected():
    """A fill must stay positive (SS13) -- 10000 bps = 100% adverse
    slippage would drive F_e/F_x to zero or negative."""
    ok, errors = validate_cost_assumptions(_valid_costs(slippage_entry_bps=10000.0))
    assert not ok
    assert any("slippage_entry_bps" in e for e in errors)


def test_wrong_borrow_accrual_convention_is_rejected():
    ok, errors = validate_cost_assumptions(_valid_costs(borrow_accrual_convention="TRADING_DAYS_252"))
    assert not ok
    assert any("borrow_accrual_convention" in e for e in errors)
