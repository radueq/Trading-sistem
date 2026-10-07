"""CalendarRegistry -- atomic registration and Evaluation's own
consumption rule (Steps 3-6; joint remediation design 003+004 section
2; decision registry B1-B4, revision 5-6; authorized 2026-10-06,
Stage 2; CORRECTED this round per GPT's own changes-required review:
the prior version of this module let a caller hand-build a
`CalendarVerificationRecord` naming an invented digest and blank
verifier/timestamp, and accepted it -- `register_verified()` now
EXECUTES the admit->verify chain itself and builds the record
internally; a caller can no longer supply one.

Regressions, in order: direct construction without registration is
refused; an admitted source tampered with after admission is rejected;
coverage incompatible with the admitted source is rejected; a genuine
session discrepancy is rejected; blank verified_by/verified_at is
rejected; a failed registration leaves no partial state AND preserves
any pre-existing entry; a valid case resolves from the registry with
its record intact; a structurally-tampered calendar is rejected.
"""
import dataclasses
import json

import pytest

from data_foundation.calendar.admission import admit_source_via_operator_attestation
from data_foundation.calendar.entities import CalendarNotVerifiedError, CalendarSource
from data_foundation.calendar.contract import build_trading_calendar
from data_foundation.calendar.registry import (
    CalendarRegistrationError,
    CalendarRegistry,
)

_SESSIONS = ("2024-01-02", "2024-01-03", "2024-01-04")


def _calendar(**overrides):
    defaults = dict(
        source=CalendarSource.OFFICIAL_VERIFIED.value, calendar_identifier="NYSE_NASDAQ_COMPOSITE",
        calendar_version="v1", market="US_EQUITIES", timezone="America/New_York",
        coverage_start="2024-01-01", coverage_end="2024-01-31", session_dates=_SESSIONS,
        session_open_time="09:30", session_close_time="16:00",
        verified_by="radu", verified_at="2026-10-06T00:00:00Z",
    )
    defaults.update(overrides)
    return build_trading_calendar(**defaults)


def _admitted(session_dates=_SESSIONS, coverage_start="2024-01-01", coverage_end="2024-01-31"):
    raw = json.dumps({"session_dates": list(session_dates), "early_close_dates": []})
    return admit_source_via_operator_attestation(
        source_identifier="X", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date="2024-01-01", coverage_start=coverage_start, coverage_end=coverage_end,
        market="US_EQUITIES", timezone="America/New_York", raw_content=raw,
    )


def test_direct_construction_without_a_record_is_refused():
    """build_trading_calendar() alone, with no registration at all, must
    never resolve -- a bare object is never trusted on its own claimed
    fields, however correct its source label."""
    calendar = _calendar()
    registry = CalendarRegistry()
    with pytest.raises(CalendarNotVerifiedError, match="CALENDAR_UNVERIFIED"):
        registry.resolve(calendar.calendar_id)


def test_admitted_source_tampered_with_after_admission_is_rejected():
    """A dataclasses.replace()-tampered AdmittedCalendarSource (new
    raw_content, stale artifact_digest) must never pass as the
    genuinely-admitted artifact -- register_verified() recomputes the
    digest itself rather than trusting the stored one."""
    calendar = _calendar()
    admitted = _admitted()
    tampered_source = dataclasses.replace(admitted, raw_content=admitted.raw_content + " TAMPERED")
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError, match="modified after admission"):
        registry.register_verified(
            calendar, tampered_source, verified_by="radu", verified_at="2026-10-06T00:00:00Z",
        )


def test_coverage_incompatible_with_admitted_source_is_rejected():
    calendar = _calendar(coverage_start="2024-01-01", coverage_end="2024-01-31")
    admitted = _admitted(coverage_start="2024-02-01", coverage_end="2024-02-29")  # disjoint coverage
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError, match="not contained within the admitted source"):
        registry.register_verified(
            calendar, admitted, verified_by="radu", verified_at="2026-10-06T00:00:00Z",
        )


def test_genuine_session_discrepancy_is_rejected_before_registration():
    calendar = _calendar(session_dates=_SESSIONS + ("2024-01-05",))
    admitted = _admitted(session_dates=_SESSIONS)  # admitted source lacks 2024-01-05
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError, match="not present in the admitted source"):
        registry.register_verified(
            calendar, admitted, verified_by="radu", verified_at="2026-10-06T00:00:00Z",
        )
    with pytest.raises(CalendarNotVerifiedError):
        registry.resolve(calendar.calendar_id)


def test_blank_verified_by_is_rejected():
    calendar = _calendar()
    admitted = _admitted()
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError, match="non-blank verified_by"):
        registry.register_verified(calendar, admitted, verified_by="   ", verified_at="2026-10-06T00:00:00Z")


def test_blank_verified_at_is_rejected():
    calendar = _calendar()
    admitted = _admitted()
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError, match="non-blank verified_at"):
        registry.register_verified(calendar, admitted, verified_by="radu", verified_at="")


def test_failed_registration_leaves_no_partial_state():
    calendar = _calendar(session_dates=_SESSIONS + ("2024-01-05",))
    admitted = _admitted(session_dates=_SESSIONS)
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError):
        registry.register_verified(calendar, admitted, verified_by="radu", verified_at="2026-10-06T00:00:00Z")
    with pytest.raises(CalendarNotVerifiedError):
        registry.resolve(calendar.calendar_id)
    with pytest.raises(CalendarNotVerifiedError):
        registry.resolve_record(calendar.calendar_id)


def test_failed_registration_preserves_a_pre_existing_entry():
    """The registry already holds ONE valid entry; a second,
    independently-failing registration (for a DIFFERENT calendar) must
    leave the first entry completely untouched."""
    good_calendar = _calendar()
    good_admitted = _admitted()
    registry = CalendarRegistry()
    registry.register_verified(good_calendar, good_admitted, verified_by="radu", verified_at="2026-10-06T00:00:00Z")

    bad_calendar = _calendar(calendar_identifier="A_DIFFERENT_CALENDAR", session_dates=_SESSIONS + ("2024-01-05",))
    bad_admitted = _admitted(session_dates=_SESSIONS)
    with pytest.raises(CalendarRegistrationError):
        registry.register_verified(bad_calendar, bad_admitted, verified_by="radu", verified_at="2026-10-06T00:00:00Z")

    resolved = registry.resolve(good_calendar.calendar_id)
    assert resolved == good_calendar
    assert registry.resolve_record(good_calendar.calendar_id).source_artifact_digest == good_admitted.artifact_digest
    with pytest.raises(CalendarNotVerifiedError):
        registry.resolve(bad_calendar.calendar_id)


def test_valid_case_resolves_from_the_registry_with_its_record_intact():
    calendar = _calendar()
    admitted = _admitted()
    registry = CalendarRegistry()
    registry.register_verified(calendar, admitted, verified_by="radu", verified_at="2026-10-06T00:00:00Z")

    resolved = registry.resolve(calendar.calendar_id)
    assert resolved == calendar
    resolved_record = registry.resolve_record(calendar.calendar_id)
    assert resolved_record.source_artifact_digest == admitted.artifact_digest
    assert resolved_record.calendar_id == calendar.calendar_id
    assert resolved_record.verified_by == "radu"


def test_registration_rejects_a_structurally_tampered_calendar():
    """A dataclasses.replace()-tampered calendar (content-address
    mismatch) must be refused at registration, not merely at the
    later require_verified_calendar_for_formal_run() gate."""
    calendar = _calendar()
    tampered = dataclasses.replace(calendar, session_dates=calendar.session_dates[:-1])
    admitted = _admitted()
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError, match="content-address verification failed"):
        registry.register_verified(tampered, admitted, verified_by="radu", verified_at="2026-10-06T00:00:00Z")
