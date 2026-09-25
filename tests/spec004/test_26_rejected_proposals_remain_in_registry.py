"""TEST 26 -- rejected proposals remain visible in the registry, never
deleted (Spec #004 SS53/SS55)."""
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.registry.hypotheses import HypothesisRegistry

from spec004.conftest import make_proposal_raw


def test_rejected_proposal_is_retrievable_and_marked(registry):
    proposal = normalize_proposal(make_proposal_raw(proposal_id="prop_rejected"))
    registry.register_proposal(proposal)
    registry.mark_proposal_rejected("prop_rejected")

    assert proposal in registry.all_proposals()
    assert "prop_rejected" in registry.rejected_proposal_ids()


def test_marking_an_unregistered_proposal_rejected_fails_loudly():
    reg = HypothesisRegistry()
    try:
        reg.mark_proposal_rejected("never_registered")
        assert False, "expected ValueError"
    except ValueError:
        pass
