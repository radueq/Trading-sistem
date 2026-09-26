"""TEST 46 -- SIGNAL_INVALIDATION always requires a preregistered
max_holding_bars time cap; an unbounded "hold until RS deteriorates" is
never accepted (Radu's SS110-B addendum, 2026-09-25) -- checked both at
proposal-validation time and at the later pre-preregistration gate."""
from hypothesis.models.entities import ExitFamily, ExitHypothesis, ParameterSource
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal
from hypothesis.validation.rules import validate_for_preregistration

from spec004.conftest import make_proposal_raw


def test_signal_invalidation_without_max_holding_bars_is_rejected_at_proposal_stage(discovery_config, hypothesis_config):
    raw = make_proposal_raw(exit_hypotheses=[{
        "exit_family": "SIGNAL_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
        "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED",
        "invalidation_conditions": [{"lane": "relative_strength", "holds_labels": ["HIGH", "VERY_HIGH"]}],
        # max_holding_bars deliberately omitted
    }])
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("max_holding_bars" in e for e in result.errors)


def test_signal_invalidation_without_max_holding_bars_is_rejected_at_preregistration_gate(registry, hypothesis_config, run_registry):
    from hypothesis.models.entities import (
        Direction, EntryDefinition, HypothesisComplexitySnapshot, HypothesisProvenance,
        HypothesisResearchMode, HypothesisStatus, LaneStateCondition, StrategyHypothesis, InvalidationCondition,
    )
    from hypothesis.registry.hypotheses import build_hypothesis_id, build_variant, hypothesis_fingerprint, materialize_variants, HorizonCandidateSet

    entry = EntryDefinition(core_conditions=(LaneStateCondition("volatility", "COMPRESSION"),))
    horizons = HorizonCandidateSet(unit="BARS", values=(3,), selection_basis="x", parameter_source="PRE_SPECIFIED")
    from hypothesis.models.entities import EvidenceProvenance
    ev = EvidenceProvenance("run_x", "v1.0.0", "cfg_eval", "SIG_X", "sigset_x", "v1.0.0", "cfg_disc", "1D")
    fp = hypothesis_fingerprint("SIG_X", Direction.LONG.value, entry, "NEXT_BAR_OPEN", horizons, ev, hypothesis_config.config_version)
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, hypothesis_config.config_version)
    prov = HypothesisProvenance("HUMAN:radu", None, None, "radu", "t")
    hyp = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.DRAFT.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id="SIG_X",
        signature_set_id="sigset_x", direction=Direction.LONG.value, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizons,
        variant_ids=(), evidence_provenance=ev, hypothesis_provenance=prov, constraints=comp,
        created_at="t", created_by="radu", strategy_config_version=hypothesis_config.config_version,
    )
    time_exit_variants = materialize_variants(hyp, created_at="t")
    unbounded_invalidation_exit = ExitHypothesis(
        exit_family=ExitFamily.SIGNAL_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=(InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),),
        max_holding_bars=None,  # the violation under test
    )
    bad_variant = build_variant(hyp, unbounded_invalidation_exit, "EXPERIMENTAL_VARIANT", "t")
    all_variants = time_exit_variants + (bad_variant,)
    hyp = hyp.__class__(**{**hyp.__dict__, "variant_ids": tuple(v.strategy_variant_id for v in all_variants)})

    ok, errors = validate_for_preregistration(hyp, all_variants, registry, hypothesis_config.data, run_registry)
    assert not ok
    assert any("max_holding_bars" in e for e in errors)
