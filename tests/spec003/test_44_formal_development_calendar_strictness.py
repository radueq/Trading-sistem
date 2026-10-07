"""TEST 44 -- #003's own FORMAL_DEVELOPMENT calendar strictness
(joint remediation design 003+004, section 2; decision registry B1,
revision 5-6; authorized 2026-10-06, Stage 2; CORRECTED this round per
GPT's own changes-required review).

CORRECTED: a FORMAL_DEVELOPMENT run can no longer OMIT the calendar
and silently fall back to the legacy, benchmark-bar-derived session
resolution -- `run_evaluation()` now REQUIRES `calendar_registry`/
`calendar_id` together whenever `mode == "FORMAL_DEVELOPMENT"`,
checked BEFORE any PIT/Discovery data access, mirroring every other
FORMAL_DEVELOPMENT guard already enforced (signature pre-registration,
provenance). EXPLORATORY mode still accepts both omitted -- that path
is exercised elsewhere, unaffected by this file.

`register_verified()` is also corrected this round (see test_03): it
now EXECUTES the admit->verify chain itself and builds the
`CalendarVerificationRecord` internally -- a caller can no longer
hand it a pre-built record.
"""
import json

import pytest

from data_foundation.calendar.admission import AdmissionRegistry, admit_source_via_operator_attestation
from data_foundation.calendar.contract import build_trading_calendar
from data_foundation.calendar.entities import CalendarNotVerifiedError, CalendarSource
from data_foundation.calendar.registry import CalendarRegistry
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


def _calendar(source, calendar_identifier="SPEC003_TEST_FIXTURE"):
    kwargs = dict(
        source=source, calendar_identifier=calendar_identifier, calendar_version="v1",
        market="US_EQUITIES", timezone="America/New_York",
        coverage_start=DATES[0], coverage_end=DATES[-1], session_dates=tuple(DATES),
        session_open_time="09:30", session_close_time="16:00",
    )
    if source == CalendarSource.OFFICIAL_VERIFIED.value:
        kwargs["verified_by"] = "radu"
        kwargs["verified_at"] = "2026-10-06T00:00:00Z"
    return build_trading_calendar(**kwargs)


def _admit_and_register(registry, calendar):
    admission_registry = AdmissionRegistry()
    raw = json.dumps({"session_dates": list(calendar.session_dates), "early_close_dates": []})
    admitted = admit_source_via_operator_attestation(
        registry=admission_registry, source_identifier="X", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date=DATES[0], coverage_start=calendar.coverage_start,
        coverage_end=calendar.coverage_end, market=calendar.market, timezone=calendar.timezone, raw_content=raw,
    )
    registry.register_verified(
        calendar, admission_registry, admitted.artifact_digest, verified_by="radu", verified_at="2026-10-06T00:00:00Z",
    )


def test_formal_development_requires_a_calendar_both_arguments_omitted(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config,
):
    assert fast_evaluation_config.data["evaluation_mode"] == "FORMAL_DEVELOPMENT"
    sigset = freeze_signature_set([_signature(reduced_discovery_config.config_version)])
    with pytest.raises(CalendarNotVerifiedError, match="CALENDAR_UNVERIFIED"):
        run_evaluation(
            conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
            COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
        )


def test_formal_development_rejects_a_single_calendar_argument_supplied_alone(
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


def test_formal_development_refuses_an_unregistered_calendar_id(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config,
):
    """A calendar_id the registry has never registered (typo, wrong
    id, or simply never admitted) is refused exactly like
    CalendarRegistry.resolve() itself refuses it -- never silently
    treated as 'no calendar'."""
    sigset = freeze_signature_set([_signature(reduced_discovery_config.config_version)])
    with pytest.raises(CalendarNotVerifiedError, match="CALENDAR_UNVERIFIED"):
        run_evaluation(
            conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
            COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
            calendar_registry=CalendarRegistry(), calendar_id="cal_never_registered",
        )


def test_formal_development_run_refuses_a_synthetic_test_fixture_calendar(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config,
):
    calendar = _calendar(CalendarSource.SYNTHETIC_TEST_FIXTURE.value)
    registry = CalendarRegistry()
    _admit_and_register(registry, calendar)

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
    registry = CalendarRegistry()
    _admit_and_register(registry, calendar)

    sigset = freeze_signature_set([_signature(reduced_discovery_config.config_version)])
    profiles, run_registry = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
        calendar_registry=registry, calendar_id=calendar.calendar_id,
    )
    assert profiles
    assert run_registry.evaluation_run_id.startswith("run_")
    assert run_registry.calendar_id == calendar.calendar_id
