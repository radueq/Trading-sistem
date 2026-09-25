"""TEST 32 -- disagreement among reviewers is preserved in the
ConsensusRecord, never silently resolved by majority (Spec #004 SS43-45)."""
from hypothesis.consensus.consensus import compute_consensus
from hypothesis.models.entities import AgentReview, ConsensusStatus


def test_mixed_support_and_object_is_disagreement_with_objections_kept():
    reviews = (
        AgentReview("a", "m", "p", "SUPPORT", (), (), "t1"),
        AgentReview("b", "m", "p", "OBJECT", ("support is marginal, concentration high",), (), "t2"),
    )
    record = compute_consensus("p", reviews)
    assert record.consensus_status == ConsensusStatus.DISAGREEMENT.value
    assert "support is marginal, concentration high" in record.unresolved_objections


def test_all_objecting_is_blocked_not_disagreement():
    reviews = (
        AgentReview("a", "m", "p", "OBJECT", ("no economic rationale",), (), "t1"),
        AgentReview("b", "m", "p", "OBJECT", ("temporal concentration",), (), "t2"),
    )
    record = compute_consensus("p", reviews)
    assert record.consensus_status == ConsensusStatus.BLOCKED.value
    assert len(record.unresolved_objections) == 2
