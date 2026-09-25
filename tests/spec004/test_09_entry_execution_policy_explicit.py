"""TEST 9 -- entry_execution_policy must be an explicit, allowed value
(Spec #004 SS14-16, Radu's SS110-A: frozen as NEXT_BAR_OPEN, the only V1
value) -- never left implicit or freely chosen per proposal."""
from hypothesis.models.entities import ENTRY_EXECUTION_POLICY
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal

from spec004.conftest import make_proposal_raw


def test_next_bar_open_is_the_only_allowed_entry_execution(discovery_config, hypothesis_config):
    assert ENTRY_EXECUTION_POLICY == "NEXT_BAR_OPEN"
    assert hypothesis_config.data["allowed_entry_execution"] == ["NEXT_BAR_OPEN"]


def test_other_entry_execution_values_are_rejected(discovery_config, hypothesis_config):
    raw = make_proposal_raw(entry_execution_policy="SAME_BAR_CLOSE")
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("entry_execution_policy" in e for e in result.errors)
