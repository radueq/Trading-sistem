"""TEST 55 -- F2a/F2b, #003 straightforward mechanisms (joint
remediation design 003+004 section 9; decision registry F2a/F2b, Stage
4).

F2a (Top Finding 12a): `run_evaluation()` never recomputed
`freeze_signature_set()` on the incoming `SignatureSet` to check its
own `signature_set_id` actually matches its own `signatures`. F2b (Top
Finding 12b): nothing rejected two `EvaluationSignatureDefinition`s
sharing one `signature_id` within a `SignatureSet`, which
`record_key()` would then silently collapse into one BH entry. Both
checks sit at the top of `run_evaluation()`'s own entry gate -- fired
BEFORE any config/PIT/Discovery access, so both can be proven here
with `conn=None` and no database at all.
"""
import dataclasses

import pytest

from discovery.config.loader import load_config as load_discovery_config
from evaluation.config.loader import load_config as load_evaluation_config
from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set


def _sig(sid, label="COMPRESSION"):
    return EvaluationSignatureDefinition(
        signature_id=sid, lane_conditions=(LaneStateCondition("volatility", label),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version="cfg_x", creation_mode="PRE_REGISTERED", created_before_outcome_evaluation=True,
    )


def _call_run_evaluation(signature_set):
    # Deliberately dummy/absent conn and universe -- F2a/F2b must raise
    # BEFORE any of these are ever touched.
    return run_evaluation(
        conn=None, security_ids=[], benchmark_security_id="bench",
        development_start="2024-01-01", development_end="2024-01-31",
        signature_set=signature_set,
        discovery_config=load_discovery_config(), evaluation_config=load_evaluation_config(),
    )


def test_f2a_signature_set_id_content_mismatch_is_rejected():
    valid = freeze_signature_set([_sig("A"), _sig("B", "EXPANSION")])
    tampered = dataclasses.replace(valid, signature_set_id="sigset_TAMPERED")
    with pytest.raises(ValueError, match="F2a"):
        _call_run_evaluation(tampered)


def test_f2a_genuinely_frozen_set_is_not_rejected_by_this_check():
    # Sanity: a REAL freeze_signature_set() output must pass F2a (it
    # will go on to fail later, for unrelated reasons -- conn=None --
    # but never on the F2a ValueError specifically).
    valid = freeze_signature_set([_sig("A"), _sig("B", "EXPANSION")])
    try:
        _call_run_evaluation(valid)
    except ValueError as e:
        assert "F2a" not in str(e) and "F2b" not in str(e)
    except Exception:
        pass  # any other failure (e.g. conn=None used downstream) is expected and irrelevant here


def test_f2b_duplicate_signature_id_is_rejected_even_when_set_id_matches():
    # Built directly via freeze_signature_set() itself (never bypassing
    # it) with two DIFFERENT signatures sharing one signature_id -- its
    # own signature_set_id is therefore genuinely consistent with its
    # content (F2a passes), isolating F2b's own check.
    dup = freeze_signature_set([_sig("DUP", "COMPRESSION"), _sig("DUP", "EXPANSION")])
    with pytest.raises(ValueError, match="F2b"):
        _call_run_evaluation(dup)


def test_f2b_unique_signature_ids_are_not_rejected_by_this_check():
    valid = freeze_signature_set([_sig("A"), _sig("B", "EXPANSION")])
    try:
        _call_run_evaluation(valid)
    except ValueError as e:
        assert "F2b" not in str(e)
    except Exception:
        pass
