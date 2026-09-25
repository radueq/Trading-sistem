"""TEST 16 -- Minimum unique-security support (Spec #003 SS46/SS66).

support_status must also gate on unique_security_count, independent of
episode_count -- many episodes from ONE security is not enough support.
"""
from dataclasses import replace

from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition, SupportStatus
from evaluation.registry.signatures import freeze_signature_set

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START


def test_support_insufficient_when_unique_securities_below_threshold(conn, tiny_universe, reduced_discovery_config, fast_evaluation_config):
    sig = EvaluationSignatureDefinition(
        signature_id="VOLATILITY_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=reduced_discovery_config.config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )
    sigset = freeze_signature_set([sig])
    high_security_threshold_cfg = replace(fast_evaluation_config, data={
        **fast_evaluation_config.data, "support": {"minimum_episode_count": 1, "minimum_unique_securities": 999},
    })
    profiles, _ = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, high_security_threshold_cfg,
    )
    # tiny_universe has only 3 non-benchmark securities -- can never reach 999
    assert all(p.support.support_status == SupportStatus.INSUFFICIENT.value for p in profiles)
    assert all(p.support.unique_security_count <= 3 for p in profiles)
