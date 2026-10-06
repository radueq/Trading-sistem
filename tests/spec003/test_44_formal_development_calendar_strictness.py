"""TEST 44 -- #003's own FORMAL_DEVELOPMENT calendar strictness
(joint remediation design 003+004, section 2; decision registry B1,
revision 5-6; authorized 2026-10-06, Stage 2).

`run_evaluation()`'s NEW, OPTIONAL `calendar_registry`/`calendar_id`
parameters resolve a calendar EXCLUSIVELY by identity, through the same
registry/consumption rule `data_foundation.calendar` already enforces.
B1's own "Verification needed": a FORMAL_DEVELOPMENT run REFUSES a
SYNTHETIC_TEST_FIXTURE calendar and SUCCEEDS against one resolved from
the registry with its CalendarVerificationRecord intact. Omitting both
parameters (every other test in this suite) is the unaffected default
path.
"""
import json

import pytest

from data_foundation.calendar.admission import admit_source_via_operator_attestation
from data_foundation.calendar.contract import build_trading_calendar
from data_foundation.calendar.entities import CalendarNotVerifiedError, CalendarSource
from data_foundation.calendar.registry import (
    VERIFICATION_METHOD_VERSION_V1,
    CalendarRegistry,
    CalendarVerificationRecord,
    verify_calendar_against_source,
)
from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START
from spec003.fixtures.tiny_universe import DATES


def _signature(discovery_config_version):
    return EvaluationSignatureDefinition(
        signature_id="VOLATILITY_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=discovery_config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )


def _calendar(source):
    kwargs = dict(
        source=source, calendar_identifier="SPEC003_TEST_FIXTURE", calendar_version="v1",
        market="US_EQUITIES", timezone="America/New_York",
        coverage_start=DATES[0], coverage_end=DATES[-1], session_dates=tuple(DATES),
        session_open_time="09:30", session_close_time="16:00",
    )
    if source == CalendarSource.OFFICIAL_VERIFIED.value:
        kwargs["verified_by"] = "radu"
        kwargs["verified_at"] = "2026-10-06T00:00:00Z"
    return build_trading_calendar(**kwargs)


def test_formal_development_run_refuses_a_synthetic_test_fixture_calendar(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config,
):
    calendar = _calendar(CalendarSource.SYNTHETIC_TEST_FIXTURE.value)
    registry = CalendarRegistry()
    raw = json.dumps({"session_dates": list(calendar.session_dates), "early_close_dates": []})
    admitted = admit_source_via_operator_attestation(
        source_identifier="X", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date=DATES[0], coverage_start=calendar.coverage_start,
        coverage_end=calendar.coverage_end, market=calendar.market, timezone=calendar.timezone, raw_content=raw,
    )
    record = CalendarVerificationRecord(
        calendar_id=calendar.calendar_id, calendar_hash=calendar.calendar_hash,
        source_artifact_digest=admitted.artifact_digest, verification_method_version=VERIFICATION_METHOD_VERSION_V1,
        verified_by="radu", verified_at="2026-10-06T00:00:00Z",
    )
    registry.register_verified(calendar, record)

    sigset = freeze_signature_set([_signature(reduced_discovery_config.config_version)])
    with pytest.raises(CalendarNotVerifiedError):
        run_evaluation(
            conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
            COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
            calendar_registry=registry, calendar_id=calendar.calendar_id,
        )


def test_formal_development_run_succeeds_against_a_registry_resolved_official_verified_calendar(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config,
):
    calendar = _calendar(CalendarSource.OFFICIAL_VERIFIED.value)
    raw = json.dumps({"session_dates": list(calendar.session_dates), "early_close_dates": []})
    admitted = admit_source_via_operator_attestation(
        source_identifier="X", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date=DATES[0], coverage_start=calendar.coverage_start,
        coverage_end=calendar.coverage_end, market=calendar.market, timezone=calendar.timezone, raw_content=raw,
    )
    ok, errors = verify_calendar_against_source(
        calendar.session_dates, calendar.early_close_dates, calendar.market, calendar.timezone, admitted,
    )
    assert ok, errors
    record = CalendarVerificationRecord(
        calendar_id=calendar.calendar_id, calendar_hash=calendar.calendar_hash,
        source_artifact_digest=admitted.artifact_digest, verification_method_version=VERIFICATION_METHOD_VERSION_V1,
        verified_by="radu", verified_at="2026-10-06T00:00:00Z",
    )
    registry = CalendarRegistry()
    registry.register_verified(calendar, record)

    sigset = freeze_signature_set([_signature(reduced_discovery_config.config_version)])
    profiles, run_registry = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
        calendar_registry=registry, calendar_id=calendar.calendar_id,
    )
    assert profiles
    assert run_registry.evaluation_run_id.startswith("run_")


def test_calendar_registry_without_calendar_id_raises_value_error(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config,
):
    """calendar_registry/calendar_id must be supplied TOGETHER -- one
    alone is a caller error, never a silent fallback to the legacy
    (non-calendar) path."""
    sigset = freeze_signature_set([_signature(reduced_discovery_config.config_version)])
    with pytest.raises(ValueError, match="must be supplied TOGETHER"):
        run_evaluation(
            conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
            COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
            calendar_registry=CalendarRegistry(),
        )
