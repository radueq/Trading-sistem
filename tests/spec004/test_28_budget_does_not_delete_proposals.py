"""TEST 28 -- exceeding the hypothesis budget rejects the NEW hypothesis
but never deletes the ones already registered, nor silently prunes the
proposal record (Spec #004 SS53/SS107)."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.registry.hypotheses import HypothesisRegistry

from spec004.conftest import make_proposal_raw


def test_registering_a_proposal_after_budget_rejection_keeps_all_prior_entries(registry):
    for i in range(3):
        proposal = normalize_proposal(make_proposal_raw(proposal_id=f"prop_{i}"))
        registry.register_proposal(proposal)

    over_budget_proposal = normalize_proposal(make_proposal_raw(proposal_id="prop_over_budget"))
    registry.register_proposal(over_budget_proposal)
    registry.mark_proposal_rejected("prop_over_budget")

    assert len(registry.all_proposals()) == 4
    assert "prop_over_budget" in registry.rejected_proposal_ids()
    for i in range(3):
        assert f"prop_{i}" not in registry.rejected_proposal_ids()
