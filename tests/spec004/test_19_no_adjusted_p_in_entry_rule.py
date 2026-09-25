"""TEST 19 -- the exact forbidden example from Spec #004 SS74 (`IF
adjusted_p < 0.05 AND mean_relative_return > 1% THEN BUY`) can never be
expressed through the approved entry vocabulary -- structurally, not just
by convention."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal

from spec004.conftest import make_proposal_raw


def test_adjusted_p_as_a_lane_condition_is_rejected(discovery_config, hypothesis_config):
    raw = make_proposal_raw(entry_definition={"core_conditions": [{"lane": "adjusted_p", "label": "LOW"}]})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("adjusted_p" in e for e in result.errors)


def test_adjusted_p_as_a_reason_code_is_rejected(discovery_config, hypothesis_config):
    raw = make_proposal_raw(entry_definition={"core_conditions": [{"reason_code": "adjusted_p"}]})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
