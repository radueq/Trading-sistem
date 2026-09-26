"""TEST 5 -- calendar-input contract and fail-closed gate (Spec #005
v1.0 SS11/SS24, Batch 1). A session calendar is a separate, verified,
versioned input -- never inferred from price data. A formal run without
one fails closed."""
import pytest

from backtest.data.calendar import (
    build_trading_calendar,
    is_session,
    require_calendar_covers_window,
    require_verified_calendar_for_formal_run,
)
from backtest.models.entities import CalendarCoverageIncompleteError, CalendarNotVerifiedError, CalendarSource

_SESSION_DATES = ("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08")


def _verified_calendar(**overrides):
    defaults = dict(
        source=CalendarSource.OFFICIAL_VERIFIED.value, calendar_identifier="NYSE_NASDAQ_COMPOSITE",
        calendar_version="v1", market="US_EQUITIES", timezone="America/New_York",
        coverage_start="2024-01-01", coverage_end="2024-01-31", session_dates=_SESSION_DATES,
        session_open_time="09:30", session_close_time="16:00",
        verified_by="radu", verified_at="2026-09-26T00:00:00Z",
    )
    defaults.update(overrides)
    return build_trading_calendar(**defaults)


def test_verified_calendar_passes_the_formal_run_gate():
    calendar = _verified_calendar()
    require_verified_calendar_for_formal_run(calendar)  # must not raise


def test_synthetic_fixture_calendar_is_rejected_for_a_formal_run():
    calendar = _verified_calendar(source=CalendarSource.SYNTHETIC_TEST_FIXTURE.value, verified_by=None, verified_at=None)
    with pytest.raises(CalendarNotVerifiedError, match="CALENDAR_UNVERIFIED"):
        require_verified_calendar_for_formal_run(calendar)


def test_official_source_missing_verification_provenance_is_rejected():
    """source=OFFICIAL_VERIFIED alone is not enough -- verified_by/
    verified_at must actually be recorded (SS11)."""
    calendar = _verified_calendar(verified_by=None, verified_at=None)
    with pytest.raises(CalendarNotVerifiedError, match="CALENDAR_UNVERIFIED"):
        require_verified_calendar_for_formal_run(calendar)


def test_window_fully_within_coverage_passes():
    calendar = _verified_calendar()
    require_calendar_covers_window(calendar, "2024-01-02", "2024-01-10")  # must not raise


def test_window_extending_past_coverage_end_fails_closed():
    calendar = _verified_calendar()
    with pytest.raises(CalendarCoverageIncompleteError, match="CALENDAR_COVERAGE_INCOMPLETE"):
        require_calendar_covers_window(calendar, "2024-01-02", "2024-06-01")


def test_window_starting_before_coverage_start_fails_closed():
    calendar = _verified_calendar()
    with pytest.raises(CalendarCoverageIncompleteError, match="CALENDAR_COVERAGE_INCOMPLETE"):
        require_calendar_covers_window(calendar, "2023-12-01", "2024-01-10")


def test_calendar_decides_session_status_not_any_price_series():
    """The contract property SS11 exists to enforce: `is_session()`
    takes ONLY the calendar -- there is no price-series parameter it
    could consult instead. A date the calendar declares a session stays
    one, structurally, regardless of what any security's own bars show."""
    calendar = _verified_calendar()
    assert is_session(calendar, "2024-01-03") is True
    assert is_session(calendar, "2024-01-06") is False  # a Saturday, correctly absent
    assert is_session(calendar, "2024-01-01") is False  # New Year's Day, a real holiday absent from session_dates
