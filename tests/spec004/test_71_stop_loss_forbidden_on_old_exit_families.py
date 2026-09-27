"""TEST 71 -- stop_loss/partial_profit must be None for TIME_EXIT and
SIGNAL_INVALIDATION; populating either is rejected, never silently
ignored by the fingerprint (PATCH #004-C / Spec #005 Exit Amendment v1.0,
ACCEPTED, section 1 -- the derogation is strictly family-conditioned, and
_exit_fp() at hypothesis/registry/hypotheses.py:91 does not reference
these fields for the old families, so an unguarded stop_loss there would
be a parameter the hash silently ignores)."""
from hypothesis.models.entities import (
    ExitFamily, ExitHypothesis, InvalidationCondition, ParameterSource, StopLossRule,
)
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal
from hypothesis.registry.hypotheses import build_variant, variant_fingerprint
from hypothesis.validation.rules import validate_for_preregistration

from spec004.conftest import build_preregistered_hypothesis_for_test, make_proposal_raw


def test_signal_invalidation_with_stop_loss_rejected_at_proposal_stage(discovery_config, hypothesis_config):
    raw = make_proposal_raw(exit_hypotheses=[{
        "exit_family": "SIGNAL_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
        "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED", "max_holding_bars": 5,
        "invalidation_conditions": [{"lane": "relative_strength", "holds_labels": ["HIGH", "VERY_HIGH"]}],
        "stop_loss": {"basis": "ATR_TRAILING_V1", "atr_multiple": 2.0},
    }])
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("stop_loss" in e and "SIGNAL_INVALIDATION" in e for e in result.errors)


def test_signal_invalidation_with_stop_loss_rejected_at_preregistration_gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    contaminated_exit = ExitHypothesis(
        exit_family=ExitFamily.SIGNAL_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=(InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),),
        max_holding_bars=5,
        stop_loss=StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=2.0),  # the contamination under test
    )
    hyp, base_variants, registry = build_preregistered_hypothesis_for_test(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config,
    )
    bad_variant = build_variant(hyp, contaminated_exit, "EXPERIMENTAL_VARIANT", "t")
    all_variants = base_variants + (bad_variant,)
    hyp = hyp.__class__(**{**hyp.__dict__, "variant_ids": tuple(v.strategy_variant_id for v in all_variants)})

    ok, errors = validate_for_preregistration(hyp, all_variants, registry, hypothesis_config.data, run_registry)
    assert not ok
    assert any("stop_loss" in e for e in errors)


def test_time_exit_with_stop_loss_rejected_at_preregistration_gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    contaminated_exit = ExitHypothesis(
        exit_family=ExitFamily.TIME_EXIT.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.PRE_SPECIFIED.value,
        time_exit_bars=3,
        stop_loss=StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=2.0),  # the contamination under test
    )
    hyp, base_variants, registry = build_preregistered_hypothesis_for_test(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config,
    )
    bad_variant = build_variant(hyp, contaminated_exit, "EXPERIMENTAL_VARIANT", "t")
    all_variants = base_variants + (bad_variant,)
    hyp = hyp.__class__(**{**hyp.__dict__, "variant_ids": tuple(v.strategy_variant_id for v in all_variants)})

    ok, errors = validate_for_preregistration(hyp, all_variants, registry, hypothesis_config.data, run_registry)
    assert not ok
    assert any("stop_loss" in e for e in errors)


def test_stop_loss_never_silently_ignored_by_old_family_fingerprint():
    """Even if a caller somehow constructed a TIME_EXIT ExitHypothesis with
    stop_loss populated (bypassing the validator above), _exit_fp() itself
    would compute the SAME fingerprint regardless of stop_loss -- proving
    the validator ban above is load-bearing, not decorative: without it,
    two objects differing only by stop_loss would collide to one identity."""
    clean = ExitHypothesis(
        exit_family=ExitFamily.TIME_EXIT.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.PRE_SPECIFIED.value, time_exit_bars=3,
    )
    contaminated = ExitHypothesis(
        exit_family=ExitFamily.TIME_EXIT.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.PRE_SPECIFIED.value, time_exit_bars=3,
        stop_loss=StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=99.0),
    )
    assert variant_fingerprint("parent_hash_x", clean) == variant_fingerprint("parent_hash_x", contaminated)
