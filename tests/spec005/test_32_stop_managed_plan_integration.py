"""TEST 32 -- the ResearchPlan acceptance gate for STOP_MANAGED_
INVALIDATION's mandatory identity/selection-metric requirements (docs/
spec005_exit_amendment_v1.0.md, ACCEPTED, sections 7 and 11; GPT review
round 3, finding #3): `accept_research_plan()` resolves the cohort from a
REAL `HypothesisRegistry`, never a caller-asserted boolean, and verifies
a REAL `StopManagedExecutionSemanticsProfile` object, never a bare id."""
import dataclasses

import pytest

from hypothesis.models.entities import (
    Direction, EntryDefinition, ExitFamily, ExitHypothesis, HorizonCandidateSet, HypothesisComplexitySnapshot,
    HypothesisProvenance, HypothesisResearchMode, HypothesisStatus, InvalidationCondition, LaneStateCondition,
    ParameterSource, StopLossRule, StrategyHypothesis,
)
from hypothesis.registry.hypotheses import HypothesisRegistry, build_hypothesis_id, hypothesis_fingerprint, materialize_variants

from backtest.exits.entities import build_stop_managed_execution_semantics_profile_v1
from backtest.exits.plan_integration import accept_research_plan
from backtest.models.entities import (
    RANKING_METRIC_STOP_MANAGED_V1,
    RANKING_METRIC_V1,
    SelectionRule,
    build_research_plan_id,
    research_plan_fingerprint,
    validate_selection_rule,
    verify_research_plan_identity,
)

from spec005.fixtures.pit_universe import make_security  # noqa: F401  (keeps DB fixtures wired if ever needed)

_EVIDENCE = dict(
    evaluation_run_id="run_x", evaluation_engine_version="v1.0.0", evaluation_config_version="cfg_eval",
    signature_id="SIG_X", signature_set_id="sigset_x", discovery_engine_version="v1.0.0",
    discovery_config_version="cfg_disc", timeframe="1D",
)


def _build_registered_hypothesis(registry: HypothesisRegistry, stop_managed_exit: "ExitHypothesis | None" = None) -> str:
    """Registers a fully self-consistent, PREREGISTERED StrategyHypothesis
    (one TIME_EXIT variant, plus the given STOP_MANAGED_INVALIDATION exit
    if supplied) directly into `registry` -- mirrors tests/spec004/
    conftest.py's own `build_preregistered_hypothesis_for_test()` pattern
    (bypassing the full preregistration gate on purpose; this test
    exercises accept_research_plan(), not #004's own gate)."""
    from hypothesis.models.entities import EvidenceProvenance
    entry = EntryDefinition(core_conditions=(LaneStateCondition("volatility", "COMPRESSION"),))
    horizons = HorizonCandidateSet(unit="BARS", values=(3,), selection_basis="x", parameter_source=ParameterSource.PRE_SPECIFIED.value)
    ev = EvidenceProvenance(**_EVIDENCE)
    fp = hypothesis_fingerprint("SIG_X", Direction.LONG.value, entry, "NEXT_BAR_OPEN", horizons, ev, "cfg_hyp_x")
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, "cfg_hyp_x")
    prov = HypothesisProvenance("HUMAN:radu", None, None, "radu", "t")
    hyp = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.PREREGISTERED.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id="SIG_X",
        signature_set_id="sigset_x", direction=Direction.LONG.value, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizons,
        variant_ids=(), evidence_provenance=ev, hypothesis_provenance=prov, constraints=comp,
        created_at="t", created_by="radu", strategy_config_version="cfg_hyp_x",
    )
    extra_exits = (stop_managed_exit,) if stop_managed_exit is not None else ()
    variants = materialize_variants(hyp, signal_invalidation_exits=extra_exits, created_at="t")
    hyp = dataclasses.replace(hyp, variant_ids=tuple(v.strategy_variant_id for v in variants))
    registry._force_register(hyp)
    for v in variants:
        registry.register_variant(v)
    return hyp.hypothesis_id


def _stop_managed_exit() -> ExitHypothesis:
    return ExitHypothesis(
        exit_family=ExitFamily.STOP_MANAGED_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=(InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),),
        stop_loss=StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=2.0),
    )


def _build_plan(hypothesis_cohort_ids, ranking_metric, stop_managed_profile_id=None):
    rule = SelectionRule(
        minimum_executed_trades=1, minimum_evaluable_trades=1, minimum_evaluable_ratio=0.5,
        ranking_metric=ranking_metric,
    )
    from backtest.models.entities import CostAssumptions, ExposureManifest, SelectionFold, build_execution_semantics_profile_v1
    profile = build_execution_semantics_profile_v1()
    costs = CostAssumptions(commission_entry_rate=0.0005, commission_exit_rate=0.0005, slippage_entry_bps=5.0, slippage_exit_bps=5.0, borrow_annual_rate=0.0)
    exposure = ExposureManifest(declared_unseen=True)
    fields = dict(
        formation_start="2024-01-01", formation_end="2024-01-31", validation_start="2024-02-01",
        validation_end="2024-02-29", locked_oos_start="2024-03-01",
        selection_folds=(SelectionFold("fold_1", "2024-01-01", "2024-01-31"),),
        hypothesis_cohort_ids=tuple(hypothesis_cohort_ids), trading_calendar_id="cal_x",
        benchmark_security_id="SBENCH", execution_semantics_profile_id=profile.profile_id,
        selection_rule=rule, cost_assumptions=costs, exposure_manifest=exposure,
        stop_managed_execution_semantics_profile_id=stop_managed_profile_id,
    )
    fp = research_plan_fingerprint(**fields)
    plan_id, plan_hash = build_research_plan_id(fp)
    from backtest.models.entities import ResearchPlan
    return ResearchPlan(research_plan_id=plan_id, plan_hash=plan_hash, created_at="t", created_by="radu", **fields)


def test_old_family_only_cohort_with_old_metric_is_accepted():
    registry = HypothesisRegistry()
    hid = _build_registered_hypothesis(registry)  # TIME_EXIT only
    plan = _build_plan([hid], RANKING_METRIC_V1)
    ok, errors = accept_research_plan(plan, registry)
    assert ok, errors


def test_old_family_only_cohort_with_new_metric_is_rejected_symmetric_enforcement():
    """GPT review round 3, finding #3: the old metric is not merely
    ALLOWED for an old-family-only cohort -- it is REQUIRED. Opting into
    the new metric without any STOP_MANAGED_INVALIDATION variant present
    is rejected."""
    registry = HypothesisRegistry()
    hid = _build_registered_hypothesis(registry)
    plan = _build_plan([hid], RANKING_METRIC_STOP_MANAGED_V1)
    ok, errors = accept_research_plan(plan, registry)
    assert not ok
    assert any("ranking_metric" in e for e in errors)


def test_stop_managed_cohort_is_determined_from_the_real_registry_not_a_boolean():
    """The cohort's family membership is resolved from `registry` itself
    -- a plan whose cohort ACTUALLY includes a STOP_MANAGED_INVALIDATION
    variant is correctly detected without any caller-supplied flag."""
    registry = HypothesisRegistry()
    hid = _build_registered_hypothesis(registry, stop_managed_exit=_stop_managed_exit())
    profile = build_stop_managed_execution_semantics_profile_v1()
    plan = _build_plan([hid], RANKING_METRIC_STOP_MANAGED_V1, stop_managed_profile_id=profile.profile_id)
    ok, errors = accept_research_plan(plan, registry, stop_managed_profile=profile)
    assert ok, errors


def test_stop_managed_cohort_with_old_metric_is_rejected():
    registry = HypothesisRegistry()
    hid = _build_registered_hypothesis(registry, stop_managed_exit=_stop_managed_exit())
    profile = build_stop_managed_execution_semantics_profile_v1()
    plan = _build_plan([hid], RANKING_METRIC_V1, stop_managed_profile_id=profile.profile_id)
    ok, errors = accept_research_plan(plan, registry, stop_managed_profile=profile)
    assert not ok
    assert any("ranking_metric" in e for e in errors)


def test_stop_managed_cohort_with_unverified_profile_id_is_rejected():
    """A bare, non-None profile id with NO real profile object supplied
    to the gate is rejected -- never accepted on faith."""
    registry = HypothesisRegistry()
    hid = _build_registered_hypothesis(registry, stop_managed_exit=_stop_managed_exit())
    plan = _build_plan([hid], RANKING_METRIC_STOP_MANAGED_V1, stop_managed_profile_id="smxp_totally_made_up")
    ok, errors = accept_research_plan(plan, registry, stop_managed_profile=None)
    assert not ok
    assert any("stop_managed_execution_semantics_profile_id" in e for e in errors)


def test_stop_managed_cohort_with_mismatched_profile_is_rejected():
    """A real, valid profile object is supplied, but the plan's own id
    field points to a DIFFERENT id -- still rejected."""
    registry = HypothesisRegistry()
    hid = _build_registered_hypothesis(registry, stop_managed_exit=_stop_managed_exit())
    profile = build_stop_managed_execution_semantics_profile_v1()
    plan = _build_plan([hid], RANKING_METRIC_STOP_MANAGED_V1, stop_managed_profile_id="smxp_totally_made_up")
    ok, errors = accept_research_plan(plan, registry, stop_managed_profile=profile)
    assert not ok
    assert any("stop_managed_execution_semantics_profile_id" in e for e in errors)


def test_stop_managed_cohort_missing_profile_id_entirely_is_rejected():
    registry = HypothesisRegistry()
    hid = _build_registered_hypothesis(registry, stop_managed_exit=_stop_managed_exit())
    plan = _build_plan([hid], RANKING_METRIC_STOP_MANAGED_V1, stop_managed_profile_id=None)
    ok, errors = accept_research_plan(plan, registry)
    assert not ok
    assert any("stop_managed_execution_semantics_profile_id" in e for e in errors)


def test_unresolvable_cohort_id_is_rejected():
    registry = HypothesisRegistry()
    plan = _build_plan(["hyp_does_not_exist"], RANKING_METRIC_V1)
    ok, errors = accept_research_plan(plan, registry)
    assert not ok
    assert any("hyp_does_not_exist" in e for e in errors)


def test_tampered_plan_fails_the_identity_check_inside_the_gate():
    registry = HypothesisRegistry()
    hid = _build_registered_hypothesis(registry)
    plan = _build_plan([hid], RANKING_METRIC_V1)
    tampered = dataclasses.replace(plan, benchmark_security_id="SOMETHING_ELSE")
    ok, errors = accept_research_plan(tampered, registry)
    assert not ok
    identity_ok, _ = verify_research_plan_identity(tampered)
    assert not identity_ok


def test_validate_selection_rule_accepts_both_ranking_metrics_rejects_a_third():
    old_rule = SelectionRule(minimum_executed_trades=1, minimum_evaluable_trades=1, minimum_evaluable_ratio=0.5)
    assert old_rule.ranking_metric == RANKING_METRIC_V1
    ok, errors = validate_selection_rule(old_rule)
    assert ok, errors

    new_rule = dataclasses.replace(old_rule, ranking_metric=RANKING_METRIC_STOP_MANAGED_V1)
    ok, errors = validate_selection_rule(new_rule)
    assert ok, errors

    bogus_rule = dataclasses.replace(old_rule, ranking_metric="SHARPE_RATIO")
    ok, errors = validate_selection_rule(bogus_rule)
    assert not ok
    assert any("ranking_metric" in e for e in errors)


def test_old_plan_fingerprint_is_byte_identical_to_before_the_new_field_existed():
    registry = HypothesisRegistry()
    hid = _build_registered_hypothesis(registry)
    plan = _build_plan([hid], RANKING_METRIC_V1)  # stop_managed_execution_semantics_profile_id=None
    fp_without_new_param = research_plan_fingerprint(
        plan.formation_start, plan.formation_end, plan.validation_start, plan.validation_end,
        plan.locked_oos_start, plan.selection_folds, plan.hypothesis_cohort_ids,
        plan.trading_calendar_id, plan.benchmark_security_id, plan.execution_semantics_profile_id,
        plan.selection_rule, plan.cost_assumptions, plan.exposure_manifest,
    )
    expected_id, expected_hash = build_research_plan_id(fp_without_new_param)
    assert plan.research_plan_id == expected_id
    assert plan.plan_hash == expected_hash
