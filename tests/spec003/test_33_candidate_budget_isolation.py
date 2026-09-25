"""TEST 33 -- Candidate Budget isolation (Spec #003 SS23/SS66,
IMPLEMENTATION BLOCKER Sec.74A).

Changing max_candidates must NOT alter the Evidence generated from
pre-budget observations -- proven from Evaluation's own consuming side
(Spec #002's TEST 24 proves the same property at the source).
"""
from dataclasses import replace

from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START


def test_changing_max_candidates_does_not_change_evidence_profiles(conn, tiny_universe, reduced_discovery_config, fast_evaluation_config):
    sig = EvaluationSignatureDefinition(
        signature_id="VOLATILITY_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=reduced_discovery_config.config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )
    sigset = freeze_signature_set([sig])

    default_cfg = reduced_discovery_config
    tiny_budget_cfg = replace(
        reduced_discovery_config,
        discovery={**reduced_discovery_config.discovery, "candidate_budget": {"enabled": True, "max_candidates": 1}},
    )

    profiles_default, _ = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, default_cfg, fast_evaluation_config,
    )
    profiles_tiny_budget, _ = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, tiny_budget_cfg, fast_evaluation_config,
    )

    assert profiles_default == profiles_tiny_budget, (
        "Evaluation's dataset must be built from compute_discovery_observations(), never run_discovery()'s "
        "post-budget output -- max_candidates must have zero effect here"
    )
