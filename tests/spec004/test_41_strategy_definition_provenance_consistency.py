"""TEST 41 -- a StrategyDefinition's provenance stays traceable to its
hypothesis (Spec #004 SS63/SS70-71: source_feature_or_state/source_engine
provenance discipline)."""
from hypothesis.models.entities import (
    Direction, HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode, HypothesisStatus,
    StrategyHypothesis,
)
from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint, materialize_variants
from hypothesis.registry.strategy_registry import build_strategy_definition


def test_strategy_definition_traces_back_to_its_hypothesis_and_variant(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    fp = hypothesis_fingerprint("SIG_X", Direction.LONG.value, entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, hypothesis_config.config_version)
    prov = HypothesisProvenance("HUMAN:radu", None, None, "radu", "2026-09-25T00:00:00Z")
    hyp_draft = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.DRAFT.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id="SIG_X",
        signature_set_id=evidence_provenance.signature_set_id, direction=Direction.LONG.value, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry_definition, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizon_candidates,
        variant_ids=(), evidence_provenance=evidence_provenance, hypothesis_provenance=prov, constraints=comp,
        created_at="2026-09-25T00:00:00Z", created_by="radu", strategy_config_version=hypothesis_config.config_version,
    )
    variants = materialize_variants(hyp_draft, created_at="2026-09-25T00:00:00Z")
    hyp = hyp_draft.__class__(**{**hyp_draft.__dict__, "status": HypothesisStatus.PREREGISTERED.value, "variant_ids": tuple(v.strategy_variant_id for v in variants)})

    for v in variants:
        sd = build_strategy_definition(hyp, v)
        assert sd.hypothesis_id == hyp.hypothesis_id
        assert sd.strategy_variant_id == v.strategy_variant_id
        assert sd.timeframe == evidence_provenance.timeframe
        assert sd.direction == hyp.direction
        assert sd.exit_definition == v.exit_hypothesis
