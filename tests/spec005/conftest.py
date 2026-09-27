"""Spec #005 v1.0 test fixtures (Batch 1: contracts, provenance,
calendar; Batch 2 adds a small real SQLite-backed PIT universe).

Batch 1 tests exercise pure functions over hand-built #003/#004-shaped
objects and need no database, mirroring the established convention in
tests/spec003 and tests/spec004. Batch 2 (snapshots, bounded PIT access,
the historical observation cache) genuinely reads through
`data_foundation.pit.access`, so `pit_universe` below builds a real
`conn`-backed universe -- see `spec005.fixtures.pit_universe`.
"""
from __future__ import annotations

import pytest

from evaluation.models.entities import EvaluationRunRegistry
from evaluation.registry.runs import build_run_id
from hypothesis.models.entities import EvidenceProvenance

from backtest.data.calendar import build_trading_calendar
from backtest.models.entities import (
    CalendarSource,
    CostAssumptions,
    ExposureManifest,
    ResearchPlan,
    SelectionFold,
    SelectionRule,
    build_execution_semantics_profile_v1,
    build_research_plan_id,
    research_plan_fingerprint,
)
from fixtures.market_data import business_days

from spec005.fixtures.pit_universe import insert_price_history, make_security

SIGNATURE_ID = "VOL_COMPRESSION_RS_HIGH"
SIGNATURE_SET_ID = "sigset_x"
DISCOVERY_CONFIG_VERSION = "cfg_disc"
EVALUATION_CONFIG_VERSION = "cfg_eval"
TIMEFRAME = "1D"
BENCHMARK_SECURITY_ID = "SBENCH"
DEVELOPMENT_START = "2020-01-01"
DEVELOPMENT_END = "2024-01-01"
VALIDATION_START = "2024-02-01"
VALIDATION_END = "2024-12-31"
LOCKED_OOS_START = "2025-01-01"

_LEGACY_HASH_DEFAULTS = dict(
    development_start=DEVELOPMENT_START, development_end=DEVELOPMENT_END, timeframe=TIMEFRAME,
    signature_set_id=SIGNATURE_SET_ID, discovery_config_version=DISCOVERY_CONFIG_VERSION,
    evaluation_config_version=EVALUATION_CONFIG_VERSION, bootstrap_seed=1, comparison_seed=2,
)


def build_run_registry(**overrides) -> EvaluationRunRegistry:
    """A genuinely self-consistent EvaluationRunRegistry: `evaluation_run_id`
    is always the REAL `build_run_id()` output for the 8 legacy-hash
    fields actually stored on the object (after `overrides` are
    applied) -- never a hand-typed string. Pass `evaluation_run_id=...`
    explicitly to deliberately construct a TAMPERED object (id no longer
    matching its own fields) for a negative test."""
    hash_fields = dict(_LEGACY_HASH_DEFAULTS)
    hash_fields.update({k: v for k, v in overrides.items() if k in hash_fields})
    run_id = overrides.get("evaluation_run_id") or build_run_id(**hash_fields)
    return EvaluationRunRegistry(
        evaluation_run_id=run_id,
        created_at=overrides.get("created_at", "2026-09-26T00:00:00Z"),
        mode=overrides.get("mode", "FORMAL_DEVELOPMENT"),
        development_start=hash_fields["development_start"], development_end=hash_fields["development_end"],
        timeframe=hash_fields["timeframe"], horizons=overrides.get("horizons", (1, 2, 3, 5, 10)),
        benchmark_security_id=overrides.get("benchmark_security_id", BENCHMARK_SECURITY_ID),
        discovery_engine_version=overrides.get("discovery_engine_version", "v1.0.0"),
        discovery_config_version=hash_fields["discovery_config_version"],
        evaluation_engine_version=overrides.get("evaluation_engine_version", "v1.0.0"),
        evaluation_config_version=hash_fields["evaluation_config_version"],
        signature_set_id=hash_fields["signature_set_id"],
        bootstrap_seed=hash_fields["bootstrap_seed"], bootstrap_iterations=overrides.get("bootstrap_iterations", 200),
        comparison_seed=hash_fields["comparison_seed"], comparison_iterations=overrides.get("comparison_iterations", 200),
        multiple_testing_method=overrides.get("multiple_testing_method", "BH"),
    )


def build_evidence_provenance(run_registry: EvaluationRunRegistry, **overrides) -> EvidenceProvenance:
    return EvidenceProvenance(
        evaluation_run_id=overrides.get("evaluation_run_id", run_registry.evaluation_run_id),
        evaluation_engine_version=overrides.get("evaluation_engine_version", run_registry.evaluation_engine_version),
        evaluation_config_version=overrides.get("evaluation_config_version", run_registry.evaluation_config_version),
        signature_id=overrides.get("signature_id", SIGNATURE_ID),
        signature_set_id=overrides.get("signature_set_id", run_registry.signature_set_id),
        discovery_engine_version=overrides.get("discovery_engine_version", run_registry.discovery_engine_version),
        discovery_config_version=overrides.get("discovery_config_version", run_registry.discovery_config_version),
        timeframe=overrides.get("timeframe", run_registry.timeframe),
    )


@pytest.fixture
def run_registry() -> EvaluationRunRegistry:
    return build_run_registry()


@pytest.fixture
def evidence_provenance(run_registry) -> EvidenceProvenance:
    return build_evidence_provenance(run_registry)


# --------------------------------------------------------------------------
# Batch 2: real SQLite-backed PIT universe (snapshots, bounded access,
# observation cache, isolation tests). Deliberately unrelated to the
# DEVELOPMENT_START/END/VALIDATION_START/END/LOCKED_OOS_START constants
# above -- those describe a #003 evidence run's OWN development window;
# these describe #005's OWN research-lifecycle zones for the PIT universe.
# --------------------------------------------------------------------------

PIT_WARMUP_START = "2023-10-02"  # >= discovery's minimum_history_days=60 by PIT_FORMATION_END
PIT_FORMATION_START = "2024-01-02"
PIT_FORMATION_END = "2024-01-31"
PIT_VALIDATION_START = "2024-02-01"
PIT_VALIDATION_END = "2024-02-29"
PIT_LOCKED_OOS_START = "2024-03-01"
PIT_UNIVERSE_END = "2024-03-29"


@pytest.fixture
def pit_universe(conn, now):
    """Two priced securities + a benchmark, each with price history from
    PIT_WARMUP_START (well before FORMATION_SELECTION starts, so that by
    PIT_FORMATION_END they already clear discovery's own
    `minimum_history_days: 60` eligibility floor -- legitimate warm-up
    per Spec #005 SS3: "Warm-up data before a zone may be read to
    compute already-frozen rolling features") through PIT_UNIVERSE_END
    (spanning FORMATION_SELECTION -> DEVELOPMENT_VALIDATION ->
    LOCKED_OOS). Plus one security with NO price history at all
    (deterministic "missing observation" case for the cache tests --
    `compute_discovery_observations()` skips a security with zero bars
    unconditionally, never dependent on eligibility-threshold tuning)."""
    sec_a = make_security(conn, "spec005:SEC_A", now)
    sec_b = make_security(conn, "spec005:SEC_B", now)
    sec_nodata = make_security(conn, "spec005:SEC_NODATA", now)
    benchmark = make_security(conn, "spec005:BENCH", now)
    insert_price_history(conn, sec_a, now, PIT_WARMUP_START, PIT_UNIVERSE_END, base_price=100.0, daily_drift=0.05)
    insert_price_history(conn, sec_b, now, PIT_WARMUP_START, PIT_UNIVERSE_END, base_price=50.0, daily_drift=-0.02)
    insert_price_history(conn, benchmark, now, PIT_WARMUP_START, PIT_UNIVERSE_END, base_price=200.0, daily_drift=0.02)
    return {
        "sec_a": sec_a, "sec_b": sec_b, "sec_nodata": sec_nodata, "benchmark_security_id": benchmark,
        "priced_security_ids": (sec_a, sec_b),
        "security_ids_with_nodata": (sec_a, sec_b, sec_nodata),
    }


@pytest.fixture
def pit_calendar():
    """A real, verified, content-addressed TradingCalendar whose
    session_dates match exactly the business-day range `pit_universe`'s
    price history is built over (both use `fixtures.market_data`'s own
    `business_days()`) -- required so `build_data_snapshot()`'s
    per-session ticker/listing history loop has real session dates to
    iterate over."""
    session_dates = tuple(business_days(PIT_WARMUP_START, PIT_UNIVERSE_END))
    return build_trading_calendar(
        source=CalendarSource.OFFICIAL_VERIFIED.value, calendar_identifier="SPEC005_TEST_CALENDAR",
        calendar_version="v1", market="US_EQUITIES", timezone="America/New_York",
        coverage_start=PIT_WARMUP_START, coverage_end=PIT_UNIVERSE_END, session_dates=session_dates,
        session_open_time="09:30", session_close_time="16:00",
        verified_by="test", verified_at="2026-09-27T00:00:00Z",
    )


@pytest.fixture
def pit_research_plan(pit_universe, pit_calendar) -> ResearchPlan:
    """A genuinely self-consistent, content-addressed ResearchPlan
    binding PIT_FORMATION_END/PIT_VALIDATION_END/PIT_LOCKED_OOS_START to
    `pit_calendar`'s own calendar_id and `pit_universe`'s own benchmark
    -- the one plan `build_stage_access_boundary_from_plan()` and
    `StageReadContext` are tested against."""
    profile = build_execution_semantics_profile_v1()
    rule = SelectionRule(minimum_executed_trades=1, minimum_evaluable_trades=1, minimum_evaluable_ratio=0.5)
    costs = CostAssumptions(
        commission_entry_rate=0.0005, commission_exit_rate=0.0005,
        slippage_entry_bps=5.0, slippage_exit_bps=5.0, borrow_annual_rate=0.0,
    )
    exposure = ExposureManifest(declared_unseen=True)
    folds = (SelectionFold("fold_1", PIT_FORMATION_START, PIT_FORMATION_END),)
    fields = dict(
        formation_start=PIT_FORMATION_START, formation_end=PIT_FORMATION_END,
        validation_start=PIT_VALIDATION_START, validation_end=PIT_VALIDATION_END,
        locked_oos_start=PIT_LOCKED_OOS_START, selection_folds=folds,
        hypothesis_cohort_ids=("hyp_a",), trading_calendar_id=pit_calendar.calendar_id,
        benchmark_security_id=pit_universe["benchmark_security_id"],
        execution_semantics_profile_id=profile.profile_id, selection_rule=rule,
        cost_assumptions=costs, exposure_manifest=exposure,
    )
    fp = research_plan_fingerprint(**fields)
    plan_id, plan_hash = build_research_plan_id(fp)
    return ResearchPlan(
        research_plan_id=plan_id, plan_hash=plan_hash,
        created_at="2026-09-27T00:00:00Z", created_by="test", **fields,
    )
