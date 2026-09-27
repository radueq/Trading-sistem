"""TEST 73 -- full pipeline round-trip for STOP_MANAGED_INVALIDATION:
normalize -> validate_proposal -> materialize_variants -> register_variant
-> validate_for_preregistration, the SAME sequence Spec #004's other exit
families already go through (PATCH #004-C / Spec #005 Exit Amendment
v1.0, ACCEPTED)."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal
from hypothesis.registry.hypotheses import materialize_variants
from hypothesis.validation.rules import validate_for_preregistration

from spec004.conftest import make_proposal_raw


def test_full_pipeline_accepts_a_mixed_family_proposal(discovery_config, hypothesis_config, entry_definition, evidence_provenance, run_registry, registry):
    from hypothesis.models.entities import (
        HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode,
        HypothesisStatus, StrategyHypothesis,
    )
    from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint

    # Exactly one SIGNAL_INVALIDATION-family-budget-worth of exit_hypotheses
    # (max_exit_families_per_hypothesis=2, unchanged by this patch: TIME_EXIT
    # always occupies one slot, leaving exactly one more here).
    raw = make_proposal_raw(exit_hypotheses=[
        {
            "exit_family": "STOP_MANAGED_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
            "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED",
            "stop_loss": {"basis": "ATR_TRAILING_V1", "atr_multiple": 2.0},
            "partial_profit": {"r_multiple": 2.0, "fraction": 0.5},
            "invalidation_conditions": [{"lane": "relative_strength", "holds_labels": ["HIGH", "VERY_HIGH"]}],
        },
    ])
    proposal = normalize_proposal(raw)
    validation_result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert validation_result.valid, validation_result.errors

    fp = hypothesis_fingerprint(
        proposal.source_evidence.signature_id, proposal.direction, proposal.entry_definition,
        proposal.entry_execution_policy, proposal.horizon_candidates, proposal.source_evidence,
        hypothesis_config.config_version,
    )
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(
        hypothesis_config.data["hypothesis_complexity"]["max_entry_conditions"],
        hypothesis_config.data["hypothesis_complexity"]["max_optional_confirmation_conditions"],
        hypothesis_config.config_version,
    )
    prov = HypothesisProvenance("AGENT:claude", proposal.proposal_id, "CONSENSUS", "radu", "t")
    draft = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.DRAFT.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value,
        parent_signature_id=proposal.source_evidence.signature_id,
        signature_set_id=proposal.source_evidence.signature_set_id, direction=proposal.direction,
        direction_basis=proposal.direction_basis, entry_definition=proposal.entry_definition,
        entry_execution_policy=proposal.entry_execution_policy, horizon_candidate_set=proposal.horizon_candidates,
        variant_ids=(), evidence_provenance=proposal.source_evidence, hypothesis_provenance=prov, constraints=comp,
        created_at="t", created_by="radu", strategy_config_version=hypothesis_config.config_version,
    )
    variants = materialize_variants(draft, signal_invalidation_exits=proposal.exit_hypotheses, created_at="t")
    # 3 TIME_EXIT (one per horizon_candidates value) + 1 STOP_MANAGED_INVALIDATION.
    assert len(variants) == 3 + 1
    stop_managed = [v for v in variants if v.exit_hypothesis.exit_family == "STOP_MANAGED_INVALIDATION"]
    assert len(stop_managed) == 1
    assert stop_managed[0].exit_hypothesis.partial_profit is not None

    hyp = draft.__class__(**{
        **draft.__dict__, "status": HypothesisStatus.PREREGISTERED.value,
        "variant_ids": tuple(v.strategy_variant_id for v in variants),
    })
    registry._force_register(hyp)
    for v in variants:
        registry.register_variant(v)

    ok, errors = validate_for_preregistration(hyp, variants, registry, hypothesis_config.data, run_registry)
    assert ok, errors
