"""TEST 27 -- max_hypotheses_per_signature is enforced at preregistration
time (Spec #004 SS52)."""
from hypothesis.models.entities import (
    Direction, EntryDefinition, HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode,
    HypothesisStatus, LaneStateCondition, StrategyHypothesis,
)
from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint, materialize_variants
from hypothesis.validation.rules import validate_for_preregistration


def _hyp(idx, horizon_candidates, evidence_provenance, hypothesis_config):
    entry = EntryDefinition(core_conditions=(LaneStateCondition("volatility", "COMPRESSION"), LaneStateCondition("volume", ["VERY_LOW", "LOW", "NEUTRAL", "HIGH", "VERY_HIGH"][idx % 5])))
    fp = hypothesis_fingerprint("SIG_X", Direction.LONG.value, entry, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, hypothesis_config.config_version)
    prov = HypothesisProvenance("HUMAN:radu", None, None, "radu", "2026-09-25T00:00:00Z")
    hyp = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.DRAFT.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id="SIG_X",
        signature_set_id=evidence_provenance.signature_set_id, direction=Direction.LONG.value, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizon_candidates,
        variant_ids=(), evidence_provenance=evidence_provenance, hypothesis_provenance=prov, constraints=comp,
        created_at="2026-09-25T00:00:00Z", created_by="radu", strategy_config_version=hypothesis_config.config_version,
    )
    variants = materialize_variants(hyp, created_at="2026-09-25T00:00:00Z")
    hyp = hyp.__class__(**{**hyp.__dict__, "status": HypothesisStatus.PREREGISTERED.value, "variant_ids": tuple(v.strategy_variant_id for v in variants)})
    return hyp, variants


def test_fourth_hypothesis_on_the_same_signature_exceeds_budget(registry, horizon_candidates, evidence_provenance, hypothesis_config):
    max_per_sig = hypothesis_config.data["hypothesis_budget"]["max_hypotheses_per_signature"]
    assert max_per_sig == 3
    for i in range(max_per_sig):
        hyp, variants = _hyp(i, horizon_candidates, evidence_provenance, hypothesis_config)
        ok, errors = validate_for_preregistration(hyp, variants, registry, hypothesis_config.data)
        assert ok, errors
        registry.register(hyp)
        for v in variants:
            registry.register_variant(v)

    hyp4, variants4 = _hyp(max_per_sig, horizon_candidates, evidence_provenance, hypothesis_config)
    ok, errors = validate_for_preregistration(hyp4, variants4, registry, hypothesis_config.data)
    assert not ok
    assert any("max_hypotheses_per_signature" in e for e in errors)
