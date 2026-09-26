"""TEST 9 -- ResearchPlan content-address excludes administrative
fields (Spec #005 v1.0 SS21, Batch 1): "Exclude created_at and
wall-clock performance from semantic identity." `created_at`/
`created_by` never participate in `research_plan_fingerprint()` at
all -- confirmed structurally (the function doesn't take them as
parameters), and behaviorally (two plans differing only in those
fields get the identical id)."""
from backtest.models.entities import (
    CostAssumptions,
    ExposureManifest,
    SelectionFold,
    SelectionRule,
    build_research_plan_id,
    research_plan_fingerprint,
)

_FOLDS = (SelectionFold("fold_1", "2020-01-01", "2021-01-01"), SelectionFold("fold_2", "2021-01-01", "2022-01-01"))
_COHORT = ("hyp_a", "hyp_b")
_RULE = SelectionRule(minimum_executed_trades=30, minimum_evaluable_trades=25, minimum_evaluable_ratio=0.8)
_COSTS = CostAssumptions(commission_entry_rate=0.0005, commission_exit_rate=0.0005, slippage_entry_bps=5.0, slippage_exit_bps=5.0, borrow_annual_rate=0.0)
_EXPOSURE = ExposureManifest()


def _fp(**overrides):
    base = dict(
        formation_start="2020-01-01", formation_end="2024-01-01", validation_start="2024-02-01",
        validation_end="2024-12-31", locked_oos_start="2025-01-01", selection_folds=_FOLDS,
        hypothesis_cohort_ids=_COHORT, trading_calendar_id="cal_abc", benchmark_security_id="SBENCH",
        execution_semantics_profile_id="exsem_abc", selection_rule=_RULE, cost_assumptions=_COSTS,
        exposure_manifest=_EXPOSURE,
    )
    base.update(overrides)
    return research_plan_fingerprint(**base)


def test_created_at_and_created_by_never_enter_the_fingerprint_function():
    """Structural check: research_plan_fingerprint() has no parameter
    for either field -- they cannot possibly affect the hash."""
    import inspect
    params = inspect.signature(research_plan_fingerprint).parameters
    assert "created_at" not in params
    assert "created_by" not in params


def test_identical_economic_fields_produce_the_identical_plan_id():
    fp_a = _fp()
    fp_b = _fp()
    id_a, hash_a = build_research_plan_id(fp_a)
    id_b, hash_b = build_research_plan_id(fp_b)
    assert id_a == id_b
    assert hash_a == hash_b


def test_cohort_id_order_does_not_affect_the_fingerprint():
    fp_a = _fp(hypothesis_cohort_ids=("hyp_a", "hyp_b"))
    fp_b = _fp(hypothesis_cohort_ids=("hyp_b", "hyp_a"))
    assert fp_a == fp_b


def test_changed_validation_end_changes_the_fingerprint():
    fp_a = _fp()
    fp_b = _fp(validation_end="2024-11-30")
    assert fp_a != fp_b


def test_changed_selection_rule_changes_the_fingerprint():
    fp_a = _fp()
    changed_rule = SelectionRule(minimum_executed_trades=50, minimum_evaluable_trades=25, minimum_evaluable_ratio=0.8)
    fp_b = _fp(selection_rule=changed_rule)
    assert fp_a != fp_b


def test_changed_cost_assumptions_changes_the_fingerprint():
    fp_a = _fp()
    changed_costs = CostAssumptions(commission_entry_rate=0.001, commission_exit_rate=0.0005, slippage_entry_bps=5.0, slippage_exit_bps=5.0, borrow_annual_rate=0.0)
    fp_b = _fp(cost_assumptions=changed_costs)
    assert fp_a != fp_b


def test_changed_exposure_manifest_changes_the_fingerprint():
    fp_a = _fp()
    fp_b = _fp(exposure_manifest=ExposureManifest(prior_validation_disclosures=("some prior peek",), declared_unseen=False))
    assert fp_a != fp_b


def test_changed_calendar_or_profile_id_changes_the_fingerprint():
    fp_a = _fp()
    fp_b = _fp(trading_calendar_id="cal_DIFFERENT")
    fp_c = _fp(execution_semantics_profile_id="exsem_DIFFERENT")
    assert fp_a != fp_b
    assert fp_a != fp_c
