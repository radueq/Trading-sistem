"""TEST 29 -- AgentReview supports exactly SUPPORT/OBJECT/ABSTAIN, and
OBJECT requires at least one objection (Spec #004 SS44)."""
from hypothesis.consensus.reviews import validate_review
from hypothesis.models.entities import AgentReview


def _review(stance, objections=()):
    return AgentReview(agent_id="a", model_id="m", hypothesis_proposal_id="p", stance=stance, objections=objections, suggested_changes=(), timestamp="t")


def test_support_and_abstain_are_valid_without_objections():
    assert validate_review(_review("SUPPORT"))[0]
    assert validate_review(_review("ABSTAIN"))[0]


def test_object_without_objections_is_invalid():
    ok, errors = validate_review(_review("OBJECT"))
    assert not ok
    assert errors


def test_object_with_objections_is_valid():
    ok, errors = validate_review(_review("OBJECT", objections=("support/concentration too low",)))
    assert ok, errors


def test_unrecognized_stance_is_invalid():
    ok, _ = validate_review(_review("MAYBE"))
    assert not ok
