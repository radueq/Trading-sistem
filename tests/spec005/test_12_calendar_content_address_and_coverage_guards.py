"""TEST 12 -- calendar content-address re-verification and coverage
guards (Spec #005 v1.0 SS11/SS21, Batch 1 patch).

GPT Batch 1 review (P1 finding #1): `dataclasses.replace()` on a
TradingCalendar to drop a session date passed
`require_verified_calendar_for_formal_run()` because `calendar_id`/
`calendar_hash` are stored fields, never recomputed at gate time --
`frozen=True` blocks in-place mutation, not this. Also, `is_session()`
returned False both for a genuine non-session and for a date outside
the calendar's declared coverage, conflating "unknown" with "verified
non-session".
"""
import dataclasses

import pytest

from backtest.data.calendar import build_trading_calendar, is_session, require_calendar_covers_window, require_verified_calendar_for_formal_run
from backtest.models.entities import (
    CalendarCoverageIncompleteError,
    CalendarNotVerifiedError,
    CalendarSource,
    verify_calendar_content_address,
    verify_calendar_structure,
)

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


def test_tampered_calendar_fails_content_address_verification():
    calendar = _verified_calendar()
    tampered = dataclasses.replace(calendar, session_dates=tuple(d for d in calendar.session_dates if d != "2024-01-03"))
    ok, errors = verify_calendar_content_address(tampered)
    assert not ok
    assert any("content-address mismatch" in e for e in errors)


def test_tampered_calendar_is_rejected_at_the_formal_run_gate():
    """The exact bug GPT reproduced: a dataclasses.replace()-tampered
    calendar (session date dropped, old id/hash kept) must never pass
    require_verified_calendar_for_formal_run()."""
    calendar = _verified_calendar()
    tampered = dataclasses.replace(calendar, session_dates=tuple(d for d in calendar.session_dates if d != "2024-01-03"))
    with pytest.raises(CalendarNotVerifiedError, match="CALENDAR_UNVERIFIED"):
        require_verified_calendar_for_formal_run(tampered)


def test_untampered_calendar_passes_content_address_verification():
    calendar = _verified_calendar()
    ok, errors = verify_calendar_content_address(calendar)
    assert ok, errors


def test_reversed_coverage_is_rejected_by_structure_check():
    calendar = _verified_calendar(coverage_start="2024-01-31", coverage_end="2024-01-01")
    ok, errors = verify_calendar_structure(calendar)
    assert not ok
    assert any("is after coverage_end" in e for e in errors)


def test_session_date_outside_declared_coverage_is_rejected_by_structure_check():
    calendar = _verified_calendar(session_dates=_SESSION_DATES + ("2024-06-01",))
    ok, errors = verify_calendar_structure(calendar)
    assert not ok
    assert any("falls outside declared coverage" in e for e in errors)


def test_duplicate_session_dates_are_rejected_by_structure_check():
    calendar = dataclasses.replace(_verified_calendar(), session_dates=_SESSION_DATES + ("2024-01-02",))
    ok, errors = verify_calendar_structure(calendar)
    assert not ok
    assert any("duplicate" in e for e in errors)


def test_is_session_raises_for_a_date_outside_declared_coverage():
    """Out-of-coverage is UNKNOWN, not a verified non-session -- must
    raise, never silently return False."""
    calendar = _verified_calendar()
    with pytest.raises(CalendarCoverageIncompleteError, match="CALENDAR_COVERAGE_INCOMPLETE"):
        is_session(calendar, "2024-06-01")


def test_is_session_still_returns_false_for_a_genuine_non_session_within_coverage():
    calendar = _verified_calendar()
    assert is_session(calendar, "2024-01-06") is False  # a Saturday, within coverage


def test_require_calendar_covers_window_rejects_a_reversed_window():
    """GPT Batch 1 review (P2 finding): require_calendar_covers_window()
    never checked window_start <= window_end before comparing against
    coverage bounds, so a reversed window could vacuously pass."""
    calendar = _verified_calendar()
    with pytest.raises(CalendarCoverageIncompleteError, match="CALENDAR_COVERAGE_INCOMPLETE"):
        require_calendar_covers_window(calendar, "2024-01-10", "2024-01-02")
