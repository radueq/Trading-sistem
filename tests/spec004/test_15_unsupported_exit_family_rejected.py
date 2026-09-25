"""TEST 15 -- an unsupported exit family (e.g. ATR_TRAILING_STOP) is
rejected, never silently accepted as a new exit mechanism (Spec #004
SS22C/SS23)."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal

from spec004.conftest import make_proposal_raw


def test_atr_trailing_stop_exit_family_is_rejected(discovery_config, hypothesis_config):
    raw = make_proposal_raw(exit_hypotheses=[{
        "exit_family": "ATR_TRAILING_STOP", "horizon_reference_point": "ENTRY_BAR",
        "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED", "max_holding_bars": 5,
    }])
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("exit_family" in e and "ATR_TRAILING_STOP" in e for e in result.errors)
