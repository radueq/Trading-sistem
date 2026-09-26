"""TEST 64 -- a registered `StrategyVariant` is immutable in FULL,
including `variant_tag` (PATCH #004-B finding #3, GPT Review #004
Round 2). `variant_tag` is deliberately excluded from
`variant_definition_hash` (it is methodological metadata, not trading
meaning), but the original `register_variant()` compared ONLY that
hash -- so a caller could re-register the SAME `strategy_variant_id`
with the SAME hash but a DIFFERENT `variant_tag` (e.g. rewriting
EXPERIMENTAL_VARIANT to BASELINE_VARIANT after seeing backtest results)
and the old check silently accepted the overwrite."""
import dataclasses

import pytest

from hypothesis.models.entities import VariantTag
from hypothesis.registry.hypotheses import ImmutableHypothesisError

from spec004.conftest import build_preregistered_hypothesis_for_test


def test_rewriting_variant_tag_after_registration_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    original = variants[0]
    assert original.variant_tag == VariantTag.EXPERIMENTAL_VARIANT.value
    rewritten = dataclasses.replace(original, variant_tag=VariantTag.BASELINE_VARIANT.value)
    # SAME strategy_variant_id, SAME variant_definition_hash -- only
    # variant_tag differs. Before PATCH #004-B this silently overwrote
    # the stored record.
    assert rewritten.strategy_variant_id == original.strategy_variant_id
    assert rewritten.variant_definition_hash == original.variant_definition_hash
    with pytest.raises(ImmutableHypothesisError, match="immutable in full"):
        registry.register_variant(rewritten)
    # the ORIGINAL record must still be the one stored, untouched:
    assert registry.get_variant(original.strategy_variant_id) == original


def test_reregistering_an_identical_variant_is_an_idempotent_noop(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    original = variants[0]
    identical_copy = dataclasses.replace(original)  # a distinct object, equal in every field
    registry.register_variant(identical_copy)  # must not raise
    assert registry.get_variant(original.strategy_variant_id) == original


def test_reregistering_with_a_different_hash_is_still_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    original = variants[0]
    different_content = dataclasses.replace(original, variant_definition_hash="0000000000000000")
    with pytest.raises(ImmutableHypothesisError, match="immutable in full"):
        registry.register_variant(different_content)
