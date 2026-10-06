"""CalendarRegistry -- atomic registration and Evaluation's own
consumption rule (Steps 4-6; joint remediation design 003+004 section
2; decision registry B1-B4, revision 5-6; authorized 2026-10-06,
Stage 2).

The five regressions Radu's own review required, in order: direct
construction without a record is refused; a record linked to the wrong
calendar/artifact is rejected; a session/exception discrepancy is
rejected (covered in test_02, exercised again here end-to-end); a
failed registration leaves no partial state; a valid case resolves
from the registry with its record intact.
"""
import json

import pytest

from data_foundation.calendar.admission import admit_source_via_operator_attestation
from data_foundation.calendar.entities import CalendarNotVerifiedError, CalendarSource
from data_foundation.calendar.contract import build_trading_calendar
from data_foundation.calendar.registry import (
    VERIFICATION_METHOD_VERSION_V1,
    CalendarRegistrationError,
    CalendarRegistry,
    CalendarVerificationRecord,
    verify_calendar_against_source,
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


def _admitted(session_dates=_SESSIONS):
    raw = json.dumps({"session_dates": list(session_dates), "early_close_dates": []})
    return admit_source_via_operator_attestation(
        source_identifier="X", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=raw,
    )


def _record_for(calendar, admitted_source, verified_by="radu", verified_at="2026-10-06T00:00:00Z"):
    return CalendarVerificationRecord(
        calendar_id=calendar.calendar_id, calendar_hash=calendar.calendar_hash,
        source_artifact_digest=admitted_source.artifact_digest,
        verification_method_version=VERIFICATION_METHOD_VERSION_V1,
        verified_by=verified_by, verified_at=verified_at,
    )


def test_direct_construction_without_a_record_is_refused():
    """build_trading_calendar() alone, with no registration at all, must
    never resolve -- a bare object is never trusted on its own claimed
    fields, however correct its source label."""
    calendar = _calendar()
    registry = CalendarRegistry()
    with pytest.raises(CalendarNotVerifiedError, match="CALENDAR_UNVERIFIED"):
        registry.resolve(calendar.calendar_id)


def test_record_linked_to_a_different_calendar_is_rejected():
    calendar = _calendar()
    other_calendar = _calendar(calendar_identifier="A_DIFFERENT_CALENDAR")
    admitted = _admitted()
    record = _record_for(other_calendar, admitted)  # names the WRONG calendar
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError, match="does not match the calendar being registered"):
        registry.register_verified(calendar, record)


def test_genuine_session_discrepancy_is_rejected_end_to_end():
    """Full chain: admit -> verify -> (verification fails) -> never
    reaches registration at all."""
    calendar = _calendar(session_dates=_SESSIONS + ("2024-01-05",))
    admitted = _admitted(session_dates=_SESSIONS)  # admitted source lacks 2024-01-05
    ok, errors = verify_calendar_against_source(
        calendar.session_dates, calendar.early_close_dates, calendar.market, calendar.timezone, admitted,
    )
    assert not ok
    assert any("not present in the admitted source" in e for e in errors)


def test_failed_registration_leaves_no_partial_state():
    calendar = _calendar()
    other_calendar = _calendar(calendar_identifier="A_DIFFERENT_CALENDAR")
    admitted = _admitted()
    bad_record = _record_for(other_calendar, admitted)
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError):
        registry.register_verified(calendar, bad_record)
    # Nothing was stored -- neither the calendar nor any record.
    with pytest.raises(CalendarNotVerifiedError):
        registry.resolve(calendar.calendar_id)
    with pytest.raises(CalendarNotVerifiedError):
        registry.resolve_record(calendar.calendar_id)


def test_valid_case_resolves_from_the_registry_with_its_record_intact():
    calendar = _calendar()
    admitted = _admitted()
    ok, errors = verify_calendar_against_source(
        calendar.session_dates, calendar.early_close_dates, calendar.market, calendar.timezone, admitted,
    )
    assert ok, errors
    record = _record_for(calendar, admitted)
    registry = CalendarRegistry()
    registry.register_verified(calendar, record)

    resolved = registry.resolve(calendar.calendar_id)
    assert resolved == calendar
    resolved_record = registry.resolve_record(calendar.calendar_id)
    assert resolved_record.source_artifact_digest == admitted.artifact_digest
    assert resolved_record.calendar_id == calendar.calendar_id


def test_registration_rejects_a_structurally_tampered_calendar():
    """A dataclasses.replace()-tampered calendar (content-address
    mismatch) must be refused at registration, not merely at the
    later require_verified_calendar_for_formal_run() gate."""
    import dataclasses
    calendar = _calendar()
    tampered = dataclasses.replace(calendar, session_dates=calendar.session_dates[:-1])
    admitted = _admitted()
    record = _record_for(tampered, admitted)
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError, match="content-address verification failed"):
        registry.register_verified(tampered, record)
