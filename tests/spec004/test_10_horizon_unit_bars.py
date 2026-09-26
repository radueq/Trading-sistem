"""TEST 10 -- horizon_candidates.unit must be BARS, never DAYS (Spec #004
SS17-18/SS68 -- bar-based, 4H-ready by construction)."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal

from spec004.conftest import make_proposal_raw


def test_bars_unit_is_accepted(discovery_config, hypothesis_config):
    raw = make_proposal_raw(horizon_candidates={"unit": "BARS", "values": [2, 3], "selection_basis": "x", "parameter_source": "PRE_SPECIFIED"})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert result.valid, result.errors


def test_days_unit_is_rejected(discovery_config, hypothesis_config):
    raw = make_proposal_raw(horizon_candidates={"unit": "DAYS", "values": [2, 3], "selection_basis": "x", "parameter_source": "PRE_SPECIFIED"})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("unit" in e for e in result.errors)
