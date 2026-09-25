"""TEST 20 -- forward_return (or relative_return/mean_return) can never
appear inside an entry OR exit/invalidation condition (Spec #004 SS72)."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal

from spec004.conftest import make_proposal_raw


def test_forward_return_in_entry_condition_is_rejected(discovery_config, hypothesis_config):
    raw = make_proposal_raw(entry_definition={"core_conditions": [{"lane": "forward_return", "label": "HIGH"}]})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("forward_return" in e for e in result.errors)


def test_mean_return_in_invalidation_condition_is_rejected(discovery_config, hypothesis_config):
    raw = make_proposal_raw(exit_hypotheses=[{
        "exit_family": "SIGNAL_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
        "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED", "max_holding_bars": 5,
        "invalidation_conditions": [{"lane": "mean_return", "holds_labels": ["HIGH"]}],
    }])
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("mean_return" in e for e in result.errors)
