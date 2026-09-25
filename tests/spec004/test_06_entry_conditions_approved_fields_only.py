"""TEST 6 -- entry conditions may only reference approved Discovery
fields (lanes/labels from states.yaml, reason codes from ReasonCode) --
Spec #004 SS11."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal

from spec004.conftest import make_proposal_raw


def test_approved_lane_and_reason_code_conditions_are_accepted(discovery_config, hypothesis_config):
    raw = make_proposal_raw(entry_definition={"core_conditions": [
        {"lane": "volatility", "label": "COMPRESSION"},
        {"reason_code": "MULTI_LANE_CONVERGENCE"},
    ]})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert result.valid, result.errors


def test_unknown_label_on_a_known_lane_is_rejected(discovery_config, hypothesis_config):
    raw = make_proposal_raw(entry_definition={"core_conditions": [
        {"lane": "volatility", "label": "SUPER_EXTREME_NONSENSE"},
    ]})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("label" in e for e in result.errors)
