"""TEST 24 -- a PREREGISTERED hypothesis is immutable: the dataclass is
frozen, and the registry refuses to overwrite a PREREGISTERED record with
different content under the same id (Spec #004 SS30-31)."""
import dataclasses

import pytest

from hypothesis.models.entities import (
    Direction, HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode, HypothesisStatus,
    StrategyHypothesis,
)
from hypothesis.registry.hypotheses import HypothesisRegistry, ImmutableHypothesisError, build_hypothesis_id, hypothesis_fingerprint


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


def test_dataclass_field_assignment_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    hyp = _preregistered(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    with pytest.raises(dataclasses.FrozenInstanceError):
        hyp.direction = "SHORT"


def test_registry_refuses_to_overwrite_preregistered_with_different_content(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    hyp = _preregistered(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    reg = HypothesisRegistry()
    reg._force_register(hyp)  # planting an already-valid PREREGISTERED record, not exercising register()'s own guard (see TEST 53 for that)
    tampered = dataclasses.replace(hyp, direction_basis="HUMAN_DECISION", created_by="someone_else")
    with pytest.raises(ImmutableHypothesisError):
        reg.register(tampered)
