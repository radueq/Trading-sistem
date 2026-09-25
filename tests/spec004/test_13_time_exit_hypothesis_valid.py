"""TEST 13 -- a well-formed TIME_EXIT ExitHypothesis materializes
correctly, and the family expands one variant per candidate value (Spec
#004 SS21-26, Radu's SS110-C/D eager-materialization decision)."""
from hypothesis.models.entities import (
    Direction, EvidenceProvenance, HypothesisComplexitySnapshot, HypothesisProvenance,
    HypothesisResearchMode, HypothesisStatus, StrategyHypothesis,
)
from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint, materialize_variants


def test_time_exit_family_expands_one_variant_per_horizon_value(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    fp = hypothesis_fingerprint("SIG_X", Direction.LONG.value, entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, hypothesis_config.config_version)
    prov = HypothesisProvenance("HUMAN:radu", None, None, "radu", "2026-09-25T00:00:00Z")
    hyp = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.DRAFT.value,
        research_mode=HypothesisResearchMode.EXPLORATORY_HYPOTHESIS.value, parent_signature_id="SIG_X",
        signature_set_id=evidence_provenance.signature_set_id, direction=Direction.LONG.value, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry_definition, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizon_candidates,
        variant_ids=(), evidence_provenance=evidence_provenance, hypothesis_provenance=prov, constraints=comp,
        created_at="2026-09-25T00:00:00Z", created_by="radu", strategy_config_version=hypothesis_config.config_version,
    )
    variants = materialize_variants(hyp, created_at="2026-09-25T00:00:00Z")
    assert len(variants) == len(horizon_candidates.values) == 3
    bars = sorted(v.exit_hypothesis.time_exit_bars for v in variants)
    assert bars == sorted(horizon_candidates.values)
    for v in variants:
        assert v.exit_hypothesis.exit_family == "TIME_EXIT"
        assert v.exit_hypothesis.horizon_reference_point == "ENTRY_BAR"
        assert v.exit_hypothesis.exit_execution_policy == "BAR_CLOSE"
