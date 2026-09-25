"""TEST 11 -- horizon_candidates.values must be a subset of the
configured allowed_values (Spec #004 SS17-18)."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal

from spec004.conftest import make_proposal_raw


def test_values_within_allowed_set_are_accepted(discovery_config, hypothesis_config):
    raw = make_proposal_raw(horizon_candidates={"unit": "BARS", "values": [1, 5, 10], "selection_basis": "x"})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert result.valid, result.errors


def test_value_outside_allowed_set_is_rejected(discovery_config, hypothesis_config):
    raw = make_proposal_raw(horizon_candidates={"unit": "BARS", "values": [2, 7], "selection_basis": "x"})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("allowed_values" in e for e in result.errors)
