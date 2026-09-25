"""TEST 8 -- max_entry_conditions / max_optional_confirmation_conditions
are enforced, never silently truncated (Spec #004 SS12/SS107)."""
from hypothesis.models.entities import ComplexityStatus
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal

from spec004.conftest import make_proposal_raw


def test_entry_within_budget_is_accepted(discovery_config, hypothesis_config):
    raw = make_proposal_raw(entry_definition={"core_conditions": [
        {"lane": "volatility", "label": "COMPRESSION"}, {"lane": "relative_strength", "label": "VERY_HIGH"},
    ]})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert result.valid
    assert result.complexity_status == ComplexityStatus.OK.value


def test_entry_over_budget_is_rejected_with_complexity_status(discovery_config, hypothesis_config):
    over_budget = [{"lane": "volatility", "label": "COMPRESSION"}] * (
        hypothesis_config.data["hypothesis_complexity"]["max_entry_conditions"] + 1
    )
    raw = make_proposal_raw(entry_definition={"core_conditions": over_budget})
    proposal = normalize_proposal(raw)
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert result.complexity_status == ComplexityStatus.HYPOTHESIS_COMPLEXITY_EXCEEDED.value
