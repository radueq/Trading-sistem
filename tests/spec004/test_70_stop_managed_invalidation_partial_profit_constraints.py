"""TEST 70 -- when present, partial_profit.r_multiple must be finite and
> 0, and partial_profit.fraction must satisfy 0 < fraction < 1 (PATCH
#004-C / Spec #005 Exit Amendment v1.0, ACCEPTED, sections 1 and 4)."""
import math

from hypothesis.models.entities import (
    ExitFamily, ExitHypothesis, InvalidationCondition, ParameterSource, PartialProfitRule, StopLossRule,
)
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal
from hypothesis.registry.hypotheses import build_variant
from hypothesis.validation.rules import validate_for_preregistration

from spec004.conftest import build_preregistered_hypothesis_for_test, make_proposal_raw

_VALID_STOP_LOSS = {"basis": "ATR_TRAILING_V1", "atr_multiple": 2.0}
_VALID_INVALIDATION = [{"lane": "relative_strength", "holds_labels": ["HIGH", "VERY_HIGH"]}]


def _raw_with_partial_profit(partial_profit: dict) -> dict:
    return make_proposal_raw(exit_hypotheses=[{
        "exit_family": "STOP_MANAGED_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
        "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED",
        "stop_loss": _VALID_STOP_LOSS, "invalidation_conditions": _VALID_INVALIDATION,
        "partial_profit": partial_profit,
    }])


def test_zero_r_multiple_rejected_at_proposal_stage(discovery_config, hypothesis_config):
    raw = _raw_with_partial_profit({"r_multiple": 0.0, "fraction": 0.5})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("r_multiple" in e for e in result.errors)


def test_fraction_at_or_above_one_rejected_at_proposal_stage(discovery_config, hypothesis_config):
    raw = _raw_with_partial_profit({"r_multiple": 2.0, "fraction": 1.0})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("fraction" in e for e in result.errors)


def test_fraction_at_or_below_zero_rejected_at_proposal_stage(discovery_config, hypothesis_config):
    raw = _raw_with_partial_profit({"r_multiple": 2.0, "fraction": 0.0})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("fraction" in e for e in result.errors)


def test_valid_fraction_boundary_accepted_at_proposal_stage(discovery_config, hypothesis_config):
    raw = _raw_with_partial_profit({"r_multiple": 2.0, "fraction": 0.99})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert result.valid, result.errors


def test_invalid_partial_profit_rejected_at_preregistration_gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    bad_exit = ExitHypothesis(
        exit_family=ExitFamily.STOP_MANAGED_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=(InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),),
        stop_loss=StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=2.0),
        partial_profit=PartialProfitRule(r_multiple=math.inf, fraction=0.5),  # the violation under test
    )
    hyp, base_variants, registry = build_preregistered_hypothesis_for_test(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config,
    )
    bad_variant = build_variant(hyp, bad_exit, "EXPERIMENTAL_VARIANT", "t")
    all_variants = base_variants + (bad_variant,)
    hyp = hyp.__class__(**{**hyp.__dict__, "variant_ids": tuple(v.strategy_variant_id for v in all_variants)})

    ok, errors = validate_for_preregistration(hyp, all_variants, registry, hypothesis_config.data, run_registry)
    assert not ok
    assert any("r_multiple" in e for e in errors)
