"""TEST 4 -- direction must be one of the explicit allowed values; never
implicit/derived (Spec #004 SS8)."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal

from spec004.conftest import make_proposal_raw


def test_valid_direction_is_accepted(discovery_config, hypothesis_config):
    proposal = normalize_proposal(make_proposal_raw(direction="LONG"))
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert result.valid, result.errors


def test_unrecognized_direction_is_rejected(discovery_config, hypothesis_config):
    proposal = normalize_proposal(make_proposal_raw(direction="SIDEWAYS"))
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("direction" in e for e in result.errors)
