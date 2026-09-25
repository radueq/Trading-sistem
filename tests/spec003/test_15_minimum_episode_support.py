"""TEST 15 -- Minimum episode support (Spec #003 SS46/SS66).

support_status is INSUFFICIENT when episode_n < minimum_episode_count,
SUFFICIENT otherwise -- never silently ignored.
"""
from dataclasses import replace

from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition, SupportStatus
from evaluation.registry.signatures import freeze_signature_set

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START


def _signature(discovery_config_version):
    return EvaluationSignatureDefinition(
        signature_id="VOLATILITY_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=discovery_config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )


def test_support_insufficient_when_episode_count_below_threshold(conn, tiny_universe, reduced_discovery_config, fast_evaluation_config):
    sigset = freeze_signature_set([_signature(reduced_discovery_config.config_version)])
    high_threshold_cfg = replace(fast_evaluation_config, data={
        **fast_evaluation_config.data, "support": {"minimum_episode_count": 999, "minimum_unique_securities": 1},
    })
    profiles, _ = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, high_threshold_cfg,
    )
    assert all(p.support.support_status == SupportStatus.INSUFFICIENT.value for p in profiles)


def test_support_sufficient_when_episode_count_meets_threshold(conn, tiny_universe, reduced_discovery_config, fast_evaluation_config):
    sigset = freeze_signature_set([_signature(reduced_discovery_config.config_version)])
    profiles, _ = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
    )
    assert any(p.support.support_status == SupportStatus.SUFFICIENT.value for p in profiles)
