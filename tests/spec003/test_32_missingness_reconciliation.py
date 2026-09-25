"""TEST 32 -- Missingness reconciliation (Spec #003 SS36/SS66).

The 5 outcome-status counts must sum EXACTLY to the episode count, for
every signature x horizon -- no observation silently unaccounted for.
"""
from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START


def test_missingness_counts_sum_to_episode_count(conn, tiny_universe, reduced_discovery_config, fast_evaluation_config):
    sig = EvaluationSignatureDefinition(
        signature_id="VOLATILITY_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=reduced_discovery_config.config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )
    sigset = freeze_signature_set([sig])
    profiles, _ = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
    )
    assert profiles, "sanity: this window should produce at least some profiles"
    for p in profiles:
        m = p.missingness
        assert m.valid_outcomes + m.insufficient_future_data + m.crosses_locked_oos + m.missing_benchmark + m.invalid_input == m.episodes
        assert m.eligible_observations == m.raw_observations
