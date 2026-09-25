"""TEST 7 -- an indicator/lane not defined by #002 (e.g. `RSI_7 > 63.4`,
Spec #004 SS11's own forbidden example) is rejected, never silently
accepted as a new feature."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal

from spec004.conftest import make_proposal_raw


def test_rsi_7_style_unapproved_indicator_is_rejected(discovery_config, hypothesis_config):
    raw = make_proposal_raw(entry_definition={"core_conditions": [{"lane": "RSI_7", "label": "HIGH"}]})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("RSI_7" in e and "not an approved" in e for e in result.errors)


def test_unknown_reason_code_is_rejected(discovery_config, hypothesis_config):
    raw = make_proposal_raw(entry_definition={"core_conditions": [{"reason_code": "MADE_UP_SIGNAL"}]})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("MADE_UP_SIGNAL" in e for e in result.errors)
