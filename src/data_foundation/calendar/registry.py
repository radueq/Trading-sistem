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

Step 0 (`admission.AdmissionRegistry`) feeds Step 3: `register_verified()`
takes an `AdmissionRegistry` and an `admission_id`, resolving the
admitted source from THAT registry rather than accepting one directly
(GPT review, Stage 2 second changes-required round -- a directly-
constructed `AdmittedCalendarSource`, however internally
self-consistent, is never evidence that it actually passed Step 0's
own admission rules). `admission_id` identifies the admission DECISION,
not merely the raw artifact text (GPT review, Stage 2 THIRD
changes-required round -- see `admission.py`'s own module docstring:
`artifact_digest` alone let two differently-admitted uses of the same
text collide in the registry). `CalendarVerificationRecord` now pins
BOTH: `source_artifact_digest` (the text) and `admission_id` (the
decision actually used).

`build_trading_calendar()` (`contract.py`) is NOT restricted by any of
this -- it remains the free, unrestricted constructor it always was.
All trust authority lives here, in the registry and in `resolve()`'s
own rule, never in the constructor.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from data_foundation.calendar.admission import AdmissionRegistry, AdmittedCalendarSource, _digest
from data_foundation.calendar.entities import (
    CalendarNotVerifiedError,
    TradingCalendar,
    parse_iso_date,
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
    WHEN. `admission_id` additionally pins WHICH admission DECISION was
    actually used -- not merely which raw text (GPT review, Stage 2
    THIRD changes-required round): `source_artifact_digest` alone
    cannot distinguish two different admissions of the identical text
    under different metadata."""
    calendar_id: str
    calendar_hash: str
    source_artifact_digest: str
    admission_id: str
    verification_method_version: str
    verified_by: str
    verified_at: str


class CalendarRegistrationError(ValueError):
    pass


@dataclass(frozen=True)
class _RegisteredCalendar:
    """One indivisible registry entry -- `calendar` and `record` are
    stored and read TOGETHER, never as two independently-settable
    dict slots (GPT review, Stage 2 changes-required round: two
    successive dict writes are not atomic -- an exception between them
    left a calendar with zero records). Holding both fields inside ONE
    object means the single `self._entries[calendar_id] = ...`
    assignment below either fully happens or does not happen at all;
    there is no intermediate state to observe."""
    calendar: TradingCalendar
    record: "CalendarVerificationRecord"


class CalendarRegistry:
    """Steps 3-6. An in-memory registry, mirroring this project's own
    established atomic-gate pattern (`hypothesis.registry.preregistration.
    preregister_hypothesis()`): one write path, atomic, and a resolve
    path that refuses anything not registered through it.

    `register_verified()` is the ONLY path to a registered calendar --
    it EXECUTES Steps 3-4 itself (source-tamper check, coverage check,
    `verify_calendar_against_source()`) and BUILDS the
    `CalendarVerificationRecord` internally; a caller can no longer
    hand it an already-built record (GPT review, Stage 2 first
    changes-required round: a hand-built record naming an invented
    digest and blank verifier/timestamp was accepted by the prior
    version of this method), NOR a directly-constructed
    `AdmittedCalendarSource` (GPT review, Stage 2 second changes-
    required round: digest/coverage/session self-consistency checks
    only prove an object agrees with itself, never that it actually
    passed Step 0's own admission rules) -- it takes an
    `AdmissionRegistry` and an `admission_id`, resolving the admitted
    source from THAT registry, which only `admission.admit_source_
    via_approved_provider()`/`admit_source_via_operator_attestation()`
    can ever write to."""

    def __init__(self) -> None:
        self._entries: dict[str, _RegisteredCalendar] = {}

    def register_verified(
        self, calendar: TradingCalendar, admission_registry: AdmissionRegistry, admission_id: str, *,
        verified_by: str, verified_at: str,
        verification_method_version: str = VERIFICATION_METHOD_VERSION_V1,
    ) -> None:
        """Steps 3-5: verify `calendar` against the ADMITTED source
        resolved from `admission_registry` by `admission_id` (GPT
        review, Stage 2 second changes-required round: this method
        previously took an `AdmittedCalendarSource` object directly --
        a caller could construct one by hand, e.g. with
        `admission_method="APPROVED_PROVIDER"` and a source NOT on the
        allow-list, bypassing Step 0 entirely, since digest/coverage/
        session checks only prove the OBJECT is self-consistent, never
        that it actually passed admission. Resolving by `admission_id`
        from a registry that ONLY `admit_source_via_approved_provider()`/
        `admit_source_via_operator_attestation()` can write to closes
        this -- there is no longer any path to a trusted source except
        through Step 0's own rules). On success ONLY, register both
        together atomically. On ANY failure below, NOTHING is stored --
        no partial state, and any PRE-EXISTING entry (this
        `calendar_id` or any other) is left exactly as it was,
        mirroring Finding 16/#004's own batch-safe dry-run discipline."""
        admitted_source = admission_registry.resolve(admission_id)  # CalendarSourceNotAdmittedError if unknown

        if not verified_by or not verified_by.strip():
            raise CalendarRegistrationError(
                "register_verified() requires a non-blank verified_by -- the named human or "
                "process vouching for this verification is never optional"
            )
        if not verified_at or not verified_at.strip():
            raise CalendarRegistrationError(
                "register_verified() requires a non-blank verified_at timestamp"
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

        # The admitted source's own digest must still match a FRESH
        # digest of its own retained raw_content -- a
        # dataclasses.replace()-tampered AdmittedCalendarSource (new
        # raw_content, stale artifact_digest) must never pass as if it
        # were the genuinely-admitted artifact.
        fresh_digest = _digest(admitted_source.raw_content)
        if fresh_digest != admitted_source.artifact_digest:
            raise CalendarRegistrationError(
                f"admitted source's artifact_digest={admitted_source.artifact_digest!r} does not "
                f"match a fresh digest of its own raw_content ({fresh_digest!r}) -- the admitted "
                f"source was modified after admission, refusing registration"
            )

        coverage_start = parse_iso_date(calendar.coverage_start)
        coverage_end = parse_iso_date(calendar.coverage_end)
        source_coverage_start = parse_iso_date(admitted_source.coverage_start)
        source_coverage_end = parse_iso_date(admitted_source.coverage_end)
        if None in (coverage_start, coverage_end, source_coverage_start, source_coverage_end) or not (
            source_coverage_start <= coverage_start and coverage_end <= source_coverage_end
        ):
            raise CalendarRegistrationError(
                f"calendar's own declared coverage [{calendar.coverage_start!r}, "
                f"{calendar.coverage_end!r}] is not contained within the admitted source's own "
                f"declared coverage [{admitted_source.coverage_start!r}, "
                f"{admitted_source.coverage_end!r}] -- refusing registration"
            )

        verify_ok, verify_errors = verify_calendar_against_source(
            calendar.session_dates, calendar.early_close_dates, calendar.market, calendar.timezone,
            admitted_source,
        )
        if not verify_ok:
            raise CalendarRegistrationError(
                f"calendar does not match the admitted source, refusing registration: "
                f"{'; '.join(verify_errors)}"
            )

        record = CalendarVerificationRecord(
            calendar_id=calendar.calendar_id, calendar_hash=calendar.calendar_hash,
            source_artifact_digest=admitted_source.artifact_digest,
            admission_id=admitted_source.admission_id,
            verification_method_version=verification_method_version,
            verified_by=verified_by, verified_at=verified_at,
        )
        self._entries[calendar.calendar_id] = _RegisteredCalendar(calendar=calendar, record=record)

    def resolve(self, calendar_id: str) -> TradingCalendar:
        """Step 6: Evaluation's own consumption rule -- resolve
        EXCLUSIVELY by identity, REQUIRE the linked record. A lookup
        with no linked record (never registered, or registration
        failed) is refused, treated the same as `CALENDAR_UNVERIFIED`."""
        entry = self._entries.get(calendar_id)
        if entry is None:
            raise CalendarNotVerifiedError(
                f"CALENDAR_UNVERIFIED: calendar_id={calendar_id!r} has no linked "
                f"CalendarVerificationRecord in this registry -- a bare TradingCalendar object is "
                f"never trusted on its own claimed fields, however correct its hash or source label"
            )
        return entry.calendar

    def resolve_record(self, calendar_id: str) -> CalendarVerificationRecord:
        entry = self._entries.get(calendar_id)
        if entry is None:
            raise CalendarNotVerifiedError(
                f"CALENDAR_UNVERIFIED: calendar_id={calendar_id!r} has no linked "
                f"CalendarVerificationRecord in this registry"
            )
        return entry.record
