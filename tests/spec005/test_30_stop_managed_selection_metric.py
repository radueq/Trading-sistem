"""TEST 30 -- MEDIAN_NET_RETURN_TO_EXIT_OR_STAGE_END and the selection
ratios (docs/spec005_exit_amendment_v1.0.md, ACCEPTED, section 11),
including the exact selection-bias scenario the metric was designed to
counter: excluding still-open (censored) positions from ranking lets a
variant win by hiding its worst trades as "still open"."""
import pytest

from backtest.exits.entities import (
    EVALUABILITY_EVALUABLE,
    EVALUABILITY_UNEVALUABLE,
    LIFECYCLE_CENSORED_AT_HORIZON,
    LIFECYCLE_CLOSED,
    LIFECYCLE_EXIT_FAILED,
    REASON_NO_EXIT_BAR,
    PositionOutcome,
)
from backtest.exits.taxonomy import censored_ratio, evaluable_ratio, median_net_return_to_exit_or_stage_end


def _closed(net_return: float) -> PositionOutcome:
    return PositionOutcome(LIFECYCLE_CLOSED, EVALUABILITY_EVALUABLE, None, net_return=net_return)


def _censored(net_return: float) -> PositionOutcome:
    return PositionOutcome(LIFECYCLE_CENSORED_AT_HORIZON, EVALUABILITY_EVALUABLE, None, net_return=net_return)


def _exit_failed() -> PositionOutcome:
    return PositionOutcome(LIFECYCLE_EXIT_FAILED, EVALUABILITY_UNEVALUABLE, REASON_NO_EXIT_BAR, net_return=None)


def test_median_over_closed_only_would_be_biased_and_the_new_metric_corrects_it():
    """Variant B: 2 closed trades at +2%, plus 2 censored (still-open,
    but evaluable) trades at -50% each. A closed-only median would
    report +2% -- hiding the two badly-losing open positions entirely.
    The mandatory metric includes them and correctly reports -24%."""
    variant_b_outcomes = [_closed(0.02), _closed(0.02), _censored(-0.50), _censored(-0.50)]

    closed_only_median = sorted(o.net_return for o in variant_b_outcomes if o.lifecycle == LIFECYCLE_CLOSED)
    naive_median = closed_only_median[len(closed_only_median) // 2]
    assert naive_median == pytest.approx(0.02)  # the biased figure a closed-only approach would report

    correct_median = median_net_return_to_exit_or_stage_end(variant_b_outcomes)
    assert correct_median == pytest.approx(-0.24)  # (-0.50 + 0.02) / 2, the two middle values once sorted


def test_exit_failed_positions_are_always_excluded_from_the_metric():
    outcomes = [_closed(0.01), _closed(0.02), _exit_failed()]
    assert median_net_return_to_exit_or_stage_end(outcomes) == pytest.approx(0.015)


def test_odd_count_median_is_the_middle_value():
    outcomes = [_closed(0.01), _censored(0.05), _closed(0.03)]
    assert median_net_return_to_exit_or_stage_end(outcomes) == pytest.approx(0.03)


def test_no_evaluable_positions_returns_none():
    assert median_net_return_to_exit_or_stage_end([_exit_failed()]) is None
    assert median_net_return_to_exit_or_stage_end([]) is None


def test_censored_ratio_and_evaluable_ratio_denominators_include_exit_failed():
    outcomes = [_closed(0.01), _censored(0.02), _censored(-0.10), _exit_failed()]
    assert censored_ratio(outcomes) == pytest.approx(2 / 4)
    assert evaluable_ratio(outcomes) == pytest.approx(3 / 4)  # exit_failed is never evaluable


def test_empty_executed_entries_ratios_are_undefined():
    assert censored_ratio([]) is None
    assert evaluable_ratio([]) is None
