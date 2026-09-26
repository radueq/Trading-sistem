"""TEST 63 -- `validate_for_preregistration()` recomputes the
content-addressed fingerprint of a hypothesis (and, per variant, of its
own `exit_hypothesis` against the hypothesis's TRUE `definition_hash`)
and hard-fails if the supplied `hypothesis_id`/`definition_hash`/
`strategy_variant_id`/`variant_definition_hash` don't match (PATCH
#004-B finding #2, GPT Review #004 Round 2). Before this patch, the gate
validated provenance/budget/completeness but never verified that "the id
proves the content" was actually true -- a hand-built object with an
arbitrary, non-matching id/hash could pass every other check and reach
the registry."""
import dataclasses

from hypothesis.registry.hypotheses import HypothesisRegistry
from hypothesis.validation.rules import validate_for_preregistration

from spec004.conftest import build_preregistered_hypothesis_for_test


def test_tampered_hypothesis_id_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    tampered = dataclasses.replace(hyp, hypothesis_id="hyp_0000000000000000")
    ok, errors = validate_for_preregistration(tampered, variants, HypothesisRegistry(), hypothesis_config.data, run_registry)
    assert not ok
    assert any("content-addressed fingerprint" in e for e in errors)


def test_tampered_definition_hash_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    tampered = dataclasses.replace(hyp, definition_hash="0000000000000000")
    ok, errors = validate_for_preregistration(tampered, variants, HypothesisRegistry(), hypothesis_config.data, run_registry)
    assert not ok
    assert any("content-addressed fingerprint" in e for e in errors)


def test_tampered_strategy_variant_id_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    tampered_variant = dataclasses.replace(variants[0], strategy_variant_id="var_0000000000000000")
    tampered_variants = (tampered_variant,) + variants[1:]
    ok, errors = validate_for_preregistration(hyp, tampered_variants, HypothesisRegistry(), hypothesis_config.data, run_registry)
    assert not ok
    assert any("strategy_variant_id/variant_definition_hash" in e for e in errors)


def test_tampered_variant_definition_hash_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    tampered_variant = dataclasses.replace(variants[0], variant_definition_hash="0000000000000000")
    tampered_variants = (tampered_variant,) + variants[1:]
    ok, errors = validate_for_preregistration(hyp, tampered_variants, HypothesisRegistry(), hypothesis_config.data, run_registry)
    assert not ok
    assert any("strategy_variant_id/variant_definition_hash" in e for e in errors)


def test_genuine_untampered_hypothesis_and_variants_pass_the_content_address_check(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    ok, errors = validate_for_preregistration(hyp, variants, registry, hypothesis_config.data, run_registry)
    assert ok, errors
