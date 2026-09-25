"""TEST 33 -- FACTS_FROM_EVIDENCE and HYPOTHESIS_INTERPRETATION are kept
in separate fields, never merged into one blob (Spec #004 SS49-50)."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal

from spec004.conftest import make_proposal_raw


def test_facts_and_interpretation_are_distinct_fields(discovery_config, hypothesis_config):
    proposal = normalize_proposal(make_proposal_raw())
    assert proposal.facts_from_evidence != (proposal.interpretation,)
    assert isinstance(proposal.facts_from_evidence, tuple)
    assert isinstance(proposal.interpretation, str)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert result.valid, result.errors


def test_missing_facts_from_evidence_is_rejected(discovery_config, hypothesis_config):
    raw = make_proposal_raw(facts_from_evidence=[])
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("facts_from_evidence" in e for e in result.errors)


def test_missing_interpretation_is_rejected(discovery_config, hypothesis_config):
    raw = make_proposal_raw(interpretation="")
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("interpretation" in e for e in result.errors)
