"""TEST 16 -- risk_exit.enabled must be false in V1 (Spec #004 SS23/SS79-81
-- ATR/stop-loss optimization is deliberately out of scope)."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal

from spec004.conftest import make_proposal_raw


def test_config_has_risk_exit_disabled(hypothesis_config):
    assert hypothesis_config.data["risk_exit"]["enabled"] is False


def test_validator_rejects_when_config_risk_exit_enabled_is_tampered(discovery_config, hypothesis_config, monkeypatch):
    tampered = dict(hypothesis_config.data)
    tampered["risk_exit"] = {"enabled": True}
    from dataclasses import replace
    tampered_config = replace(hypothesis_config, data=tampered)
    proposal = normalize_proposal(make_proposal_raw())
    result = validate_proposal(proposal, discovery_config, tampered_config)
    assert not result.valid
    assert any("risk_exit" in e for e in result.errors)
