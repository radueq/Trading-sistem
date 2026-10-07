"""Calendar verification against an ADMITTED source (Step 3) -- joint
remediation design 003+004 section 2; decision registry B1-B4,
revision 5-6; authorized 2026-10-06, Stage 2.

Comparing a candidate against an UNADMITTED artifact is not this
module's job (admission is Step 0, separate and prior) -- these tests
always start from an already-admitted source.
"""
import json

from data_foundation.calendar.admission import AdmissionRegistry, admit_source_via_operator_attestation
from data_foundation.calendar.registry import verify_calendar_against_source

_SESSIONS = ("2024-01-02", "2024-01-03", "2024-01-04")
_CLOSES = (("2024-01-03", "13:00"),)


def _admitted(session_dates=_SESSIONS, early_close_dates=_CLOSES, market="US_EQUITIES", timezone="America/New_York"):
    raw = json.dumps({"session_dates": list(session_dates), "early_close_dates": [list(p) for p in early_close_dates]})
    return admit_source_via_operator_attestation(
        registry=AdmissionRegistry(), source_identifier="X", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date="2024-01-01", coverage_start="2024-01-01", coverage_end="2024-01-31",
        market=market, timezone=timezone, raw_content=raw,
    )


def test_matching_candidate_is_verified():
    ok, errors = verify_calendar_against_source(_SESSIONS, _CLOSES, "US_EQUITIES", "America/New_York", _admitted())
    assert ok, errors


def test_missing_session_date_is_rejected():
    ok, errors = verify_calendar_against_source(
        ("2024-01-02", "2024-01-04"), _CLOSES, "US_EQUITIES", "America/New_York", _admitted(),
    )
    assert not ok
    assert any("missing session dates" in e for e in errors)


def test_extra_session_date_is_rejected():
    ok, errors = verify_calendar_against_source(
        _SESSIONS + ("2024-01-05",), _CLOSES, "US_EQUITIES", "America/New_York", _admitted(),
    )
    assert not ok
    assert any("session dates not present in the admitted source" in e for e in errors)


def test_early_close_mismatch_is_rejected():
    ok, errors = verify_calendar_against_source(
        _SESSIONS, (("2024-01-04", "13:00"),), "US_EQUITIES", "America/New_York", _admitted(),
    )
    assert not ok
    assert any("early-close" in e for e in errors)


def test_market_mismatch_is_rejected():
    ok, errors = verify_calendar_against_source(_SESSIONS, _CLOSES, "US_OPTIONS", "America/New_York", _admitted())
    assert not ok
    assert any("market mismatch" in e for e in errors)


def test_timezone_mismatch_is_rejected():
    ok, errors = verify_calendar_against_source(_SESSIONS, _CLOSES, "US_EQUITIES", "Europe/London", _admitted())
    assert not ok
    assert any("timezone mismatch" in e for e in errors)
