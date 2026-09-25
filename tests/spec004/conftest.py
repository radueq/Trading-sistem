"""Spec #004 v1.0 test fixtures.

No PIT/ingestion/database is needed anywhere in this test package -- #004
consumes only already-materialized #003 artifacts (EvaluationSignature
Definition, EvidenceProfile, EvaluationRunRegistry), so every fixture
here is a hand-built, fully synthetic, deterministic object. Mirrors the
project's established discipline (Spec #002/#003's own hand-constructed
unit fixtures) rather than re-running the full Discovery/Evaluation
pipeline just to get inputs #004 never needed a live pipeline for.
"""
from __future__ import annotations

import pytest

from discovery.config.loader import load_config as load_discovery_config
from evaluation.models.entities import (
    BaselineComparison,
    ConcentrationStats,
    DescriptiveStats,
    EvaluationRunRegistry,
    EvidenceProfile,
    LaneStateCondition as ELaneStateCondition,
    MissingnessReport,
    OpportunityDensity,
    StabilityBinResult,
    SupportInfo,
)
from evaluation.models.entities import EvaluationSignatureDefinition

from hypothesis.config.loader import load_config as load_hypothesis_config
from hypothesis.models.entities import (
    EntryDefinition,
    EvidenceProvenance,
    HorizonCandidateSet,
    LaneStateCondition,
)
from hypothesis.registry.hypotheses import HypothesisRegistry

SIGNATURE_ID = "VOL_COMPRESSION_RS_HIGH"
EVALUATION_RUN_ID = "run_x"
SIGNATURE_SET_ID = "sigset_x"
DISCOVERY_CONFIG_VERSION = "cfg_disc"
EVALUATION_CONFIG_VERSION = "cfg_eval"
TIMEFRAME = "1D"


@pytest.fixture
def discovery_config():
    return load_discovery_config()


@pytest.fixture
def hypothesis_config():
    return load_hypothesis_config()


@pytest.fixture
def registry():
    return HypothesisRegistry()


@pytest.fixture
def signature_definition():
    return EvaluationSignatureDefinition(
        signature_id=SIGNATURE_ID,
        lane_conditions=(
            ELaneStateCondition("volatility", "COMPRESSION"),
            ELaneStateCondition("relative_strength", "VERY_HIGH"),
        ),
        reason_code_conditions=(),
        timeframe=TIMEFRAME,
        discovery_engine_version="v1.0.0",
        discovery_config_version=DISCOVERY_CONFIG_VERSION,
        creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )


@pytest.fixture
def evidence_provenance():
    return EvidenceProvenance(
        evaluation_run_id=EVALUATION_RUN_ID,
        evaluation_engine_version="v1.0.0",
        evaluation_config_version=EVALUATION_CONFIG_VERSION,
        signature_id=SIGNATURE_ID,
        signature_set_id=SIGNATURE_SET_ID,
        discovery_engine_version="v1.0.0",
        discovery_config_version=DISCOVERY_CONFIG_VERSION,
        timeframe=TIMEFRAME,
    )


@pytest.fixture
def run_registry():
    return EvaluationRunRegistry(
        evaluation_run_id=EVALUATION_RUN_ID, created_at="2026-09-25T00:00:00Z", mode="FORMAL_DEVELOPMENT",
        development_start="2020-01-01", development_end="2024-01-01", timeframe=TIMEFRAME,
        horizons=(1, 2, 3, 5, 10), benchmark_security_id="SBENCH", discovery_engine_version="v1.0.0",
        discovery_config_version=DISCOVERY_CONFIG_VERSION, evaluation_engine_version="v1.0.0",
        evaluation_config_version=EVALUATION_CONFIG_VERSION, signature_set_id=SIGNATURE_SET_ID,
        bootstrap_seed=1, bootstrap_iterations=200, comparison_seed=2, comparison_iterations=200,
        multiple_testing_method="BH",
    )


@pytest.fixture
def entry_definition():
    return EntryDefinition(core_conditions=(
        LaneStateCondition("volatility", "COMPRESSION"),
        LaneStateCondition("relative_strength", "VERY_HIGH"),
    ))


@pytest.fixture
def horizon_candidates():
    return HorizonCandidateSet(unit="BARS", values=(2, 3, 5), selection_basis="decay concentrated in the 2-5 bar zone")


def make_evidence_profile(
    horizon_bars: int, mean_relative: float = 0.006, adjusted_p: float | None = 0.03,
    valid_episode_n: int = 40, unique_security_count: int = 12, stability=(), warnings=(),
) -> EvidenceProfile:
    return EvidenceProfile(
        signature_id=SIGNATURE_ID, timeframe=TIMEFRAME, horizon_bars=horizon_bars, evaluation_mode="FORMAL_DEVELOPMENT",
        support=SupportInfo(
            raw_n=valid_episode_n + 5, episode_n=valid_episode_n + 2, valid_episode_n=valid_episode_n,
            unique_security_count=unique_security_count, support_status="SUFFICIENT",
        ),
        opportunity_density=OpportunityDensity(
            episode_count=valid_episode_n, episodes_per_20_sessions=1.2, episodes_per_60_sessions=3.5,
            median_sessions_between_episodes=15.0,
        ),
        absolute_outcome=DescriptiveStats(
            n=valid_episode_n, mean=0.01, median=0.008, std=0.02, q10=-0.01, q25=0.0, q75=0.02, q90=0.03,
            positive_rate=0.6, confidence_interval=None,
        ),
        relative_outcome=DescriptiveStats(
            n=valid_episode_n, mean=mean_relative, median=mean_relative * 0.9, std=0.015, q10=-0.005,
            q25=0.001, q75=0.015, q90=0.02, positive_rate=0.62, confidence_interval=None,
        ),
        baseline_comparison=BaselineComparison(
            baseline_mean=0.001, baseline_median=0.0008, mean_difference=mean_relative - 0.001,
            median_difference=mean_relative * 0.9 - 0.0008, mean_difference_ci=None, standardized_effect=0.3,
            standardized_effect_status="OK", raw_p=0.02, adjusted_p=adjusted_p, family_id="fam",
            multiple_testing_method="BH",
        ),
        concentration=ConcentrationStats(unique_security_count=unique_security_count, largest_security_share_of_episodes=0.2),
        stability=stability,
        missingness=MissingnessReport(
            eligible_observations=100, raw_observations=90, episodes=valid_episode_n + 2, valid_outcomes=valid_episode_n,
            insufficient_future_data=1, crosses_locked_oos=0, missing_benchmark=0, invalid_input=1,
        ),
        warnings=warnings,
    )


@pytest.fixture
def profiles_all_horizons():
    return [
        make_evidence_profile(1, mean_relative=0.002, adjusted_p=0.20, stability=(StabilityBinResult("early", 13, 5, 0.002, 0.001, 0.002, 0.55),)),
        make_evidence_profile(2, mean_relative=0.006, adjusted_p=0.05, stability=(StabilityBinResult("early", 13, 5, 0.006, 0.005, 0.006, 0.6),)),
        make_evidence_profile(3, mean_relative=0.010, adjusted_p=0.03, stability=(StabilityBinResult("early", 13, 5, 0.010, 0.009, 0.010, 0.62),)),
        make_evidence_profile(5, mean_relative=0.009, adjusted_p=0.04, stability=(StabilityBinResult("early", 13, 5, 0.009, 0.008, 0.009, 0.61),)),
        make_evidence_profile(10, mean_relative=0.001, adjusted_p=0.5, stability=(StabilityBinResult("early", 13, 5, 0.001, 0.001, 0.001, 0.51),)),
    ]


def make_proposal_raw(**overrides) -> dict:
    raw = {
        "proposal_id": "prop_1",
        "source_evidence": {
            "evaluation_run_id": EVALUATION_RUN_ID, "evaluation_engine_version": "v1.0.0",
            "evaluation_config_version": EVALUATION_CONFIG_VERSION, "signature_id": SIGNATURE_ID,
            "signature_set_id": SIGNATURE_SET_ID, "discovery_engine_version": "v1.0.0",
            "discovery_config_version": DISCOVERY_CONFIG_VERSION, "timeframe": TIMEFRAME,
        },
        "direction": "LONG", "direction_basis": "EVIDENCE_SIGN",
        "entry_definition": {"core_conditions": [
            {"lane": "volatility", "label": "COMPRESSION"}, {"lane": "relative_strength", "label": "VERY_HIGH"},
        ]},
        "entry_execution_policy": "NEXT_BAR_OPEN",
        "horizon_candidates": {"unit": "BARS", "values": [2, 3, 5], "selection_basis": "decay concentrated in the 2-5 bar zone"},
        "exit_hypotheses": [{
            "exit_family": "SIGNAL_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
            "exit_execution_policy": "BAR_CLOSE", "parameter_source": "EVIDENCE_DERIVED", "max_holding_bars": 5,
            "invalidation_conditions": [{"lane": "relative_strength", "holds_labels": ["HIGH", "VERY_HIGH"]}],
        }],
        "facts_from_evidence": ["relative return peaks near 3 bars in Development"],
        "interpretation": "compression + strong RS could represent stored volatility in a leader",
        "proposer": "AGENT:claude", "created_at": "2026-09-25T00:00:00Z",
    }
    raw.update(overrides)
    return raw
