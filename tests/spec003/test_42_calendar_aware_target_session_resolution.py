"""TEST 42 -- calendar-aware target-session resolution (joint
remediation design 003+004, section 1.3; decision registry B1-B2,
revision 5-6; authorized 2026-10-06, Stage 2).

`compute_forward_outcome()`'s NEW, OPTIONAL `calendar=` parameter
resolves `T_target` from a `TradingCalendar`'s own `session_dates`
instead of a bar position, following the four-way check in its own
stated order: calendar-insufficient (checked first, no price read) ->
Locked-OOS -> not-yet-reached -> data-gap/valid (price read only now,
bounded to a date already proven <= effective_as_of). Omitting
`calendar` (the default, `None`) must leave every existing bar-position
behavior completely unchanged -- covered by test_01/test_41, not
repeated here.
"""
import pytest

from data_foundation.calendar.contract import build_trading_calendar
from data_foundation.calendar.entities import CalendarSource
from evaluation.models.entities import OutcomeStatus
from evaluation.outcomes.forward_returns import compute_forward_outcome


class Bar:
    def __init__(self, date, close):
        self.date, self.split_adjusted_close = date, close


_SESSIONS = ("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05")


def _calendar(session_dates=_SESSIONS):
    return build_trading_calendar(
        source=CalendarSource.SYNTHETIC_TEST_FIXTURE.value, calendar_identifier="TEST_FIXTURE",
        calendar_version="v1", market="US_EQUITIES", timezone="America/New_York",
        coverage_start="2024-01-01", coverage_end="2024-01-31", session_dates=session_dates,
        session_open_time="09:30", session_close_time="16:00",
    )


def test_t_entry_absent_from_calendar_is_invalid_input():
    calendar = _calendar()
    bars = [Bar("2023-12-29", 100.0), Bar("2024-01-02", 101.0)]
    o = compute_forward_outcome(
        "sid", bars, "2023-12-29", "1D", 1, None, "cfg_x", calendar=calendar,
    )
    assert o.outcome_status == OutcomeStatus.INVALID_INPUT.value
    assert o.forward_return is None


def test_target_index_past_end_of_calendar_session_list_is_invalid_input():
    calendar = _calendar()  # only 4 sessions
    bars = [Bar(d, 100.0) for d in _SESSIONS]
    o = compute_forward_outcome(
        "sid", bars, "2024-01-05", "1D", 1, None, "cfg_x", calendar=calendar,
    )
    assert o.outcome_status == OutcomeStatus.INVALID_INPUT.value
    assert o.forward_return is None


def test_target_present_in_calendar_but_security_bar_missing_is_data_gap():
    """4a -- the calendar says 2024-01-04 IS a session, but this
    security's own bar series has no bar dated exactly that day."""
    calendar = _calendar()
    bars = [Bar("2024-01-02", 100.0), Bar("2024-01-05", 110.0)]  # 01-03/01-04 missing
    o = compute_forward_outcome(
        "sid", bars, "2024-01-02", "1D", 2, None, "cfg_x", calendar=calendar,
    )
    assert o.outcome_status == OutcomeStatus.DATA_GAP.value
    assert o.forward_return is None
    assert o.exit_reference_price is None


def test_target_bar_present_with_none_price_is_data_gap():
    """4b -- a bar exists at T_target but its own price field is None."""
    calendar = _calendar()
    bars = [Bar("2024-01-02", 100.0), Bar("2024-01-03", None), Bar("2024-01-04", 102.0)]
    o = compute_forward_outcome(
        "sid", bars, "2024-01-02", "1D", 1, None, "cfg_x", calendar=calendar,
    )
    assert o.outcome_status == OutcomeStatus.DATA_GAP.value
    assert o.forward_return is None


def test_target_beyond_development_end_is_crosses_locked_oos():
    calendar = _calendar()
    bars = [Bar(d, 100.0 + i) for i, d in enumerate(_SESSIONS)]
    o = compute_forward_outcome(
        "sid", bars, "2024-01-02", "1D", 2, "2024-01-03", "cfg_x", calendar=calendar,
    )
    assert o.outcome_status == OutcomeStatus.CROSSES_LOCKED_OOS.value
    assert o.forward_return is None
    assert o.exit_reference_price is None


def test_target_beyond_data_as_of_but_within_development_end_is_insufficient_future_data():
    calendar = _calendar()
    bars = [Bar(d, 100.0 + i) for i, d in enumerate(_SESSIONS)]
    o = compute_forward_outcome(
        "sid", bars, "2024-01-02", "1D", 2, "2024-01-31", "cfg_x",
        calendar=calendar, data_as_of="2024-01-03",
    )
    assert o.outcome_status == OutcomeStatus.INSUFFICIENT_FUTURE_DATA.value
    assert o.forward_return is None


def test_valid_calendar_resolved_outcome():
    calendar = _calendar()
    bars = [Bar("2024-01-02", 100.0), Bar("2024-01-03", 105.0), Bar("2024-01-04", 110.0)]
    o = compute_forward_outcome(
        "sid", bars, "2024-01-02", "1D", 2, "2024-01-31", "cfg_x",
        calendar=calendar, data_as_of="2024-01-31",
    )
    assert o.outcome_status == OutcomeStatus.VALID.value
    assert o.exit_as_of == "2024-01-04"
    assert o.exit_reference_price == 110.0
    assert o.entry_reference_price == 100.0
    assert o.forward_return == pytest.approx(0.1)


def test_entry_bar_missing_from_security_series_despite_calendar_entry_is_invalid_input():
    """T_entry IS a calendar session, but this security has no bar at
    all on that exact date -- the existing entry-resolution check
    (unchanged) still applies within the calendar-aware path."""
    calendar = _calendar()
    bars = [Bar("2024-01-03", 100.0), Bar("2024-01-04", 101.0)]  # no 2024-01-02 bar
    o = compute_forward_outcome(
        "sid", bars, "2024-01-02", "1D", 1, None, "cfg_x", calendar=calendar,
    )
    assert o.outcome_status == OutcomeStatus.INVALID_INPUT.value


def test_entry_price_non_finite_is_invalid_input_in_calendar_path():
    calendar = _calendar()
    bars = [Bar("2024-01-02", float("nan")), Bar("2024-01-03", 101.0)]
    o = compute_forward_outcome(
        "sid", bars, "2024-01-02", "1D", 1, None, "cfg_x", calendar=calendar,
    )
    assert o.outcome_status == OutcomeStatus.INVALID_INPUT.value


def test_target_price_non_finite_is_invalid_input_not_data_gap_in_calendar_path():
    """Stage 1's numeric-validity check (J1) applies equally in the
    calendar-aware path -- a present-but-non-finite price is a
    different failure mode than an absent one, never folded into
    DATA_GAP."""
    calendar = _calendar()
    bars = [Bar("2024-01-02", 100.0), Bar("2024-01-03", -5.0)]
    o = compute_forward_outcome(
        "sid", bars, "2024-01-02", "1D", 1, None, "cfg_x", calendar=calendar,
    )
    assert o.outcome_status == OutcomeStatus.INVALID_INPUT.value


def test_omitting_calendar_keeps_legacy_bar_position_result_unchanged():
    """Same inputs, run once with the new calendar path and once
    without -- for a case where both agree, confirming the new
    parameter is purely additive, not a silent behavior change."""
    calendar = _calendar()
    bars = [Bar("2024-01-02", 100.0), Bar("2024-01-03", 105.0), Bar("2024-01-04", 110.0)]
    legacy = compute_forward_outcome("sid", bars, "2024-01-02", "1D", 2, "2024-01-31", "cfg_x")
    calendar_aware = compute_forward_outcome(
        "sid", bars, "2024-01-02", "1D", 2, "2024-01-31", "cfg_x",
        calendar=calendar, data_as_of="2024-01-31",
    )
    assert legacy.outcome_status == calendar_aware.outcome_status == OutcomeStatus.VALID.value
    assert legacy.forward_return == calendar_aware.forward_return
    assert legacy.exit_as_of == calendar_aware.exit_as_of
