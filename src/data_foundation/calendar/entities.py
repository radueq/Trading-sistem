"""Calendar contract -- relocated out of `backtest.models.entities`
(Spec #005 SS11) into Data Foundation (joint remediation design
003+004, 2026-10-04, section 2; decision registry B4, revision 5;
authorized 2026-10-06 as part of Stage 2).

"A session calendar is a separate, verified, versioned input, not
inferred from benchmark bars or a vote/union of security series."
Moved here, verbatim in behavior, so both `evaluation` (Spec #003) and
`backtest` (Spec #005) can import it without `evaluation` importing
`backtest` -- the reversed-dependency gap the joint design's own
section 2 named. `backtest.models.entities` and `backtest.data.calendar`
keep re-exporting every name below unchanged, so every existing #005
import site and test keeps working without modification (byte-identical
relocation, per the joint design's own regression (1)).

`canonical_json`/`parse_iso_date` below are LOCAL, independent copies of
`backtest.models.entities`'s own functions of the same name -- not
imports from there, which would reverse the one-way dependency chain
this relocation exists to fix. Keeping them duplicated here (rather
than, say, importing backtest's copy) is a deliberate, contained
trade-off: a handful of small, pure, unlikely-to-drift functions,
isolated per the same "separate fingerprint recipe per domain"
discipline `canonical_json`'s own original docstring already states
for this project (it explicitly is not shared with #003's `build_run_id()`
or #004's `hypothesis_fingerprint()` either).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_HH_MM_RE = re.compile(r"^\d{2}:\d{2}$")


def parse_iso_date(value) -> Optional[date]:
    """Strict canonical `YYYY-MM-DD` parsing ONLY -- rejects ISO week
    dates ("2024W011") and unpadded basic format ("20240101"), which
    `date.fromisoformat()` alone would accept but which parse to a
    DIFFERENT calendar date than the string suggests and do not sort
    correctly against canonical `YYYY-MM-DD` strings."""
    if not isinstance(value, str) or not _ISO_DATE_RE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_hh_mm(value) -> Optional[time]:
    if not isinstance(value, str) or not _HH_MM_RE.match(value):
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def _is_valid_timezone(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        ZoneInfo(value)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


class CalendarSource(str, Enum):
    """A formal run requires OFFICIAL_VERIFIED (SS11/SS24: "Without a
    verified calendar covering the stage and required warm-up, fail
    closed"). SYNTHETIC_TEST_FIXTURE exists so infrastructure tests can
    supply a trivial calendar of their own -- SS11 is explicit that such
    a fixture "cannot label it a verified real-market calendar", so it
    must never satisfy the formal-run gate."""
    OFFICIAL_VERIFIED = "OFFICIAL_VERIFIED"
    SYNTHETIC_TEST_FIXTURE = "SYNTHETIC_TEST_FIXTURE"


@dataclass(frozen=True)
class TradingCalendar:
    """Spec #005 SS11: "Record its source, calendar identifier, version,
    covered dates, timezone, session open/close times (including
    holidays, early closes and exceptional closures), verification
    provenance and content hash." `session_dates` is the ground truth of
    which dates ARE trading sessions -- a date's absence from every price
    series does NOT make it a non-session."""
    calendar_id: str
    calendar_hash: str

    source: str  # CalendarSource
    calendar_identifier: str  # human-assigned name, e.g. "NYSE_NASDAQ_COMPOSITE"
    calendar_version: str
    market: str  # e.g. "US_EQUITIES"
    timezone: str  # e.g. "America/New_York"

    coverage_start: str
    coverage_end: str

    session_dates: tuple[str, ...]  # sorted, deduplicated ISO dates
    session_open_time: str  # e.g. "09:30"
    session_close_time: str  # e.g. "16:00"
    early_close_dates: tuple[tuple[str, str], ...] = field(default_factory=tuple)  # (date, close_time)

    verified_by: Optional[str] = None
    verified_at: Optional[str] = None


def calendar_fingerprint(
    source: str, calendar_identifier: str, calendar_version: str, market: str, timezone: str,
    coverage_start: str, coverage_end: str, session_dates: tuple[str, ...],
    session_open_time: str, session_close_time: str, early_close_dates: tuple[tuple[str, str], ...],
) -> str:
    """`source` is part of the fingerprint on purpose: a synthetic
    fixture with the exact same dates as a real calendar must still be a
    DIFFERENT calendar identity, never interchangeable with it.
    `verified_by`/`verified_at` are excluded -- administrative
    provenance, not economic identity."""
    payload = {
        "source": source,
        "calendar_identifier": calendar_identifier,
        "calendar_version": calendar_version,
        "market": market,
        "timezone": timezone,
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
        "session_dates": sorted(session_dates),
        "session_open_time": session_open_time,
        "session_close_time": session_close_time,
        "early_close_dates": sorted([list(pair) for pair in early_close_dates]),
    }
    return canonical_json(payload)


def build_calendar_id(fingerprint: str) -> tuple[str, str]:
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    return f"cal_{digest}", digest


def verify_calendar_content_address(calendar: TradingCalendar) -> tuple[bool, tuple[str, ...]]:
    """Recomputes the fingerprint from the calendar's OWN stored fields
    and compares it to the stored `calendar_id`/`calendar_hash`. `frozen=
    True` blocks in-place mutation but not construction of a
    self-inconsistent object via `dataclasses.replace()` (e.g. dropping a
    session date while keeping the old id)."""
    fp = calendar_fingerprint(
        calendar.source, calendar.calendar_identifier, calendar.calendar_version, calendar.market,
        calendar.timezone, calendar.coverage_start, calendar.coverage_end, calendar.session_dates,
        calendar.session_open_time, calendar.session_close_time, calendar.early_close_dates,
    )
    expected_id, expected_hash = build_calendar_id(fp)
    if calendar.calendar_id != expected_id or calendar.calendar_hash != expected_hash:
        return False, (
            f"calendar content-address mismatch: stored calendar_id={calendar.calendar_id!r}/"
            f"calendar_hash={calendar.calendar_hash!r} does not match the id/hash recomputed from "
            f"the calendar's own fields ({expected_id!r}/{expected_hash!r}) -- the object was "
            f"modified after construction (e.g. via dataclasses.replace())",
        )
    return True, ()


def verify_calendar_structure(calendar: TradingCalendar) -> tuple[bool, tuple[str, ...]]:
    """Validates the calendar's declared SHAPE, independent of its
    content address: `timezone` must be a real IANA zone;
    `session_open_time`/`session_close_time` must be genuine `HH:MM`
    times with open before close; `coverage_start`/`coverage_end` and
    every session/early-close date must be genuine ISO dates, coverage
    must not be reversed, every `session_date` must fall within the
    declared coverage with no duplicates; and every `early_close_dates`
    entry must name an actual session date, have a close_time strictly
    between `session_open_time` and `session_close_time`, and appear at
    most once."""
    errors: list[str] = []

    if not _is_valid_timezone(calendar.timezone):
        errors.append(f"timezone is not a recognized IANA timezone: {calendar.timezone!r}")

    open_time = _parse_hh_mm(calendar.session_open_time)
    close_time = _parse_hh_mm(calendar.session_close_time)
    if open_time is None:
        errors.append(f"session_open_time is not a valid HH:MM time: {calendar.session_open_time!r}")
    if close_time is None:
        errors.append(f"session_close_time is not a valid HH:MM time: {calendar.session_close_time!r}")
    if open_time is not None and close_time is not None and not (open_time < close_time):
        errors.append(f"session_open_time={calendar.session_open_time!r} must be before session_close_time={calendar.session_close_time!r}")

    coverage_start_date = parse_iso_date(calendar.coverage_start)
    coverage_end_date = parse_iso_date(calendar.coverage_end)
    if coverage_start_date is None:
        errors.append(f"coverage_start is not a valid ISO date: {calendar.coverage_start!r}")
    if coverage_end_date is None:
        errors.append(f"coverage_end is not a valid ISO date: {calendar.coverage_end!r}")
    coverage_known = coverage_start_date is not None and coverage_end_date is not None and coverage_start_date <= coverage_end_date
    if coverage_start_date is not None and coverage_end_date is not None and not coverage_known:
        errors.append(f"coverage_start={calendar.coverage_start!r} is after coverage_end={calendar.coverage_end!r}")

    if len(calendar.session_dates) != len(set(calendar.session_dates)):
        errors.append("session_dates contains duplicate entries")

    for d in calendar.session_dates:
        d_date = parse_iso_date(d)
        if d_date is None:
            errors.append(f"session_dates contains a non-ISO-date value: {d!r}")
        elif coverage_known and not (coverage_start_date <= d_date <= coverage_end_date):
            errors.append(f"session_date {d!r} falls outside declared coverage [{calendar.coverage_start!r}, {calendar.coverage_end!r}]")

    seen_early_close_dates: set[str] = set()
    for entry_date, entry_close_time in calendar.early_close_dates:
        entry_date_parsed = parse_iso_date(entry_date)
        if entry_date_parsed is None:
            errors.append(f"early_close_dates contains a non-ISO-date value: {entry_date!r}")
        else:
            if coverage_known and not (coverage_start_date <= entry_date_parsed <= coverage_end_date):
                errors.append(f"early_close_date {entry_date!r} falls outside declared coverage [{calendar.coverage_start!r}, {calendar.coverage_end!r}]")
            if entry_date not in calendar.session_dates:
                errors.append(f"early_close_date {entry_date!r} is not one of the calendar's session_dates -- an early close cannot apply to a non-session day")
            if entry_date in seen_early_close_dates:
                errors.append(f"early_close_date {entry_date!r} appears more than once in early_close_dates (contradictory early closes)")
            seen_early_close_dates.add(entry_date)

        entry_close_time_parsed = _parse_hh_mm(entry_close_time)
        if entry_close_time_parsed is None:
            errors.append(f"early_close_dates close_time is not a valid HH:MM time: {entry_close_time!r}")
        else:
            if close_time is not None and not (entry_close_time_parsed < close_time):
                errors.append(f"early_close_date {entry_date!r} close_time={entry_close_time!r} must be earlier than session_close_time={calendar.session_close_time!r}")
            if open_time is not None and not (open_time < entry_close_time_parsed):
                errors.append(f"early_close_date {entry_date!r} close_time={entry_close_time!r} must be later than session_open_time={calendar.session_open_time!r} -- a session cannot close at or before it opens")

    return (not errors, tuple(errors))


class CalendarNotVerifiedError(ValueError):
    pass


class CalendarCoverageIncompleteError(ValueError):
    pass
