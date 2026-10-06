"""Calendar source ADMISSION (Step 0) -- joint remediation design
003+004 section 2; decision registry B3, revision 5-6; authorized
2026-10-06, Stage 2.

Fixture-based only (decision registry B3): no real provider is
integrated. These tests verify the admission MECHANISM, not that any
real calendar is available for a formal run.
"""
import json

import pytest

from data_foundation.calendar.admission import (
    ADMISSION_METHOD_APPROVED_PROVIDER,
    ADMISSION_METHOD_OPERATOR_ATTESTATION,
    CalendarSourceNotAdmittedError,
    admit_source_via_approved_provider,
    admit_source_via_operator_attestation,
)

_RAW_FIXTURE = json.dumps({
    "session_dates": ["2024-01-02", "2024-01-03", "2024-01-04"],
    "early_close_dates": [["2024-01-03", "13:00"]],
})


def test_approved_provider_admission_succeeds_when_on_the_allow_list():
    admitted = admit_source_via_approved_provider(
        source_identifier="FIXTURE_EXCHANGE_FEED", approved_providers=frozenset({"FIXTURE_EXCHANGE_FEED"}),
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
    )
    assert admitted.admission_method == ADMISSION_METHOD_APPROVED_PROVIDER
    assert admitted.attested_by is None
    assert admitted.attested_at is None
    assert admitted.raw_content == _RAW_FIXTURE


def test_approved_provider_admission_rejected_when_not_on_the_allow_list():
    with pytest.raises(CalendarSourceNotAdmittedError, match="not on the approved-provider allow-list"):
        admit_source_via_approved_provider(
            source_identifier="UNKNOWN_FEED", approved_providers=frozenset({"FIXTURE_EXCHANGE_FEED"}),
            version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
            market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
        )


def test_operator_attestation_admission_succeeds_with_a_named_operator():
    admitted = admit_source_via_operator_attestation(
        source_identifier="MANUAL_NYSE_CALENDAR", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
    )
    assert admitted.admission_method == ADMISSION_METHOD_OPERATOR_ATTESTATION
    assert admitted.attested_by == "radu"
    assert admitted.attested_at == "2026-10-06T00:00:00Z"


def test_operator_attestation_rejected_when_operator_name_is_blank():
    with pytest.raises(CalendarSourceNotAdmittedError, match="named human operator"):
        admit_source_via_operator_attestation(
            source_identifier="MANUAL_NYSE_CALENDAR", operator_name="   ", attested_at="2026-10-06T00:00:00Z",
            version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
            market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
        )


def test_operator_attestation_rejected_when_attested_at_is_blank():
    with pytest.raises(CalendarSourceNotAdmittedError, match="attestation timestamp"):
        admit_source_via_operator_attestation(
            source_identifier="MANUAL_NYSE_CALENDAR", operator_name="radu", attested_at="",
            version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
            market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
        )


def test_artifact_digest_is_computed_from_raw_content_not_caller_supplied():
    """The digest must genuinely correspond to what was retained --
    admission computes it itself, it is never a free parameter a caller
    could lie about."""
    admitted_a = admit_source_via_operator_attestation(
        source_identifier="X", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE,
    )
    admitted_b = admit_source_via_operator_attestation(
        source_identifier="X", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market="US_EQUITIES", timezone="America/New_York", raw_content=_RAW_FIXTURE + " ",
    )
    assert admitted_a.artifact_digest != admitted_b.artifact_digest
