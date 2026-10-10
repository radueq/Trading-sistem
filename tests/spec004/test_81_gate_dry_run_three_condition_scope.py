"""TEST 81 -- Stage 6, Finding 16/GPT-G3, decision registry E1: the
batch-internal SIMULATED-SEQUENTIAL dry run, at EXACTLY its stated
3-condition/synchronous-only scope.

Before Stage 6, `preregister_hypothesis()` wrote the hypothesis and then
each variant; a conflict on a LATER variant raised only after the
hypothesis and the earlier variants were already in the registry -- a
partial write, and a pre-existing DRAFT under the same id was left
overwritten as PREREGISTERED (both reproduced by execution on `b7d6b02`).

Covered here, through the real gate unless stated:
- each of E1's three named conditions (content mismatch; PREREGISTERED-
  content mismatch; variant content mismatch) refuses the call with NO
  real write -- the registry is in the exact pre-call state;
- a conflict on the LAST variant, i.e. found only after the hypothesis
  and earlier variants were inserted into the dry run's own VIRTUAL
  state (never a real write -- no rollback exists or is needed);
- a pre-existing DRAFT under the same hypothesis id stays exactly as it
  was;
- a conflict BETWEEN two items of the SAME batch, against the dry run
  directly (at the gate, Finding 14/15 now refuse such a batch even
  earlier, so the dry run's own batch-internal path is exercised on the
  registry method itself) -- and proof that checking each item only
  against the PRE-batch state would have missed it;
- the dry run and the real writes share ONE predicate per write;
- the exact scope statement, quoted from decision registry E1, appears
  in the shipped docstrings, never paraphrased.
"""
import dataclasses

import pytest

from hypothesis.models.entities import HypothesisStatus, VariantTag
from hypothesis.registry.hypotheses import HypothesisRegistry, ImmutableHypothesisError
from hypothesis.registry.preregistration import PreregistrationError, preregister_hypothesis

from spec004.gate_inputs import draft_from_proposal, gate, make_proposal, registry_state, with_variants

E1_GUARANTEE = (
    "The batch-internal simulated-sequential dry run guarantees no partial write under exactly THREE "
    "named conditions (content mismatch; PREREGISTERED-content mismatch; variant content mismatch), "
    "ONLY under synchronous execution with no write from another caller interleaved between the dry "
    "run and the real writes."
)
E1_PRESENT_LIMITATION = (
    "An exception or failure OUTSIDE the three named conditions (e.g. an unexpected error from a bug "
    "elsewhere in the call path) is NOT guaranteed to leave the registry in an all-or-nothing state "
    "RIGHT NOW, under the CURRENT plain in-memory dict -- this is a gap in today's implementation, not "
    "a risk that first appears after some future storage-layer migration."
)


def _inputs(hypothesis_config, created_at="2026-09-25T00:00:00Z"):
    proposal = make_proposal()
    draft, variants = with_variants(draft_from_proposal(proposal, hypothesis_config, created_at=created_at), proposal)
    return proposal, draft, variants


def _gate(proposal, draft, variants, reg, hypothesis_config, config_registry, run_registry):
    return gate(
        draft, variants, proposal, hypothesis_config=hypothesis_config, config_registry=config_registry,
        run_registry=run_registry, registry=reg,
    )


def test_variant_content_mismatch_on_the_last_variant_writes_nothing(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal, draft, variants = _inputs(hypothesis_config)
    reg = HypothesisRegistry()
    last = variants[-1]
    reg.register_variant(dataclasses.replace(last, variant_tag=VariantTag.BASELINE_VARIANT.value))  # pre-existing, different
    before = registry_state(reg)

    with pytest.raises(PreregistrationError, match=r"NO write performed.*already registered with DIFFERENT content"):
        _gate(proposal, draft, variants, reg, hypothesis_config, hypothesis_config_registry, run_registry)
    assert registry_state(reg) == before  # not the hypothesis, not one earlier variant
    assert reg.get(draft.hypothesis_id) is None


def test_a_pre_existing_draft_under_the_same_id_is_left_exactly_as_it_was(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal, draft, variants = _inputs(hypothesis_config)
    reg = HypothesisRegistry()
    reg.register(draft)  # a prior DRAFT with the same content-addressed id
    reg.register_variant(dataclasses.replace(variants[1], created_at="OTHER"))
    before = registry_state(reg)

    with pytest.raises(PreregistrationError, match="NO write performed"):
        _gate(proposal, draft, variants, reg, hypothesis_config, hypothesis_config_registry, run_registry)
    assert registry_state(reg) == before
    assert reg.get(draft.hypothesis_id).status == HypothesisStatus.DRAFT.value


def test_preregistered_content_mismatch_writes_nothing(hypothesis_config, hypothesis_config_registry, run_registry):
    proposal, draft, variants = _inputs(hypothesis_config)
    reg = HypothesisRegistry()
    _gate(proposal, draft, variants, reg, hypothesis_config, hypothesis_config_registry, run_registry)
    before = registry_state(reg)

    # Same economic content (same id), different administrative content.
    proposal2, draft2, variants2 = _inputs(hypothesis_config, created_at="2026-09-26T00:00:00Z")
    assert draft2.hypothesis_id == draft.hypothesis_id
    with pytest.raises(PreregistrationError, match=r"NO write performed.*is PREREGISTERED and immutable"):
        _gate(proposal2, draft2, variants2, reg, hypothesis_config, hypothesis_config_registry, run_registry)
    assert registry_state(reg) == before


def test_hypothesis_content_mismatch_writes_nothing(hypothesis_config, hypothesis_config_registry, run_registry):
    proposal, draft, variants = _inputs(hypothesis_config)
    reg = HypothesisRegistry()
    reg.register(dataclasses.replace(draft, definition_hash="forged_hash_0000"))  # same id, different hash
    before = registry_state(reg)
    with pytest.raises(PreregistrationError, match=r"NO write performed.*DIFFERENT definition_hash"):
        _gate(proposal, draft, variants, reg, hypothesis_config, hypothesis_config_registry, run_registry)
    assert registry_state(reg) == before


def test_a_conflict_between_two_items_of_the_same_batch_is_found_in_the_virtual_state(hypothesis_config):
    proposal, draft, variants = _inputs(hypothesis_config)
    frozen = dataclasses.replace(draft, status=HypothesisStatus.PREREGISTERED.value)
    clash = dataclasses.replace(variants[0], variant_tag=VariantTag.BASELINE_VARIANT.value)  # same id as variants[0]
    batch = variants + (clash,)
    reg = HypothesisRegistry()
    before = registry_state(reg)

    # Checked only against the PRE-batch (empty) state, every item looks fine:
    assert all(HypothesisRegistry._register_variant_conflict(v, dict(reg._variants)) is None for v in batch)
    # The simulated-sequential dry run sees variants[0] in its VIRTUAL state:
    conflicts = reg.dry_run_preregistration(frozen, batch)
    assert len(conflicts) == 1 and variants[0].strategy_variant_id in conflicts[0]
    assert registry_state(reg) == before  # the dry run itself never writes

    # ...and this is exactly the case the unguarded write sequence would
    # have left half-written:
    unguarded = HypothesisRegistry()
    with pytest.raises(ImmutableHypothesisError):
        unguarded._force_register(frozen)
        for v in batch:
            unguarded.register_variant(v)
    assert unguarded.get(frozen.hypothesis_id) is not None and len(unguarded.all_variants()) == len(variants)


def test_the_dry_run_and_the_real_writes_share_one_predicate_each(hypothesis_config):
    _proposal, draft, variants = _inputs(hypothesis_config)
    reg = HypothesisRegistry()
    conflicting_variant = dataclasses.replace(variants[0], created_at="OTHER")
    reg.register_variant(conflicting_variant)
    predicate_message = HypothesisRegistry._register_variant_conflict(variants[0], reg._variants)
    with pytest.raises(ImmutableHypothesisError) as exc_info:
        reg.register_variant(variants[0])
    assert str(exc_info.value) == predicate_message

    forged = dataclasses.replace(draft, definition_hash="forged_hash_0000")
    reg.register(forged)
    predicate_message = HypothesisRegistry._force_register_conflict(draft, reg._hypotheses)
    with pytest.raises(ImmutableHypothesisError) as exc_info:
        reg._force_register(draft)
    assert str(exc_info.value) == predicate_message


def _normalized(text: str) -> str:
    return " ".join(text.split())


@pytest.mark.parametrize("doc_owner", ["preregister_hypothesis", "HypothesisRegistry.dry_run_preregistration"])
def test_the_exact_e1_scope_statement_is_in_the_shipped_docstring(doc_owner):
    doc = preregister_hypothesis.__doc__ if doc_owner == "preregister_hypothesis" else HypothesisRegistry.dry_run_preregistration.__doc__
    assert _normalized(E1_GUARANTEE) in _normalized(doc)
    assert _normalized(E1_PRESENT_LIMITATION) in _normalized(doc)
