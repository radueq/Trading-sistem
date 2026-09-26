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


def test_require_calendar_covers_window_rejects_garbage_suffixed_dates():
    """GPT Batch 1 review, round 2 (P2 finding): "2024-01-02junk"/
    "2024-01-03junk" were previously compared as raw strings and could
    slip through undetected -- must be rejected outright as invalid
    dates, not silently classified as covered or uncovered."""
    calendar = _verified_calendar()
    with pytest.raises(CalendarCoverageIncompleteError, match="CALENDAR_COVERAGE_INCOMPLETE"):
        require_calendar_covers_window(calendar, "2024-01-02junk", "2024-01-03junk")


def test_require_calendar_covers_window_rejects_an_iso_week_date():
    """Same non-canonical-ISO-form loophole as the zone-ordering exploit
    -- "2024W011" (== 2024-01-01) must be rejected outright, never
    accepted as a window bound."""
    calendar = _verified_calendar()
    with pytest.raises(CalendarCoverageIncompleteError, match="CALENDAR_COVERAGE_INCOMPLETE"):
        require_calendar_covers_window(calendar, "2024W011", "2024-01-10")


def test_is_session_rejects_a_garbage_suffixed_date_instead_of_returning_false():
    """GPT Batch 1 review, round 2 (P2 finding): is_session() previously
    returned False for "2024-01-02junk" (treating it like a genuine
    non-session) instead of rejecting the malformed input outright."""
    calendar = _verified_calendar()
    with pytest.raises(CalendarCoverageIncompleteError, match="CALENDAR_COVERAGE_INCOMPLETE"):
        is_session(calendar, "2024-01-02junk")


def test_verify_calendar_structure_rejects_a_nonexistent_timezone():
    """GPT Batch 1 review, round 2 (P2 finding): a nonexistent timezone
    previously passed formal verification entirely -- structure
    validation never checked it."""
    calendar = _verified_calendar(timezone="Not/AZone")
    ok, errors = verify_calendar_structure(calendar)
    assert not ok
    assert any("timezone" in e for e in errors)


def test_verify_calendar_structure_rejects_a_garbage_session_open_time():
    calendar = _verified_calendar(session_open_time="garbage")
    ok, errors = verify_calendar_structure(calendar)
    assert not ok
    assert any("session_open_time" in e for e in errors)


def test_verify_calendar_structure_rejects_open_time_not_before_close_time():
    calendar = _verified_calendar(session_open_time="16:00", session_close_time="09:30")
    ok, errors = verify_calendar_structure(calendar)
    assert not ok
    assert any("must be before session_close_time" in e for e in errors)


def test_verify_calendar_structure_rejects_contradictory_early_closes_on_a_non_session_day():
    """GPT Batch 1 review, round 2 (P2 finding): two contradictory
    early-close entries on a day that is not even one of the calendar's
    session_dates previously passed formal verification entirely."""
    calendar = _verified_calendar(early_close_dates=(("2024-01-10", "13:00"), ("2024-01-10", "14:00")))
    ok, errors = verify_calendar_structure(calendar)
    assert not ok
    assert any("is not one of the calendar's session_dates" in e for e in errors)
    assert any("appears more than once" in e for e in errors)


def test_verify_calendar_structure_rejects_an_early_close_not_earlier_than_session_close():
    calendar = _verified_calendar(early_close_dates=(("2024-01-03", "16:00"),))
    ok, errors = verify_calendar_structure(calendar)
    assert not ok
    assert any("must be earlier than session_close_time" in e for e in errors)


def test_verify_calendar_structure_rejects_an_early_close_before_session_open():
    """GPT Batch 1 review, round 3 (P2 finding): the upper-bound check
    (close_time < session_close_time) alone let an early close BEFORE
    the session even opens (09:30 open, "08:00" early close) pass
    verification, including the formal-run gate."""
    calendar = _verified_calendar(early_close_dates=(("2024-01-03", "08:00"),))
    ok, errors = verify_calendar_structure(calendar)
    assert not ok
    assert any("must be later than session_open_time" in e for e in errors)


def test_verify_calendar_structure_rejects_an_early_close_equal_to_session_open():
    """Same finding, the exact-equality edge: an early close AT the
    opening time (09:30 open, "09:30" early close) is not a genuine
    early close either -- must be rejected, not accepted."""
    calendar = _verified_calendar(early_close_dates=(("2024-01-03", "09:30"),))
    ok, errors = verify_calendar_structure(calendar)
    assert not ok
    assert any("must be later than session_open_time" in e for e in errors)


def test_verify_calendar_structure_accepts_a_genuine_early_close_on_a_session_day():
    calendar = _verified_calendar(early_close_dates=(("2024-01-03", "13:00"),))
    ok, errors = verify_calendar_structure(calendar)
    assert ok, errors
