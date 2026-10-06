"""Calendar verification, atomic registration, and Evaluation's own
consumption rule -- Steps 3-6 of the admission/verification/
registration contract (joint remediation design 003+004, 2026-10-04,
section 2; decision registry B1-B4/I1, revision 5-6; authorized
2026-10-06 as part of Stage 2).

Step 3 (`verify_calendar_against_source`): compares a candidate
calendar's own session dates/early closes against the ADMITTED source's
own parsed content, for the SAME market/timezone. A mismatch of any
kind is a rejection, with the specific discrepancy recorded.

Step 4 (`CalendarVerificationRecord`): on success, the explicit link
between the candidate calendar's own identity, the admitted source's
own digest, the verification method/version, the verifier, and the
time.

Step 5 (`CalendarRegistry.register_verified`): the calendar and its
record are registered TOGETHER, atomically -- on any failure, NOTHING
is registered.

Step 6 (`CalendarRegistry.resolve`): Evaluation's own consumption rule,
the actual trust boundary this contract exists to provide -- resolve
EXCLUSIVELY by identity, REQUIRE the linked record, never trust a bare
`TradingCalendar` object's own claimed fields. A lookup with no linked
record is refused, treated the same as `CALENDAR_UNVERIFIED`.

`build_trading_calendar()` (`contract.py`) is NOT restricted by any of
this -- it remains the free, unrestricted constructor it always was.
All trust authority lives here, in the registry and in `resolve()`'s
own rule, never in the constructor.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from data_foundation.calendar.admission import AdmittedCalendarSource
from data_foundation.calendar.entities import (
    CalendarNotVerifiedError,
    TradingCalendar,
    verify_calendar_content_address,
    verify_calendar_structure,
)

VERIFICATION_METHOD_VERSION_V1 = "v1"


def verify_calendar_against_source(
    candidate_session_dates: tuple[str, ...],
    candidate_early_close_dates: tuple[tuple[str, str], ...],
    candidate_market: str,
    candidate_timezone: str,
    admitted_source: AdmittedCalendarSource,
) -> tuple[bool, tuple[str, ...]]:
    """Parses `admitted_source.raw_content` (expected JSON with
    `session_dates`/`early_close_dates` keys -- the source's own claimed
    content, retained verbatim at admission) and compares it, exactly,
    against the candidate. Never compares against an arbitrary,
    unadmitted artifact -- `admitted_source` must already have passed
    Step 0."""
    errors: list[str] = []
    if candidate_market != admitted_source.market:
        errors.append(
            f"market mismatch: candidate={candidate_market!r} vs. admitted source="
            f"{admitted_source.market!r}"
        )
    if candidate_timezone != admitted_source.timezone:
        errors.append(
            f"timezone mismatch: candidate={candidate_timezone!r} vs. admitted source="
            f"{admitted_source.timezone!r}"
        )

    try:
        parsed = json.loads(admitted_source.raw_content)
    except (json.JSONDecodeError, TypeError) as exc:
        return False, errors + [f"admitted source's raw_content is not valid JSON: {exc}"]

    source_sessions = set(parsed.get("session_dates", []))
    source_early_closes = {tuple(pair) for pair in parsed.get("early_close_dates", [])}
    candidate_sessions = set(candidate_session_dates)
    candidate_closes = set(candidate_early_close_dates)

    missing_sessions = sorted(source_sessions - candidate_sessions)
    extra_sessions = sorted(candidate_sessions - source_sessions)
    if missing_sessions:
        errors.append(f"candidate is missing session dates present in the admitted source: {missing_sessions!r}")
    if extra_sessions:
        errors.append(f"candidate has session dates not present in the admitted source: {extra_sessions!r}")

    missing_closes = sorted(source_early_closes - candidate_closes)
    extra_closes = sorted(candidate_closes - source_early_closes)
    if missing_closes:
        errors.append(f"candidate is missing early-close dates present in the admitted source: {missing_closes!r}")
    if extra_closes:
        errors.append(f"candidate has early-close dates not present in the admitted source: {extra_closes!r}")

    return (not errors, tuple(errors))


@dataclass(frozen=True)
class CalendarVerificationRecord:
    """The explicit link a bare `TradingCalendar` object can never carry
    on its own: WHICH calendar (by content-address), verified against
    WHICH source artifact (by digest), by WHICH method version, by WHOM,
    WHEN."""
    calendar_id: str
    calendar_hash: str
    source_artifact_digest: str
    verification_method_version: str
    verified_by: str
    verified_at: str


class CalendarRegistrationError(ValueError):
    pass


class CalendarRegistry:
    """Steps 5-6. An in-memory registry, mirroring this project's own
    established atomic-gate pattern (`hypothesis.registry.preregistration.
    preregister_hypothesis()`): one write path, atomic, and a resolve
    path that refuses anything not registered through it."""

    def __init__(self) -> None:
        self._calendars: dict[str, TradingCalendar] = {}
        self._records: dict[str, CalendarVerificationRecord] = {}

    def register_verified(self, calendar: TradingCalendar, record: CalendarVerificationRecord) -> None:
        """Step 5: register `calendar` and `record` TOGETHER. On any
        failure below, NOTHING is stored -- no partial state, mirroring
        Finding 16/#004's own batch-safe dry-run discipline."""
        if record.calendar_id != calendar.calendar_id or record.calendar_hash != calendar.calendar_hash:
            raise CalendarRegistrationError(
                f"CalendarVerificationRecord names calendar_id={record.calendar_id!r}/"
                f"calendar_hash={record.calendar_hash!r}, which does not match the calendar being "
                f"registered (calendar_id={calendar.calendar_id!r}/calendar_hash={calendar.calendar_hash!r}) "
                f"-- refusing to register a record linked to a different calendar"
            )
        address_ok, address_errors = verify_calendar_content_address(calendar)
        if not address_ok:
            raise CalendarRegistrationError(
                f"calendar content-address verification failed, refusing registration: "
                f"{'; '.join(address_errors)}"
            )
        structure_ok, structure_errors = verify_calendar_structure(calendar)
        if not structure_ok:
            raise CalendarRegistrationError(
                f"calendar structural validation failed, refusing registration: "
                f"{'; '.join(structure_errors)}"
            )
        self._calendars[calendar.calendar_id] = calendar
        self._records[calendar.calendar_id] = record

    def resolve(self, calendar_id: str) -> TradingCalendar:
        """Step 6: Evaluation's own consumption rule -- resolve
        EXCLUSIVELY by identity, REQUIRE the linked record. A lookup
        with no linked record (never registered, or registration
        failed) is refused, treated the same as `CALENDAR_UNVERIFIED`."""
        if calendar_id not in self._calendars or calendar_id not in self._records:
            raise CalendarNotVerifiedError(
                f"CALENDAR_UNVERIFIED: calendar_id={calendar_id!r} has no linked "
                f"CalendarVerificationRecord in this registry -- a bare TradingCalendar object is "
                f"never trusted on its own claimed fields, however correct its hash or source label"
            )
        return self._calendars[calendar_id]

    def resolve_record(self, calendar_id: str) -> CalendarVerificationRecord:
        if calendar_id not in self._records:
            raise CalendarNotVerifiedError(
                f"CALENDAR_UNVERIFIED: calendar_id={calendar_id!r} has no linked "
                f"CalendarVerificationRecord in this registry"
            )
        return self._records[calendar_id]
