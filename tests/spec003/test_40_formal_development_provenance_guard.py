"""TEST 40 -- FORMAL_DEVELOPMENT rejects a provenance mismatch (PATCH
#003-B, GPT Review #003 Round 2 guard).

The Signature Set fingerprint correctly makes a provenance change
produce a DIFFERENT `signature_set_id` (TEST 28), but nothing previously
stopped a signature pre-registered under one Discovery
config/engine/timeframe from actually being RUN against a different
one -- the two would legitimately be different entities, yet the engine
would silently accept the mismatched combination. `run_evaluation()`
must hard-error instead.
"""
import pytest

from evaluation.engine import DISCOVERY_ENGINE_VERSION, run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START


def _base_sig(**overrides):
    fields = dict(
        signature_id="VOLATILITY_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version=DISCOVERY_ENGINE_VERSION,
        discovery_config_version="cfg_x", creation_mode="PRE_REGISTERED", created_before_outcome_evaluation=True,
    )
    fields.update(overrides)
    return EvaluationSignatureDefinition(**fields)


def test_discovery_config_version_mismatch_is_rejected(conn, tiny_universe, reduced_discovery_config, fast_evaluation_config):
    sig = _base_sig(discovery_config_version="cfg_completely_different")
    sigset = freeze_signature_set([sig])
    assert sig.discovery_config_version != reduced_discovery_config.config_version, "sanity: must actually mismatch"
    with pytest.raises(ValueError, match="discovery_config_version"):
        run_evaluation(
            conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
            COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
        )


def test_discovery_engine_version_mismatch_is_rejected(conn, tiny_universe, reduced_discovery_config, fast_evaluation_config):
    sig = _base_sig(discovery_engine_version="v0.0.1-stale", discovery_config_version=reduced_discovery_config.config_version)
    sigset = freeze_signature_set([sig])
    assert sig.discovery_engine_version != DISCOVERY_ENGINE_VERSION, "sanity: must actually mismatch"
    with pytest.raises(ValueError, match="discovery_engine_version"):
        run_evaluation(
            conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
            COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
        )


def test_timeframe_mismatch_is_rejected(conn, tiny_universe, reduced_discovery_config, fast_evaluation_config):
    sig = _base_sig(timeframe="4H", discovery_config_version=reduced_discovery_config.config_version)
    sigset = freeze_signature_set([sig])
    assert fast_evaluation_config.data["timeframe"] == "1D", "sanity: must actually mismatch"
    with pytest.raises(ValueError, match="timeframe"):
        run_evaluation(
            conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
            COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
        )


def test_matching_provenance_is_accepted(conn, tiny_universe, reduced_discovery_config, fast_evaluation_config):
    sig = _base_sig(discovery_config_version=reduced_discovery_config.config_version)
    sigset = freeze_signature_set([sig])
    profiles, _ = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
    )
    assert profiles
