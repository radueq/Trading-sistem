"""TEST 29 -- Post-hoc labeling (Spec #003 SS27-28/SS66).

`creation_mode` (PRE_REGISTERED vs EXPLORATORY_POST_HOC, a property of a
SIGNATURE) and `evaluation_mode` (EXPLORATORY vs FORMAL_DEVELOPMENT, a
property of the RUN) are two independent concepts, never conflated.
"""
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition, SignatureCreationMode


def test_creation_mode_is_carried_unchanged_and_distinct_from_run_mode():
    pre_registered = EvaluationSignatureDefinition(
        signature_id="A", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version="cfg_x", creation_mode=SignatureCreationMode.PRE_REGISTERED.value,
        created_before_outcome_evaluation=True,
    )
    post_hoc = EvaluationSignatureDefinition(
        signature_id="B", lane_conditions=(LaneStateCondition("volatility", "EXPANSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version="cfg_x", creation_mode=SignatureCreationMode.EXPLORATORY_POST_HOC.value,
        created_before_outcome_evaluation=False,
    )
    assert pre_registered.creation_mode == "PRE_REGISTERED"
    assert post_hoc.creation_mode == "EXPLORATORY_POST_HOC"
    assert pre_registered.created_before_outcome_evaluation is True
    assert post_hoc.created_before_outcome_evaluation is False
    # the field exists on the SIGNATURE, not on the run's EvidenceProfile.evaluation_mode
    assert not hasattr(pre_registered, "evaluation_mode")
