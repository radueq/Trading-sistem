"""TEST 31 -- an explicit HumanDecision(decision=APPROVE) is required
before PREREGISTERED (Spec #004 SS46). PATCH #004-A finding #1: no
`human_decision` at all is rejected exactly like a REJECT decision --
see TEST 54 for the free-text-as-boolean bug this replaced."""
from hypothesis.consensus.consensus import can_preregister, compute_consensus

from spec004.conftest import approved_human_decision


def test_no_human_decision_is_rejected():
    record = compute_consensus("p", (), human_decision=None)
    ok, errors = can_preregister(record)
    assert not ok
    assert errors


def test_explicit_approve_human_decision_allows_preregistration():
    record = compute_consensus("p", (), human_decision=approved_human_decision())
    ok, errors = can_preregister(record)
    assert ok, errors
