"""TEST 25 -- any modification after preregistration creates a new
hypothesis_version/id via create_new_version(), never an in-place edit
(Spec #004 SS31)."""
import pytest

from hypothesis.models.entities import (
    Direction, HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode, HypothesisStatus,
    StrategyHypothesis,
)
from hypothesis.registry.hypotheses import build_hypothesis_id, create_new_version, hypothesis_fingerprint


def _preregistered(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    fp = hypothesis_fingerprint("SIG_X", Direction.LONG.value, entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, hypothesis_config.config_version)
    prov = HypothesisProvenance("HUMAN:radu", None, None, "radu", "2026-09-25T00:00:00Z")
    return StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.PREREGISTERED.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id="SIG_X",
        signature_set_id=evidence_provenance.signature_set_id, direction=Direction.LONG.value, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry_definition, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizon_candidates,
        variant_ids=(), evidence_provenance=evidence_provenance, hypothesis_provenance=prov, constraints=comp,
        created_at="2026-09-25T00:00:00Z", created_by="radu", strategy_config_version=hypothesis_config.config_version,
    )


def test_create_new_version_produces_different_id_and_bumped_version(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    parent = _preregistered(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    child = create_new_version(parent, direction="SHORT")
    assert child.hypothesis_id != parent.hypothesis_id
    assert child.hypothesis_version == parent.hypothesis_version + 1
    assert child.supersedes_hypothesis_id == parent.hypothesis_id
    assert child.status == HypothesisStatus.DRAFT.value  # a new version restarts the lifecycle


def test_create_new_version_with_no_actual_change_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    parent = _preregistered(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    with pytest.raises(ValueError):
        create_new_version(parent)
