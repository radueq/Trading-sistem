"""TEST 18 -- Evidence/outcome fields (adjusted_p, forward_return,
mean_return, win_rate, ...) can never appear as a runtime entry/exit
signal condition (Spec #004 SS72 -- the outcome contamination rule)."""
from hypothesis.models.entities import LaneStateCondition
from hypothesis.validation.rules import FORBIDDEN_OUTCOME_FIELD_NAMES, _scan_condition_for_outcome_contamination


def test_forbidden_outcome_field_list_covers_the_spec_examples():
    for token in ("adjusted_p", "forward_return", "mean_return", "win_rate"):
        assert token in FORBIDDEN_OUTCOME_FIELD_NAMES


def test_condition_using_an_outcome_field_as_a_lane_is_flagged():
    errors: list[str] = []
    bad = LaneStateCondition(lane="adjusted_p", label="LOW")
    _scan_condition_for_outcome_contamination(bad, "entry_definition", errors)
    assert errors, "an outcome field used as a lane name must be flagged"
