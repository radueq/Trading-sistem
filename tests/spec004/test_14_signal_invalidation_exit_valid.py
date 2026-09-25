"""TEST 14 -- a well-formed SIGNAL_INVALIDATION ExitHypothesis (with its
required max_holding_bars time cap) validates successfully (Spec #004
SS22B/SS25, Radu's SS110-B addendum)."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal

from spec004.conftest import make_proposal_raw


def test_signal_invalidation_with_time_cap_is_accepted(discovery_config, hypothesis_config):
    proposal = normalize_proposal(make_proposal_raw())
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert result.valid, result.errors
    ex = proposal.exit_hypotheses[0]
    assert ex.exit_family == "SIGNAL_INVALIDATION"
    assert ex.max_holding_bars == 5
    assert ex.invalidation_conditions[0].lane == "relative_strength"
    assert ex.invalidation_conditions[0].holds_labels == ("HIGH", "VERY_HIGH")


def test_signal_invalidation_with_reason_code_trigger_is_accepted(discovery_config, hypothesis_config):
    raw = make_proposal_raw(exit_hypotheses=[{
        "exit_family": "SIGNAL_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
        "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED", "max_holding_bars": 5,
        "invalidation_conditions": [{"reason_code": "STATE_TRANSITION", "triggers_on_presence": True}],
    }])
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert result.valid, result.errors
