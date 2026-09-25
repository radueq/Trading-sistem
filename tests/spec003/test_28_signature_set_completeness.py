"""TEST 28 -- Signature set completeness (Spec #003 SS26/SS66).

Same signature list -> same signature_set_id (reproducible); a
different list (one added/removed) -> a DIFFERENT id, visibly -- never
a silent post-hoc mutation of "which signatures were tested."
"""
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set


def _sig(sid, label):
    return EvaluationSignatureDefinition(
        signature_id=sid, lane_conditions=(LaneStateCondition("volatility", label),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version="cfg_x", creation_mode="PRE_REGISTERED", created_before_outcome_evaluation=True,
    )


def test_same_set_reproduces_same_id():
    s1 = freeze_signature_set([_sig("A", "COMPRESSION"), _sig("B", "EXPANSION")])
    s2 = freeze_signature_set([_sig("B", "EXPANSION"), _sig("A", "COMPRESSION")])  # different order
    assert s1.signature_set_id == s2.signature_set_id


def test_adding_a_signature_changes_the_id():
    s1 = freeze_signature_set([_sig("A", "COMPRESSION")])
    s2 = freeze_signature_set([_sig("A", "COMPRESSION"), _sig("B", "EXPANSION")])
    assert s1.signature_set_id != s2.signature_set_id
