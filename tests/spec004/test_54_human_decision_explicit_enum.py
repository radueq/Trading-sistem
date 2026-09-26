"""TEST 54 -- HumanDecision is an explicit APPROVE/REJECT contract, not
free text used as a boolean (PATCH #004-A finding #1, GPT Review #004
Round 1). The original `can_preregister()` accepted ANY non-empty
string, including "REJECT", "NU SUNT DE ACORD", and "NO" -- because
non-emptiness alone was treated as approval. This reproduces exactly
those three strings against the FIXED contract and confirms all three
are correctly rejected once expressed as `HumanDecisionValue.REJECT`
(and that REJECT is a normal, legitimate outcome that survives, not a
formatting error)."""
from hypothesis.consensus.consensus import can_preregister, compute_consensus
from hypothesis.models.entities import HumanDecision, HumanDecisionValue


def test_reject_decision_with_any_rationale_text_is_never_treated_as_approval():
    for rationale in ("REJECT", "NU SUNT DE ACORD", "NO", ""):
        record = compute_consensus("p", (), human_decision=HumanDecision(
            decision=HumanDecisionValue.REJECT.value, decided_by="radu", decided_at="t", rationale=rationale,
        ))
        ok, errors = can_preregister(record)
        assert not ok, f"rationale={rationale!r} must never pass the gate just because it is non-empty text"
        assert errors


def test_only_the_literal_approve_value_passes():
    record = compute_consensus("p", (), human_decision=HumanDecision(
        decision=HumanDecisionValue.APPROVE.value, decided_by="radu", decided_at="t",
    ))
    ok, errors = can_preregister(record)
    assert ok, errors


def test_human_decision_is_a_structured_dataclass_not_a_bare_string():
    import dataclasses
    assert dataclasses.is_dataclass(HumanDecision)
    field_names = {f.name for f in dataclasses.fields(HumanDecision)}
    assert {"decision", "decided_by", "decided_at"} <= field_names
