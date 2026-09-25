"""TEST 3 -- StrategyHypothesis serializes deterministically: converting
the same frozen object to a dict/tuple form twice (or across two
independently-built-but-identical objects) always produces byte-identical
output -- no set/dict ordering nondeterminism anywhere in the entity
(Spec #004 SS86-87 -- reproducibility rests on the STRUCTURED record)."""
import dataclasses

from hypothesis.models.entities import HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode, HypothesisStatus, StrategyHypothesis
from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint


def _build(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    fp = hypothesis_fingerprint(
        "SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance,
        hypothesis_config.config_version,
    )
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, hypothesis_config.config_version)
    prov = HypothesisProvenance("HUMAN:radu", None, None, "radu", "2026-09-25T00:00:00Z")
    return StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.DRAFT.value,
        research_mode=HypothesisResearchMode.EXPLORATORY_HYPOTHESIS.value, parent_signature_id="SIG_X",
        signature_set_id=evidence_provenance.signature_set_id, direction="LONG", direction_basis="EVIDENCE_SIGN",
        entry_definition=entry_definition, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizon_candidates,
        variant_ids=(), evidence_provenance=evidence_provenance, hypothesis_provenance=prov, constraints=comp,
        created_at="2026-09-25T00:00:00Z", created_by="radu", strategy_config_version=hypothesis_config.config_version,
    )


def test_two_independently_built_identical_hypotheses_serialize_identically(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    h1 = _build(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    h2 = _build(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    assert dataclasses.asdict(h1) == dataclasses.asdict(h2)
    assert repr(h1) == repr(h2)
