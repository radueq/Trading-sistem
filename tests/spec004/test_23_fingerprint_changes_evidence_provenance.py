"""TEST 23 -- fingerprint changes if Evidence provenance changes (Spec
#004 SS33-34 -- a new evaluation_run_id/config means a NEW hypothesis,
never a silent re-point)."""
import dataclasses

from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint


def test_fingerprint_differs_when_evaluation_run_id_changes(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    other_provenance = dataclasses.replace(evidence_provenance, evaluation_run_id="run_y")
    fp1 = hypothesis_fingerprint("SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    fp2 = hypothesis_fingerprint("SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, other_provenance, hypothesis_config.config_version)
    assert fp1 != fp2
    assert build_hypothesis_id(fp1)[0] != build_hypothesis_id(fp2)[0]


def test_fingerprint_differs_when_evaluation_config_version_changes(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    other_provenance = dataclasses.replace(evidence_provenance, evaluation_config_version="cfg_eval_v2")
    fp1 = hypothesis_fingerprint("SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    fp2 = hypothesis_fingerprint("SIG_X", "LONG", entry_definition, "NEXT_BAR_OPEN", horizon_candidates, other_provenance, hypothesis_config.config_version)
    assert fp1 != fp2
