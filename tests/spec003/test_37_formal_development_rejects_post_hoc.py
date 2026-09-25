"""TEST 37 -- FORMAL_DEVELOPMENT rejects a post-hoc signature (PATCH
#003-A, GPT Review #003 Round 1, mandatory finding #3).

A frozen Signature Set (SS26) is meaningless if a signature created
AFTER looking at outcomes (EXPLORATORY_POST_HOC) can still run through
a FORMAL_DEVELOPMENT evaluation -- this must be a hard, fast error, not
silently accepted.
"""
import pytest

from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START


def test_post_hoc_signature_raises_in_formal_development(conn, tiny_universe, reduced_discovery_config, fast_evaluation_config):
    post_hoc_sig = EvaluationSignatureDefinition(
        signature_id="POST_HOC_SIG", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=reduced_discovery_config.config_version,
        creation_mode="EXPLORATORY_POST_HOC", created_before_outcome_evaluation=False,
    )
    sigset = freeze_signature_set([post_hoc_sig])
    assert fast_evaluation_config.data["evaluation_mode"] == "FORMAL_DEVELOPMENT"

    with pytest.raises(ValueError, match="PRE_REGISTERED"):
        run_evaluation(
            conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
            COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
        )


def test_pre_registered_but_not_marked_created_before_outcome_evaluation_also_rejected(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config,
):
    inconsistent_sig = EvaluationSignatureDefinition(
        signature_id="INCONSISTENT_SIG", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=reduced_discovery_config.config_version,
        creation_mode="PRE_REGISTERED", created_before_outcome_evaluation=False,
    )
    sigset = freeze_signature_set([inconsistent_sig])
    with pytest.raises(ValueError, match="created_before_outcome_evaluation"):
        run_evaluation(
            conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
            COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
        )
