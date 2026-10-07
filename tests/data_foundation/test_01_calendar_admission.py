"""Calendar source ADMISSION (Step 0) -- joint remediation design
003+004 section 2; decision registry B3, revision 5-6; authorized
2026-10-06, Stage 2.

Fixture-based only (decision registry B3): no real provider is
integrated. These tests verify the admission MECHANISM, not that any
real calendar is available for a formal run.
"""
import json

import pytest

import data_foundation.calendar.admission as admission_module
from data_foundation.calendar.admission import (
    ADMISSION_METHOD_APPROVED_PROVIDER,
    ADMISSION_METHOD_OPERATOR_ATTESTATION,
    AdmissionRegistry,
    CalendarSourceNotAdmittedError,
    admit_source_via_approved_provider,
    admit_source_via_operator_attestation,
)

_RAW_FIXTURE = json.dumps({
    "session_dates": ["2024-01-02", "2024-01-03", "2024-01-04"],
    "early_close_dates": [["2024-01-03", "13:00"]],
})


@pytest.fixture
def registry():
    return AdmissionRegistry()


def test_approved_provider_admission_succeeds_when_on_the_allow_list(monkeypatch, registry):
    """`APPROVED_PROVIDERS_V1` is the mechanism's OWN trust config, not
    a caller-supplied parameter (GPT review, Stage 2 changes-required
    round) -- exercising the success path means overriding that
    module-level constant explicitly via monkeypatch, never passing an
    ad-hoc allow-list through the public function."""
    monkeypatch.setattr(admission_module, "APPROVED_PROVIDERS_V1", frozenset({"FIXTURE_EXCHANGE_FEED"}))
    admitted = admit_source_via_approved_provider(
        registry=registry, source_identifier="FIXTURE_EXCHANGE_FEED",
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
    )
    assert admitted.admission_method == ADMISSION_METHOD_APPROVED_PROVIDER
    assert admitted.attested_by is None
    assert admitted.attested_at is None
    assert admitted.raw_content == _RAW_FIXTURE
    assert registry.resolve(admitted.admission_id) is admitted


def test_approved_provider_admission_rejected_when_not_on_the_allow_list(registry):
    with pytest.raises(CalendarSourceNotAdmittedError, match="not on the approved-provider allow-list"):
        admit_source_via_approved_provider(
            registry=registry, source_identifier="UNKNOWN_FEED",
            version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
            market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
        )


def test_approved_provider_admission_rejected_in_v1_even_for_a_plausible_identifier(registry):
    """V1's own allow-list is deliberately empty (decision registry
    B3) -- no caller-supplied frozenset can make this path succeed
    without an explicit monkeypatch of the mechanism's own trust
    config."""
    assert admission_module.APPROVED_PROVIDERS_V1 == frozenset()
    with pytest.raises(CalendarSourceNotAdmittedError, match="not on the approved-provider allow-list"):
        admit_source_via_approved_provider(
            registry=registry, source_identifier="ANY_PLAUSIBLE_REAL_SOUNDING_FEED",
            version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
            market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
        )


def test_operator_attestation_admission_succeeds_with_a_named_operator(registry):
    admitted = admit_source_via_operator_attestation(
        registry=registry, source_identifier="MANUAL_NYSE_CALENDAR", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
    )
    assert admitted.admission_method == ADMISSION_METHOD_OPERATOR_ATTESTATION
    assert admitted.attested_by == "radu"
    assert admitted.attested_at == "2026-10-06T00:00:00Z"
    assert registry.resolve(admitted.admission_id) is admitted


def test_operator_attestation_rejected_when_operator_name_is_blank(registry):
    with pytest.raises(CalendarSourceNotAdmittedError, match="named human operator"):
        admit_source_via_operator_attestation(
            registry=registry, source_identifier="MANUAL_NYSE_CALENDAR", operator_name="   ", attested_at="2026-10-06T00:00:00Z",
            version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
            market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
        )


def test_operator_attestation_rejected_when_attested_at_is_blank(registry):
    with pytest.raises(CalendarSourceNotAdmittedError, match="attestation timestamp"):
        admit_source_via_operator_attestation(
            registry=registry, source_identifier="MANUAL_NYSE_CALENDAR", operator_name="radu", attested_at="",
            version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
            market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
        )


def test_artifact_digest_is_computed_from_raw_content_not_caller_supplied(registry):
    """The digest must genuinely correspond to what was retained --
    admission computes it itself, it is never a free parameter a caller
    could lie about."""
    admitted_a = admit_source_via_operator_attestation(
        registry=registry, source_identifier="X", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
    )
    admitted_b = admit_source_via_operator_attestation(
        registry=registry, source_identifier="X", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE + " ",
    )
    assert admitted_a.artifact_digest != admitted_b.artifact_digest


def test_direct_construction_of_admitted_source_is_never_resolvable_without_going_through_admission(registry):
    """GPT review, Stage 2 second changes-required round, reproduced:
    a hand-built `AdmittedCalendarSource` (never passed through either
    admit_* function) must never resolve from an `AdmissionRegistry`,
    however internally self-consistent (coherent content/digest pair,
    a plausible admission_method) it looks."""
    from data_foundation.calendar.admission import AdmittedCalendarSource, _digest

    forged = AdmittedCalendarSource(
        source_identifier="NEVER_ADMITTED_FEED", admission_method=ADMISSION_METHOD_APPROVED_PROVIDER,
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
        artifact_digest=_digest(_RAW_FIXTURE), admission_id="NEVER_RECORDED_ID", attested_by=None, attested_at=None,
    )
    with pytest.raises(CalendarSourceNotAdmittedError, match="has no linked admission"):
        registry.resolve(forged.admission_id)


def test_same_text_admitted_twice_with_different_metadata_gets_distinct_identities_both_retained(registry):
    """GPT review, Stage 2 THIRD changes-required round, reproduced:
    admission A (this text, source A, coverage to 2024-01-31) and
    admission B (the SAME text, source B, coverage to 2024-12-31) both
    succeed -- `artifact_digest` alone cannot tell them apart, so the
    registry must key by `admission_id` (digest + metadata), never by
    `artifact_digest` alone, or B would silently replace A."""
    admitted_a = admit_source_via_operator_attestation(
        registry=registry, source_identifier="SOURCE_A", operator_name="operator_a", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
    )
    admitted_b = admit_source_via_operator_attestation(
        registry=registry, source_identifier="SOURCE_B", operator_name="operator_b", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-12-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
    )
    # Same raw text -> same artifact_digest, but DIFFERENT admission_id.
    assert admitted_a.artifact_digest == admitted_b.artifact_digest
    assert admitted_a.admission_id != admitted_b.admission_id
    # BOTH snapshots are retained -- resolving A's own identity still
    # returns A, not B, even after B was admitted.
    assert registry.resolve(admitted_a.admission_id) is admitted_a
    assert registry.resolve(admitted_b.admission_id) is admitted_b
    assert registry.resolve(admitted_a.admission_id).coverage_end == "2024-01-31"
    assert registry.resolve(admitted_b.admission_id).coverage_end == "2024-12-31"


def test_repeating_the_identical_admission_is_idempotent(registry):
    """The exact same admission call, repeated verbatim, must succeed
    both times and resolve to an equal snapshot -- never raise, never
    create a second, divergent entry."""
    kwargs = dict(
        registry=registry, source_identifier="SOURCE_A", operator_name="operator_a", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
    )
    admitted_first = admit_source_via_operator_attestation(**kwargs)
    admitted_second = admit_source_via_operator_attestation(**kwargs)
    assert admitted_first.admission_id == admitted_second.admission_id
    assert admitted_first == admitted_second
    assert registry.resolve(admitted_first.admission_id) == admitted_first
