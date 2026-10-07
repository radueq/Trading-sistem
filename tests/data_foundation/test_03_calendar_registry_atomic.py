"""CalendarRegistry -- atomic registration and Evaluation's own
consumption rule (Steps 3-6; joint remediation design 003+004 section
2; decision registry B1-B4, revision 5-6; authorized 2026-10-06,
Stage 2; CORRECTED across three changes-required rounds per GPT's own
review:

Round 1: the prior version let a caller hand-build a
`CalendarVerificationRecord` naming an invented digest and blank
verifier/timestamp, and accepted it -- `register_verified()` now
EXECUTES the admit->verify chain itself and builds the record
internally; a caller can no longer supply one.

Round 2: the prior version of THIS round's own fix still accepted a
directly-constructed `AdmittedCalendarSource` (never passed through
Step 0's own `admit_source_via_*()` functions) as long as it was
internally self-consistent -- digest/coverage/session checks only
prove the OBJECT agrees with itself, never that it was actually
admitted. `register_verified()` now takes an `AdmissionRegistry` and
an `admission_id`, resolving the admitted source from THAT registry,
which only the two admit_* functions can ever write to.

Round 3: `admission_id` was, at that point, still just the artifact's
own `sha256` digest -- so two LEGITIMATE admissions of the identical
raw text under different metadata (different source, operator,
coverage) collided on the same registry key, and the second silently
replaced the first. `admission_id` is now a distinct identity, binding
the digest to the full admission metadata (see `admission.py`'s own
module docstring); `CalendarVerificationRecord` now also carries
`admission_id`, pinning the EXACT admission decision used, not merely
the shared raw text.

Regressions, in order: direct construction without registration is
refused; a directly-constructed AdmittedCalendarSource for an
unapproved provider is refused (never reaches the calendar gate at
all, since it has no admission_id); a nonexistent admission_id is
refused; content and digest changed TOGETHER after admission cannot
replace the admitted snapshot; the SAME text admitted twice under
DIFFERENT metadata gets distinct identities, both snapshots retained,
with the calendar record tied to the one actually used; the identical
admission repeated is idempotent; coverage incompatible with the
admitted source is rejected; a genuine session discrepancy is
rejected; blank verified_by/verified_at is rejected; a failed
registration leaves no partial state AND preserves any pre-existing
entry; a valid case resolves from the registry with its record
intact, through the full admit -> verify -> register -> resolve chain;
a structurally-tampered calendar is rejected.
"""
import dataclasses
import json

import pytest

from data_foundation.calendar.admission import (
    ADMISSION_METHOD_APPROVED_PROVIDER,
    AdmissionRegistry,
    AdmittedCalendarSource,
    CalendarSourceNotAdmittedError,
    _digest,
    admit_source_via_operator_attestation,
)
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


def _admit(
    admission_registry, session_dates=_SESSIONS, coverage_start="2024-01-01", coverage_end="2024-01-31",
    source_identifier="X", operator_name="radu",
):
    raw = json.dumps({"session_dates": list(session_dates), "early_close_dates": []})
    admitted = admit_source_via_operator_attestation(
        registry=admission_registry, source_identifier=source_identifier, operator_name=operator_name,
        attested_at="2026-10-06T00:00:00Z", version="v1", publication_date="2024-01-01",
        coverage_start=coverage_start, coverage_end=coverage_end,
        market="US_EQUITIES", timezone="America/New_York", raw_content=raw,
    )
    return admitted.admission_id, admitted


def test_direct_construction_without_a_record_is_refused():
    """build_trading_calendar() alone, with no registration at all, must
    never resolve -- a bare object is never trusted on its own claimed
    fields, however correct its source label."""
    calendar = _calendar()
    registry = CalendarRegistry()
    with pytest.raises(CalendarNotVerifiedError, match="CALENDAR_UNVERIFIED"):
        registry.resolve(calendar.calendar_id)


def test_directly_constructed_admitted_source_for_an_unapproved_provider_is_refused():
    """GPT review, Stage 2 second changes-required round, reproduced:
    a hand-built `AdmittedCalendarSource` with `admission_method=
    APPROVED_PROVIDER` for a source never actually on the (empty, V1)
    allow-list must have NO path into the calendar gate at all -- it
    was never admitted, so it has no admission_id any registry would
    recognize."""
    calendar = _calendar()
    raw = json.dumps({"session_dates": list(_SESSIONS), "early_close_dates": []})
    forged = AdmittedCalendarSource(
        source_identifier="NEVER_APPROVED_FEED", admission_method=ADMISSION_METHOD_APPROVED_PROVIDER,
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=raw,
        artifact_digest=_digest(raw), admission_id="NEVER_RECORDED_ID", attested_by=None, attested_at=None,
    )
    admission_registry = AdmissionRegistry()  # forged was never admitted into it
    calendar_registry = CalendarRegistry()
    with pytest.raises(CalendarSourceNotAdmittedError, match="has no linked admission"):
        calendar_registry.register_verified(
            calendar, admission_registry, forged.admission_id, verified_by="radu", verified_at="2026-10-06T00:00:00Z",
        )


def test_nonexistent_admission_id_is_refused():
    calendar = _calendar()
    admission_registry = AdmissionRegistry()
    calendar_registry = CalendarRegistry()
    with pytest.raises(CalendarSourceNotAdmittedError, match="has no linked admission"):
        calendar_registry.register_verified(
            calendar, admission_registry, "totally_made_up_admission_id",
            verified_by="radu", verified_at="2026-10-06T00:00:00Z",
        )


def test_content_and_digest_changed_together_cannot_replace_the_admitted_snapshot():
    """GPT review, Stage 2 second changes-required round: even a
    'tampered' AdmittedCalendarSource with a FRESHLY, correctly
    recomputed digest for its own new content (so the old digest-
    mismatch tamper check alone would not catch it) has no way into
    the calendar gate -- admission_registry.resolve() only ever
    returns what admission ITSELF stored, by the ORIGINAL admission_id,
    and there is no public function that lets a caller overwrite or
    substitute that stored entry. `dataclasses.replace()` never
    re-derives `admission_id` -- `tampered` carries the SAME (now
    stale) id as `admitted`, but that id resolves to whatever the
    registry itself holds, never to a caller-held copy."""
    admission_registry = AdmissionRegistry()
    admission_id, admitted = _admit(admission_registry)
    tampered_content = admitted.raw_content + " TAMPERED"
    tampered = dataclasses.replace(admitted, raw_content=tampered_content, artifact_digest=_digest(tampered_content))
    assert tampered.admission_id == admission_id  # stale -- replace() does not recompute it
    resolved = admission_registry.resolve(admission_id)
    assert resolved is admitted
    assert resolved.raw_content == admitted.raw_content
    assert resolved.artifact_digest == admitted.artifact_digest


def test_same_text_admitted_twice_with_different_metadata_both_snapshots_retained():
    """GPT review, Stage 2 THIRD changes-required round, reproduced via
    the public API alone: admission A (text X, source A, coverage to
    2024-01-31) and admission B (the SAME text X, source B, coverage to
    2024-12-31) both succeed. Before this fix, both keyed by the SAME
    `artifact_digest`, so B silently overwrote A in the registry --
    resolving A's own original identity returned B's metadata instead.
    Now each gets its own `admission_id`, and the CalendarVerification
    Record built from each stays tied to the admission actually used."""
    admission_registry = AdmissionRegistry()
    admission_id_a, admitted_a = _admit(
        admission_registry, source_identifier="SOURCE_A", operator_name="operator_a", coverage_end="2024-01-31",
    )
    admission_id_b, admitted_b = _admit(
        admission_registry, source_identifier="SOURCE_B", operator_name="operator_b", coverage_end="2024-12-31",
    )
    assert admitted_a.artifact_digest == admitted_b.artifact_digest  # identical raw text
    assert admission_id_a != admission_id_b

    calendar = _calendar(coverage_end="2024-01-31")
    registry = CalendarRegistry()
    registry.register_verified(calendar, admission_registry, admission_id_a, verified_by="radu", verified_at="2026-10-06T00:00:00Z")

    # Admission A's identity still resolves to A, untouched by B's later admission.
    assert admission_registry.resolve(admission_id_a) is admitted_a
    assert admission_registry.resolve(admission_id_a).coverage_end == "2024-01-31"
    assert admission_registry.resolve(admission_id_b) is admitted_b
    assert admission_registry.resolve(admission_id_b).coverage_end == "2024-12-31"
    # The calendar's own record is tied to the EXACT admission used (A), not merely the shared text.
    record = registry.resolve_record(calendar.calendar_id)
    assert record.admission_id == admission_id_a
    assert record.source_artifact_digest == admitted_a.artifact_digest


def test_repeating_the_identical_admission_and_registration_is_idempotent():
    admission_registry = AdmissionRegistry()
    admission_id_first, admitted_first = _admit(admission_registry)
    admission_id_second, admitted_second = _admit(admission_registry)
    assert admission_id_first == admission_id_second
    assert admitted_first == admitted_second
    assert admission_registry.resolve(admission_id_first) == admitted_first


def test_coverage_incompatible_with_admitted_source_is_rejected():
    calendar = _calendar(coverage_start="2024-01-01", coverage_end="2024-01-31")
    admission_registry = AdmissionRegistry()
    admission_id, _ = _admit(admission_registry, coverage_start="2024-02-01", coverage_end="2024-02-29")  # disjoint
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError, match="not contained within the admitted source"):
        registry.register_verified(
            calendar, admission_registry, admission_id, verified_by="radu", verified_at="2026-10-06T00:00:00Z",
        )


def test_genuine_session_discrepancy_is_rejected_before_registration():
    calendar = _calendar(session_dates=_SESSIONS + ("2024-01-05",))
    admission_registry = AdmissionRegistry()
    admission_id, _ = _admit(admission_registry, session_dates=_SESSIONS)  # admitted source lacks 2024-01-05
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError, match="not present in the admitted source"):
        registry.register_verified(
            calendar, admission_registry, admission_id, verified_by="radu", verified_at="2026-10-06T00:00:00Z",
        )
    with pytest.raises(CalendarNotVerifiedError):
        registry.resolve(calendar.calendar_id)


def test_blank_verified_by_is_rejected():
    calendar = _calendar()
    admission_registry = AdmissionRegistry()
    admission_id, _ = _admit(admission_registry)
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError, match="non-blank verified_by"):
        registry.register_verified(calendar, admission_registry, admission_id, verified_by="   ", verified_at="2026-10-06T00:00:00Z")


def test_blank_verified_at_is_rejected():
    calendar = _calendar()
    admission_registry = AdmissionRegistry()
    admission_id, _ = _admit(admission_registry)
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError, match="non-blank verified_at"):
        registry.register_verified(calendar, admission_registry, admission_id, verified_by="radu", verified_at="")


def test_failed_registration_leaves_no_partial_state():
    calendar = _calendar(session_dates=_SESSIONS + ("2024-01-05",))
    admission_registry = AdmissionRegistry()
    admission_id, _ = _admit(admission_registry, session_dates=_SESSIONS)
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError):
        registry.register_verified(calendar, admission_registry, admission_id, verified_by="radu", verified_at="2026-10-06T00:00:00Z")
    with pytest.raises(CalendarNotVerifiedError):
        registry.resolve(calendar.calendar_id)
    with pytest.raises(CalendarNotVerifiedError):
        registry.resolve_record(calendar.calendar_id)


def test_failed_registration_preserves_a_pre_existing_entry():
    """The registry already holds ONE valid entry; a second,
    independently-failing registration (for a DIFFERENT calendar) must
    leave the first entry completely untouched."""
    admission_registry = AdmissionRegistry()
    good_calendar = _calendar()
    good_admission_id, good_admitted = _admit(admission_registry)
    registry = CalendarRegistry()
    registry.register_verified(good_calendar, admission_registry, good_admission_id, verified_by="radu", verified_at="2026-10-06T00:00:00Z")

    bad_calendar = _calendar(calendar_identifier="A_DIFFERENT_CALENDAR", session_dates=_SESSIONS + ("2024-01-05",))
    bad_admission_id, _ = _admit(admission_registry, session_dates=_SESSIONS)
    with pytest.raises(CalendarRegistrationError):
        registry.register_verified(bad_calendar, admission_registry, bad_admission_id, verified_by="radu", verified_at="2026-10-06T00:00:00Z")

    resolved = registry.resolve(good_calendar.calendar_id)
    assert resolved == good_calendar
    assert registry.resolve_record(good_calendar.calendar_id).source_artifact_digest == good_admitted.artifact_digest
    with pytest.raises(CalendarNotVerifiedError):
        registry.resolve(bad_calendar.calendar_id)


def test_valid_case_resolves_from_the_registry_with_its_record_intact():
    """The full chain: admit -> verify -> register -> resolve."""
    admission_registry = AdmissionRegistry()
    calendar = _calendar()
    admission_id, admitted = _admit(admission_registry)
    registry = CalendarRegistry()
    registry.register_verified(calendar, admission_registry, admission_id, verified_by="radu", verified_at="2026-10-06T00:00:00Z")

    resolved = registry.resolve(calendar.calendar_id)
    assert resolved == calendar
    resolved_record = registry.resolve_record(calendar.calendar_id)
    assert resolved_record.source_artifact_digest == admitted.artifact_digest
    assert resolved_record.admission_id == admission_id
    assert resolved_record.calendar_id == calendar.calendar_id
    assert resolved_record.verified_by == "radu"


def test_registration_rejects_a_structurally_tampered_calendar():
    """A dataclasses.replace()-tampered calendar (content-address
    mismatch) must be refused at registration, not merely at the
    later require_verified_calendar_for_formal_run() gate."""
    calendar = _calendar()
    tampered = dataclasses.replace(calendar, session_dates=calendar.session_dates[:-1])
    admission_registry = AdmissionRegistry()
    admission_id, _ = _admit(admission_registry)
    registry = CalendarRegistry()
    with pytest.raises(CalendarRegistrationError, match="content-address verification failed"):
        registry.register_verified(tampered, admission_registry, admission_id, verified_by="radu", verified_at="2026-10-06T00:00:00Z")
