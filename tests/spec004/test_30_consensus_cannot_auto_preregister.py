"""TEST 30 -- consensus_status alone can never move a proposal to
PREREGISTERED, regardless of how strong the agreement is (Spec #004
SS45-46)."""
from hypothesis.consensus.consensus import can_preregister, compute_consensus
from hypothesis.models.entities import AgentReview, ConsensusStatus


def test_unanimous_support_without_human_decision_cannot_preregister():
    reviews = (
        AgentReview("a", "m", "p", "SUPPORT", (), (), "t1"),
        AgentReview("b", "m", "p", "SUPPORT", (), (), "t2"),
    )
    record = compute_consensus("p", reviews, human_decision=None)
    assert record.consensus_status == ConsensusStatus.CONSENSUS.value
    ok, errors = can_preregister(record)
    assert not ok
    assert errors
