"""Calendar-input contract and fail-closed gate -- relocated out of
`backtest.data.calendar` (Spec #005 v1.0 SS11, Batch 1) into Data
Foundation (joint remediation design 003+004, section 2; decision
registry B4, revision 5; authorized 2026-10-06 as part of Stage 2).

Behavior is UNCHANGED from the original module -- this is a pure move.
`backtest.data.calendar` keeps re-exporting every name below so every
existing #005 import site and test keeps working without modification.

Reconciling a calendar against actual price series is engine work for a
later batch -- this module is the contract and the fail-closed gate
only. `evaluation.engine._resolve_session_dates()` (Spec #003) is
untouched by this relocation; Spec #005's own stricter calendar
requirement (`require_verified_calendar_for_formal_run()`) remains
scoped to #005's own FORMAL runs, exactly as before.
"""
from __future__ import annotations

from data_foundation.calendar.entities import (
    CalendarCoverageIncompleteError,
    CalendarNotVerifiedError,
    CalendarSource,
    TradingCalendar,
    build_calendar_id,
    calendar_fingerprint,
    parse_iso_date,
    verify_calendar_content_address,
    verify_calendar_structure,
)


def build_trading_calendar(
    source: str, calendar_identifier: str, calendar_version: str, market: str, timezone: str,
    coverage_start: str, coverage_end: str, session_dates: tuple[str, ...],
    session_open_time: str, session_close_time: str,
    early_close_dates: tuple[tuple[str, str], ...] = (),
    verified_by: str | None = None, verified_at: str | None = None,
) -> TradingCalendar:
    deduped_sorted = tuple(sorted(set(session_dates)))
    fp = calendar_fingerprint(
        source, calendar_identifier, calendar_version, market, timezone,
        coverage_start, coverage_end, deduped_sorted, session_open_time, session_close_time, early_close_dates,
    )
    calendar_id, calendar_hash = build_calendar_id(fp)
    return TradingCalendar(
        calendar_id=calendar_id, calendar_hash=calendar_hash,
        source=source, calendar_identifier=calendar_identifier, calendar_version=calendar_version,
        market=market, timezone=timezone, coverage_start=coverage_start, coverage_end=coverage_end,
        session_dates=deduped_sorted, session_open_time=session_open_time, session_close_time=session_close_time,
        early_close_dates=tuple(early_close_dates), verified_by=verified_by, verified_at=verified_at,
    )


def require_verified_calendar_for_formal_run(calendar: TradingCalendar) -> None:
    """Spec #005 SS11: "Without a verified calendar covering the stage
    and required warm-up, fail closed with CALENDAR_UNVERIFIED... before
    formal execution. Synthetic infrastructure tests may declare their
    own explicit fixture calendar; they cannot label it a verified
    real-market calendar."

    Re-verifies the calendar's own content-address and structural shape
    FIRST -- `source`/`verified_by`/`verified_at` alone are stored fields
    that a `dataclasses.replace()`-tampered object would still carry
    unchanged. Neither check is optional for a formal run."""
    address_ok, address_errors = verify_calendar_content_address(calendar)
    if not address_ok:
        raise CalendarNotVerifiedError(
            f"CALENDAR_UNVERIFIED: calendar_id={calendar.calendar_id!r} failed content-address "
            f"re-verification: {'; '.join(address_errors)} (Spec #005 SS11/SS21)"
        )
    structure_ok, structure_errors = verify_calendar_structure(calendar)
    if not structure_ok:
        raise CalendarNotVerifiedError(
            f"CALENDAR_UNVERIFIED: calendar_id={calendar.calendar_id!r} failed structural "
            f"validation: {'; '.join(structure_errors)} (Spec #005 SS11)"
        )
    if calendar.source != CalendarSource.OFFICIAL_VERIFIED.value:
        raise CalendarNotVerifiedError(
            f"CALENDAR_UNVERIFIED: calendar_id={calendar.calendar_id!r} has source={calendar.source!r}, "
            f"not {CalendarSource.OFFICIAL_VERIFIED.value!r} -- a formal run requires a verified "
            f"real-market calendar; a synthetic test fixture can never satisfy this (Spec #005 SS11)"
        )
    if not calendar.verified_by or not calendar.verified_at:
        raise CalendarNotVerifiedError(
            f"CALENDAR_UNVERIFIED: calendar_id={calendar.calendar_id!r} claims source="
            f"{CalendarSource.OFFICIAL_VERIFIED.value!r} but is missing verified_by/verified_at "
            f"provenance (Spec #005 SS11)"
        )


def require_calendar_covers_window(calendar: TradingCalendar, window_start: str, window_end: str) -> None:
    """Spec #005 SS11/SS24: "fail closed with... CALENDAR_COVERAGE_
    INCOMPLETE before formal execution" when the calendar's own declared
    coverage does not fully contain the window a run needs."""
    parsed_window_start = parse_iso_date(window_start)
    parsed_window_end = parse_iso_date(window_end)
    if parsed_window_start is None or parsed_window_end is None:
        raise CalendarCoverageIncompleteError(
            f"CALENDAR_COVERAGE_INCOMPLETE: window_start={window_start!r}/window_end={window_end!r} "
            f"must both be valid ISO dates (YYYY-MM-DD) (Spec #005 SS11)"
        )
    parsed_coverage_start = parse_iso_date(calendar.coverage_start)
    parsed_coverage_end = parse_iso_date(calendar.coverage_end)
    if parsed_coverage_start is None or parsed_coverage_end is None:
        raise CalendarCoverageIncompleteError(
            f"CALENDAR_COVERAGE_INCOMPLETE: calendar_id={calendar.calendar_id!r} has a malformed "
            f"coverage_start/coverage_end and cannot be checked against a window (Spec #005 SS11)"
        )
    if parsed_window_start > parsed_window_end:
        raise CalendarCoverageIncompleteError(
            f"CALENDAR_COVERAGE_INCOMPLETE: window_start={window_start!r} is after "
            f"window_end={window_end!r} -- a reversed window can never be covered (Spec #005 SS11)"
        )
    if not (parsed_coverage_start <= parsed_window_start and parsed_window_end <= parsed_coverage_end):
        raise CalendarCoverageIncompleteError(
            f"CALENDAR_COVERAGE_INCOMPLETE: calendar_id={calendar.calendar_id!r} covers "
            f"[{calendar.coverage_start!r}, {calendar.coverage_end!r}] but the required window is "
            f"[{window_start!r}, {window_end!r}] (Spec #005 SS11)"
        )


def is_session(calendar: TradingCalendar, date: str) -> bool:
    """A date's ABSENCE from `session_dates` means the calendar declares
    it a non-session -- this is the ground truth, never inferred from
    whether any particular security's price series happens to have a
    bar on that date. But that ground truth only extends as far as the
    calendar's own declared coverage: a date OUTSIDE [coverage_start,
    coverage_end] is UNKNOWN, not a verified non-session -- an
    out-of-coverage query raises instead of silently returning False."""
    query_date = parse_iso_date(date)
    if query_date is None:
        raise CalendarCoverageIncompleteError(
            f"CALENDAR_COVERAGE_INCOMPLETE: date={date!r} is not a valid ISO date (YYYY-MM-DD) -- "
            f"cannot be classified as a session or non-session (Spec #005 SS11)"
        )
    coverage_start = parse_iso_date(calendar.coverage_start)
    coverage_end = parse_iso_date(calendar.coverage_end)
    if coverage_start is None or coverage_end is None:
        raise CalendarCoverageIncompleteError(
            f"CALENDAR_COVERAGE_INCOMPLETE: calendar_id={calendar.calendar_id!r} has a malformed "
            f"coverage_start/coverage_end and cannot be queried (Spec #005 SS11)"
        )
    if not (coverage_start <= query_date <= coverage_end):
        raise CalendarCoverageIncompleteError(
            f"CALENDAR_COVERAGE_INCOMPLETE: date={date!r} falls outside calendar_id="
            f"{calendar.calendar_id!r}'s declared coverage [{calendar.coverage_start!r}, "
            f"{calendar.coverage_end!r}] -- this calendar has no verified information about "
            f"whether that date is a session (Spec #005 SS11)"
        )
    return date in calendar.session_dates
