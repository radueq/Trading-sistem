"""Shared helper for building a REAL, registered STOP_MANAGED_INVALIDATION
`StrategyHypothesis`/`StrategyVariant` pair and a matching ACCEPTED
`ResearchPlan` -- used by test_32 (the plan-acceptance gate itself),
test_33/34/35 (the Session Engine, which round-1 review finding #5
requires to resolve every entry signal against a REAL, registry-backed
variant belonging to the plan's own accepted cohort -- never a
caller-typed direction/k/r_multiple/fraction dict floating free of any
actual hypothesis).
"""
from __future__ import annotations

import dataclasses
from typing import Optional

from hypothesis.models.entities import (
    Direction,
    EntryDefinition,
    EvidenceProvenance,
    ExitFamily,
    ExitHypothesis,
    HorizonCandidateSet,
    HypothesisComplexitySnapshot,
    HypothesisProvenance,
    HypothesisResearchMode,
    HypothesisStatus,
    InvalidationCondition,
    LaneStateCondition,
    ParameterSource,
    PartialProfitRule,
    StopLossRule,
    StrategyHypothesis,
)
from hypothesis.registry.hypotheses import HypothesisRegistry, build_hypothesis_id, hypothesis_fingerprint, materialize_variants

from backtest.exits.entities import build_stop_managed_execution_semantics_profile_v1
from backtest.models.entities import (
    RANKING_METRIC_STOP_MANAGED_V1,
    CostAssumptions,
    ExposureManifest,
    ResearchPlan,
    SelectionFold,
    SelectionRule,
    build_execution_semantics_profile_v1,
    build_research_plan_id,
    research_plan_fingerprint,
)

_EVIDENCE = dict(
    evaluation_run_id="run_x", evaluation_engine_version="v1.0.0", evaluation_config_version="cfg_eval",
    signature_id="SIG_X", signature_set_id="sigset_x", discovery_engine_version="v1.0.0",
    discovery_config_version="cfg_disc", timeframe="1D",
)


def build_stop_managed_exit_hypothesis(k: float = 2.0, r_multiple: Optional[float] = None, fraction: Optional[float] = None) -> ExitHypothesis:
    return ExitHypothesis(
        exit_family=ExitFamily.STOP_MANAGED_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=(InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),),
        stop_loss=StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=k),
        partial_profit=PartialProfitRule(r_multiple=r_multiple, fraction=fraction) if r_multiple is not None else None,
    )


def build_registered_stop_managed_hypothesis(
    registry: HypothesisRegistry, direction: str = Direction.LONG.value,
    k: float = 2.0, r_multiple: Optional[float] = None, fraction: Optional[float] = None,
    signature_id: str = "SIG_X",
) -> tuple[str, str]:
    """Registers a fully self-consistent, PREREGISTERED StrategyHypothesis
    with exactly one STOP_MANAGED_INVALIDATION variant, directly into
    `registry` (mirrors tests/spec004/conftest.py's own
    `build_preregistered_hypothesis_for_test()` pattern -- bypassing the
    full #004 preregistration gate on purpose; these tests exercise the
    Session Engine, not that gate). Returns (hypothesis_id,
    strategy_variant_id)."""
    entry = EntryDefinition(core_conditions=(LaneStateCondition("volatility", "COMPRESSION"),))
    horizons = HorizonCandidateSet(unit="BARS", values=(3,), selection_basis="x", parameter_source=ParameterSource.PRE_SPECIFIED.value)
    ev = EvidenceProvenance(**{**_EVIDENCE, "signature_id": signature_id})
    fp = hypothesis_fingerprint(signature_id, direction, entry, "NEXT_BAR_OPEN", horizons, ev, "cfg_hyp_x")
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, "cfg_hyp_x")
    prov = HypothesisProvenance("HUMAN:radu", None, None, "radu", "t")
    hyp = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.PREREGISTERED.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id=signature_id,
        signature_set_id="sigset_x", direction=direction, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizons,
        variant_ids=(), evidence_provenance=ev, hypothesis_provenance=prov, constraints=comp,
        created_at="t", created_by="radu", strategy_config_version="cfg_hyp_x",
    )
    stop_managed_exit = build_stop_managed_exit_hypothesis(k=k, r_multiple=r_multiple, fraction=fraction)
    variants = materialize_variants(hyp, signal_invalidation_exits=(stop_managed_exit,), created_at="t")
    hyp = dataclasses.replace(hyp, variant_ids=tuple(v.strategy_variant_id for v in variants))
    registry._force_register(hyp)
    for v in variants:
        registry.register_variant(v)
    stop_managed_variant = next(v for v in variants if v.exit_hypothesis.exit_family == ExitFamily.STOP_MANAGED_INVALIDATION.value)
    return hyp.hypothesis_id, stop_managed_variant.strategy_variant_id


def build_accepted_stop_managed_plan(
    hypothesis_cohort_ids: tuple[str, ...], cost_assumptions: Optional[CostAssumptions] = None,
    **zone_overrides,
) -> tuple[ResearchPlan, "StopManagedExecutionSemanticsProfile"]:
    """A `ResearchPlan` that `accept_research_plan()` accepts for a cohort
    that includes at least one STOP_MANAGED_INVALIDATION variant: the new
    ranking metric, a real, verified `StopManagedExecutionSemanticsProfile`,
    and a matching `stop_managed_execution_semantics_profile_id`. Returns
    (plan, profile) -- the caller must pass `profile` back into
    `accept_research_plan()`/`run_stage()`'s own `stop_managed_profile`
    parameter."""
    from backtest.exits.entities import StopManagedExecutionSemanticsProfile  # noqa: F401  (for the return type)

    profile = build_stop_managed_execution_semantics_profile_v1()
    rule = SelectionRule(minimum_executed_trades=1, minimum_evaluable_trades=1, minimum_evaluable_ratio=0.5, ranking_metric=RANKING_METRIC_STOP_MANAGED_V1)
    exec_profile = build_execution_semantics_profile_v1()
    costs = cost_assumptions or CostAssumptions(
        commission_entry_rate=0.0, commission_exit_rate=0.0, slippage_entry_bps=0.0, slippage_exit_bps=0.0, borrow_annual_rate=0.0,
    )
    exposure = ExposureManifest(declared_unseen=True)
    fields = dict(
        formation_start=zone_overrides.get("formation_start", "2024-01-01"),
        formation_end=zone_overrides.get("formation_end", "2024-01-31"),
        validation_start=zone_overrides.get("validation_start", "2024-02-01"),
        validation_end=zone_overrides.get("validation_end", "2024-02-29"),
        locked_oos_start=zone_overrides.get("locked_oos_start", "2024-03-01"),
        selection_folds=(SelectionFold("fold_1", "2024-01-01", "2024-01-31"),),
        hypothesis_cohort_ids=tuple(hypothesis_cohort_ids), trading_calendar_id="cal_x",
        benchmark_security_id="SBENCH", execution_semantics_profile_id=exec_profile.profile_id,
        selection_rule=rule, cost_assumptions=costs, exposure_manifest=exposure,
        stop_managed_execution_semantics_profile_id=profile.profile_id,
    )
    fp = research_plan_fingerprint(**fields)
    plan_id, plan_hash = build_research_plan_id(fp)
    plan = ResearchPlan(research_plan_id=plan_id, plan_hash=plan_hash, created_at="t", created_by="radu", **fields)
    return plan, profile
