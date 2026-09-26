"""TEST 56 -- `validate_for_preregistration()` now actually calls the
provenance guard AND checks internal `parent_signature_id`/
`signature_set_id` <-> `evidence_provenance` consistency (PATCH #004-A
finding #2, GPT Review #004 Round 1). Before this patch, `check_
provenance_matches_run()` existed but nothing wired it into the gate --
a caller could skip it entirely -- and nothing checked that a
hypothesis's own top-level `parent_signature_id`/`signature_set_id`
(used for budget accounting) actually agreed with the Evidence it claims
to rest on."""
import dataclasses

from hypothesis.registry.hypotheses import HypothesisRegistry
from hypothesis.validation.rules import validate_for_preregistration

from spec004.conftest import build_preregistered_hypothesis_for_test


def test_provenance_mismatch_against_the_actual_run_is_caught_by_the_gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    mismatched_run = dataclasses.replace(run_registry, discovery_config_version="cfg_disc_DIFFERENT")
    ok, errors = validate_for_preregistration(hyp, variants, registry, hypothesis_config.data, mismatched_run)
    assert not ok
    assert any("discovery_config_version" in e for e in errors)


def test_parent_signature_id_disagreeing_with_evidence_provenance_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    tampered = dataclasses.replace(hyp, parent_signature_id="SOME_OTHER_SIGNATURE")
    ok, errors = validate_for_preregistration(tampered, variants, HypothesisRegistry(), hypothesis_config.data, run_registry)
    assert not ok
    assert any("parent_signature_id" in e for e in errors)


def test_signature_set_id_disagreeing_with_evidence_provenance_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    tampered = dataclasses.replace(hyp, signature_set_id="sigset_DIFFERENT")
    ok, errors = validate_for_preregistration(tampered, variants, HypothesisRegistry(), hypothesis_config.data, run_registry)
    assert not ok
    assert any("signature_set_id" in e for e in errors)


def test_fully_consistent_hypothesis_passes_the_gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    ok, errors = validate_for_preregistration(hyp, variants, registry, hypothesis_config.data, run_registry)
    assert ok, errors
