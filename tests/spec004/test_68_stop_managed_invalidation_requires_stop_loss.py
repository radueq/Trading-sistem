"""TEST 68 -- STOP_MANAGED_INVALIDATION always requires stop_loss, and
stop_loss.basis/atr_multiple must be structurally valid -- checked at
both proposal-validation time and the pre-preregistration gate (PATCH
#004-C / Spec #005 Exit Amendment v1.0, ACCEPTED, section 1)."""
from hypothesis.models.entities import (
    ExitFamily, ExitHypothesis, InvalidationCondition, ParameterSource, StopLossRule,
)
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal
from hypothesis.registry.hypotheses import build_variant
from hypothesis.validation.rules import validate_for_preregistration

from spec004.conftest import build_preregistered_hypothesis_for_test, make_proposal_raw


def _raw_with_stop_loss(stop_loss: dict | None) -> dict:
    exit_h = {
        "exit_family": "STOP_MANAGED_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
        "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED",
        "invalidation_conditions": [{"lane": "relative_strength", "holds_labels": ["HIGH", "VERY_HIGH"]}],
    }
    if stop_loss is not None:
        exit_h["stop_loss"] = stop_loss
    return make_proposal_raw(exit_hypotheses=[exit_h])


def test_missing_stop_loss_rejected_at_proposal_stage(discovery_config, hypothesis_config):
    raw = _raw_with_stop_loss(None)
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("stop_loss" in e for e in result.errors)


def test_wrong_basis_rejected_at_proposal_stage(discovery_config, hypothesis_config):
    raw = _raw_with_stop_loss({"basis": "FIXED_PERCENT", "atr_multiple": 2.0})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("ATR_TRAILING_V1" in e for e in result.errors)


def test_non_positive_atr_multiple_rejected_at_proposal_stage(discovery_config, hypothesis_config):
    raw = _raw_with_stop_loss({"basis": "ATR_TRAILING_V1", "atr_multiple": 0.0})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("atr_multiple" in e for e in result.errors)


def test_missing_stop_loss_rejected_at_preregistration_gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    bad_exit = ExitHypothesis(
        exit_family=ExitFamily.STOP_MANAGED_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=(InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),),
        stop_loss=None,
    )
    hyp, base_variants, registry = build_preregistered_hypothesis_for_test(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config,
    )
    bad_variant = build_variant(hyp, bad_exit, "EXPERIMENTAL_VARIANT", "t")
    all_variants = base_variants + (bad_variant,)
    hyp = hyp.__class__(**{**hyp.__dict__, "variant_ids": tuple(v.strategy_variant_id for v in all_variants)})

    ok, errors = validate_for_preregistration(hyp, all_variants, registry, hypothesis_config.data, run_registry)
    assert not ok
    assert any("stop_loss" in e for e in errors)
