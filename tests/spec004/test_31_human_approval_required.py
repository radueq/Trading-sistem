"""TEST 31 -- an explicit, non-empty human_decision is required before
PREREGISTERED (Spec #004 SS46)."""
from hypothesis.consensus.consensus import can_preregister, compute_consensus


def test_empty_human_decision_is_rejected():
    record = compute_consensus("p", (), human_decision="   ")
    ok, errors = can_preregister(record)
    assert not ok
    assert errors


def test_explicit_human_decision_allows_preregistration():
    record = compute_consensus("p", (), human_decision="Approved by Radu 2026-09-25")
    ok, errors = can_preregister(record)
    assert ok, errors
