"""TEST 43 -- a hypothesis pointing at a DIFFERENT evaluation_run_id (or
evaluation engine/config version) than the one actually supplied is
detected (Spec #004 SS33-34)."""
import dataclasses

from hypothesis.validation.provenance import check_provenance_matches_run


def test_evaluation_run_id_mismatch_is_detected(evidence_provenance, run_registry):
    mismatched = dataclasses.replace(evidence_provenance, evaluation_run_id="run_DIFFERENT")
    ok, errors = check_provenance_matches_run(mismatched, run_registry)
    assert not ok
    assert any("evaluation_run_id" in e for e in errors)


def test_evaluation_engine_version_mismatch_is_detected(evidence_provenance, run_registry):
    mismatched = dataclasses.replace(evidence_provenance, evaluation_engine_version="v0.0.1-stale")
    ok, errors = check_provenance_matches_run(mismatched, run_registry)
    assert not ok
    assert any("evaluation_engine_version" in e for e in errors)
