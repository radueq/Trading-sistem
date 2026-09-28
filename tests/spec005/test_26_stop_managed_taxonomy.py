"""TEST 26 -- the three-facet taxonomy for STOP_MANAGED_INVALIDATION
(docs/spec005_exit_amendment_v1.0.md, ACCEPTED, section 10), including
section 13's behavioral regressions 7-11."""
from backtest.exits.entities import (
    EVALUABILITY_EVALUABLE,
    EVALUABILITY_UNEVALUABLE,
    EXIT_REASON_STOP,
    EXIT_REASON_TARGET,
    LIFECYCLE_CENSORED_AT_HORIZON,
    LIFECYCLE_CLOSED,
    LIFECYCLE_EXIT_FAILED,
    REASON_CENSORED_MARK_UNAVAILABLE,
    REASON_INVALIDATION_PATH_INCOMPLETE,
    REASON_NO_EXIT_BAR,
    StopManagedPosition,
    Tranche,
)
from backtest.exits.session import advance_intrabar, check_trend_invalidation, execute_scheduled_invalidation
from backtest.exits.taxonomy import classify_position


def _base_position(**overrides) -> StopManagedPosition:
    fields = dict(
        security_id="SEC_X", direction="LONG", entry_date="2024-01-11", signal_date="2024-01-10",
        entry_fill_price=100.0, k=2.0, r_multiple=2.0, fraction=0.5,
        active_stop=90.0, initial_risk=10.0, target_price=120.0,
    )
    fields.update(overrides)
    return StopManagedPosition(**fields)


def test_closed_with_no_incompleteness_is_evaluable():
    pos = _base_position(closed=True, close_tranche=Tranche("REMAINDER", EXIT_REASON_STOP, 1.0, "2024-01-12", 90.0, 1, entry_fill_price_reference=100.0))
    outcome = classify_position(pos, stage_end_reached=False)
    assert outcome.lifecycle == LIFECYCLE_CLOSED
    assert outcome.evaluability == EVALUABILITY_EVALUABLE
    assert outcome.reason is None


def test_exit_failed_is_always_uneval_no_exit_bar():
    pos = _base_position(exit_failed=True)
    outcome = classify_position(pos, stage_end_reached=True)
    assert outcome.lifecycle == LIFECYCLE_EXIT_FAILED
    assert outcome.evaluability == EVALUABILITY_UNEVALUABLE
    assert outcome.reason == REASON_NO_EXIT_BAR


def test_regression_7_partial_executed_rest_censored_is_evaluable_w_is_fraction():
    """Section 13 regression #7: partial profit realized, remainder still
    active at stage end -> CENSORED_AT_HORIZON, EVALUABLE, w = fraction."""
    partial = Tranche("PARTIAL_PROFIT", EXIT_REASON_TARGET, 0.5, "2024-01-13", 120.0, 2, entry_fill_price_reference=100.0)
    pos = _base_position(target_consumed=True, partial_tranche=partial, remaining_quantity=0.5)
    outcome = classify_position(pos, stage_end_reached=True, final_mark_available=True)
    assert outcome.lifecycle == LIFECYCLE_CENSORED_AT_HORIZON
    assert outcome.evaluability == EVALUABILITY_EVALUABLE

    from backtest.exits.costs import compute_w
    assert compute_w(pos) == 0.5


def test_regression_8_control_variant_censored_w_is_zero():
    """Section 13 regression #8: Control (no partial_profit) still active
    at stage end -> CENSORED_AT_HORIZON, w=0, result = rest only."""
    pos = _base_position(fraction=None, target_price=None, r_multiple=None)
    outcome = classify_position(pos, stage_end_reached=True, final_mark_available=True)
    assert outcome.lifecycle == LIFECYCLE_CENSORED_AT_HORIZON
    assert outcome.evaluability == EVALUABILITY_EVALUABLE

    from backtest.exits.costs import compute_w, aggregate_position_return
    w = compute_w(pos)
    assert w == 0.0
    assert aggregate_position_return(w, partial_return=None, rest_return=0.03) == 0.03


def test_regression_9_invalidation_pending_next_stage_is_censored_not_exit_failed():
    """Section 13 regression #9: invalidation detected at the stage's
    LAST close, fill due next stage -> CENSORED_AT_HORIZON (never
    EXIT_FAILED), pending_exit_note recorded, next stage's open never read."""
    pos = _base_position()
    pos = check_trend_invalidation(pos, "2024-01-31", "INVALIDATED")  # last session of the stage
    assert pos.pending_invalidation_detected_date == "2024-01-31"

    # The fill would be due 2024-02-01, but the stage ends 2024-01-31.
    pos = execute_scheduled_invalidation(pos, next_session_date="2024-02-01", next_session_open_price=95.0, stage_end_date="2024-01-31")
    assert pos.closed is False
    assert pos.pending_exit_note is not None
    assert "2024-02-01" in pos.pending_exit_note

    outcome = classify_position(pos, stage_end_reached=True, final_mark_available=True)
    assert outcome.lifecycle == LIFECYCLE_CENSORED_AT_HORIZON
    assert outcome.evaluability == EVALUABILITY_EVALUABLE


def test_due_in_stage_invalidation_with_missing_open_is_exit_failed():
    pos = _base_position()
    pos = check_trend_invalidation(pos, "2024-01-30", "INVALIDATED")
    pos = execute_scheduled_invalidation(pos, next_session_date="2024-01-31", next_session_open_price=None, stage_end_date="2024-01-31")
    assert pos.exit_failed is True
    outcome = classify_position(pos, stage_end_reached=True)
    assert outcome.lifecycle == LIFECYCLE_EXIT_FAILED


def test_due_in_stage_invalidation_with_available_open_closes_normally():
    pos = _base_position()
    pos = check_trend_invalidation(pos, "2024-01-30", "INVALIDATED")
    pos = execute_scheduled_invalidation(pos, next_session_date="2024-01-31", next_session_open_price=95.0, stage_end_date="2024-01-31")
    assert pos.closed is True
    assert pos.close_tranche.exit_fill_price == 95.0
    outcome = classify_position(pos, stage_end_reached=False)
    assert outcome.lifecycle == LIFECYCLE_CLOSED
    assert outcome.evaluability == EVALUABILITY_EVALUABLE


def test_regression_10_unknown_taint_persists_after_valid_observations_and_normal_close():
    """Section 13 regression #10: one UNKNOWN observation while active,
    followed by valid observations and a normal close, still leaves the
    position INVALIDATION_PATH_INCOMPLETE, UNEVALUABLE -- the return of
    valid observations does not repair the earlier gap."""
    pos = _base_position()
    pos = check_trend_invalidation(pos, "2024-01-15", "UNKNOWN")
    assert pos.invalidation_path_incomplete is True

    pos = check_trend_invalidation(pos, "2024-01-16", "VALID_HOLD")
    assert pos.invalidation_path_incomplete is True  # never cleared

    pos, _ = advance_intrabar(pos, "2024-01-17", open_price=100.0, high=105.0, low=85.0)  # stop hit, normal close
    assert pos.closed is True

    outcome = classify_position(pos, stage_end_reached=False)
    assert outcome.lifecycle == LIFECYCLE_CLOSED
    assert outcome.evaluability == EVALUABILITY_UNEVALUABLE
    assert outcome.reason == REASON_INVALIDATION_PATH_INCOMPLETE


def test_regression_11_fully_closed_at_pas3prime_skips_invalidation_check():
    """Section 13 regression #11: a position closed COMPLETELY at Pas 3'
    (stop on the whole quantity) triggers no invalidation evaluation for
    that same day -- never a false INVALIDATION_PATH_INCOMPLETE from an
    inapplicable check, even if the caller (mistakenly or not) still
    calls check_trend_invalidation with UNKNOWN afterward."""
    pos = _base_position()
    pos, _ = advance_intrabar(pos, "2024-01-12", open_price=85.0, high=86.0, low=84.0)
    assert pos.closed is True

    pos = check_trend_invalidation(pos, "2024-01-12", "UNKNOWN")
    assert pos.invalidation_path_incomplete is False  # skipped entirely -- no-op on a closed position

    outcome = classify_position(pos, stage_end_reached=False)
    assert outcome.evaluability == EVALUABILITY_EVALUABLE


def test_censored_with_no_final_mark_is_uneval():
    pos = _base_position()
    outcome = classify_position(pos, stage_end_reached=True, final_mark_available=False)
    assert outcome.lifecycle == LIFECYCLE_CENSORED_AT_HORIZON
    assert outcome.evaluability == EVALUABILITY_UNEVALUABLE
    assert outcome.reason == REASON_CENSORED_MARK_UNAVAILABLE


def test_classify_unclosed_before_stage_end_raises():
    import pytest
    pos = _base_position()
    with pytest.raises(ValueError):
        classify_position(pos, stage_end_reached=False)
