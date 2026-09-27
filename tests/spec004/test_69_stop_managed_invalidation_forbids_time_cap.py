"""TEST 69 -- STOP_MANAGED_INVALIDATION never accepts max_holding_bars or
time_exit_bars: no automatic time-based exit (Radu's explicit design
decision, PATCH #004-C / Spec #005 Exit Amendment v1.0, ACCEPTED, section
1) -- distinct from and narrower than SS110-B's own no-unbounded-hold rule,
which continues to govern SIGNAL_INVALIDATION alone (test_46, unchanged)."""
from hypothesis.models.entities import (
    ExitFamily, ExitHypothesis, InvalidationCondition, ParameterSource, StopLossRule,
)
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal
from hypothesis.registry.hypotheses import build_variant
from hypothesis.validation.rules import validate_for_preregistration

from spec004.conftest import build_preregistered_hypothesis_for_test, make_proposal_raw

_VALID_STOP_LOSS = {"basis": "ATR_TRAILING_V1", "atr_multiple": 2.0}
_VALID_INVALIDATION = [{"lane": "relative_strength", "holds_labels": ["HIGH", "VERY_HIGH"]}]


def test_max_holding_bars_rejected_at_proposal_stage(discovery_config, hypothesis_config):
    raw = make_proposal_raw(exit_hypotheses=[{
        "exit_family": "STOP_MANAGED_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
        "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED",
        "stop_loss": _VALID_STOP_LOSS, "invalidation_conditions": _VALID_INVALIDATION,
        "max_holding_bars": 5,
    }])
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("max_holding_bars" in e for e in result.errors)


def test_time_exit_bars_rejected_at_proposal_stage(discovery_config, hypothesis_config):
    raw = make_proposal_raw(exit_hypotheses=[{
        "exit_family": "STOP_MANAGED_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
        "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED",
        "stop_loss": _VALID_STOP_LOSS, "invalidation_conditions": _VALID_INVALIDATION,
        "time_exit_bars": 3,
    }])
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("time_exit_bars" in e for e in result.errors)


def test_missing_invalidation_conditions_rejected_at_proposal_stage(discovery_config, hypothesis_config):
    raw = make_proposal_raw(exit_hypotheses=[{
        "exit_family": "STOP_MANAGED_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
        "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED",
        "stop_loss": _VALID_STOP_LOSS,
        # invalidation_conditions deliberately omitted
    }])
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("invalidation_conditions" in e for e in result.errors)


def test_max_holding_bars_rejected_at_preregistration_gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    bad_exit = ExitHypothesis(
        exit_family=ExitFamily.STOP_MANAGED_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=(InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),),
        stop_loss=StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=2.0),
        max_holding_bars=5,  # the violation under test
    )
    hyp, base_variants, registry = build_preregistered_hypothesis_for_test(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config,
    )
    bad_variant = build_variant(hyp, bad_exit, "EXPERIMENTAL_VARIANT", "t")
    all_variants = base_variants + (bad_variant,)
    hyp = hyp.__class__(**{**hyp.__dict__, "variant_ids": tuple(v.strategy_variant_id for v in all_variants)})

    ok, errors = validate_for_preregistration(hyp, all_variants, registry, hypothesis_config.data, run_registry)
    assert not ok
    assert any("max_holding_bars" in e for e in errors)
