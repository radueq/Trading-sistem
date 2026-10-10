"""TEST 79 -- Stage 6, Finding 14 baseline designation (joint remediation
design 003+004 section 10, "Linkage, corrected"). `designated_baseline_
bars` is methodology, deliberately EXCLUDED from every economic
fingerprint -- so it gets its OWN approval-time record,
`HumanDecision.approved_designated_baseline_bars`, and the gate reads the
baseline for its `materialize_variants()` replay from `proposal.horizon_
candidates.designated_baseline_bars` exclusively, never from a free
call-site argument.

The two regressions the design names:
(1) a call whose `materialize_variants()` invocation tags a DIFFERENT
    horizon BASELINE_VARIANT than the proposal declares is rejected;
(2) `proposal`/`draft` mutated TOGETHER after approval, changing ONLY
    `designated_baseline_bars` (every economically-hashed field
    unchanged) is rejected -- by the separate check, since the economic
    fingerprint provably cannot see it.
"""
import dataclasses

import pytest

from hypothesis.models.entities import VariantTag
from hypothesis.registry.hypotheses import HypothesisRegistry, proposal_content_fingerprint
from hypothesis.registry.preregistration import PreregistrationError

from spec004.gate_inputs import draft_from_proposal, gate, make_proposal, registry_state, with_variants


def _call(proposal, hypothesis_config, config_registry, run_registry, *, baseline_kwargs=None, approval_proposal=None, registry=None):
    draft, variants = with_variants(draft_from_proposal(proposal, hypothesis_config), proposal, **(baseline_kwargs or {}))
    return gate(
        draft, variants, proposal, approval_proposal=approval_proposal, hypothesis_config=hypothesis_config,
        config_registry=config_registry, run_registry=run_registry, registry=registry,
    ), variants


def test_variants_tagging_a_different_baseline_than_the_proposal_declares_are_rejected(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal(horizon_overrides={"designated_baseline_bars": 3})
    reg = HypothesisRegistry()
    with pytest.raises(PreregistrationError, match="designated_baseline_bars=3"):
        _call(proposal, hypothesis_config, hypothesis_config_registry, run_registry, baseline_kwargs={"baseline": 5}, registry=reg)
    assert reg.all_hypotheses() == () and reg.all_variants() == ()


def test_a_baseline_tag_on_a_proposal_that_designates_none_is_rejected(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal()  # designated_baseline_bars is None
    with pytest.raises(PreregistrationError, match="designated_baseline_bars=None"):
        _call(proposal, hypothesis_config, hypothesis_config_registry, run_registry, baseline_kwargs={"baseline": 2})


def test_no_baseline_tag_when_the_proposal_designates_one_is_rejected(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal(horizon_overrides={"designated_baseline_bars": 3})
    with pytest.raises(PreregistrationError, match="designated_baseline_bars=3"):
        _call(proposal, hypothesis_config, hypothesis_config_registry, run_registry, baseline_kwargs={"baseline": None})


def test_the_designated_baseline_is_the_one_tagged_when_everything_agrees(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal(horizon_overrides={"designated_baseline_bars": 3})
    reg = HypothesisRegistry()
    frozen, _variants = _call(proposal, hypothesis_config, hypothesis_config_registry, run_registry, registry=reg)
    tags = {v.exit_hypothesis.time_exit_bars: v.variant_tag for v in reg.variants_for(frozen.hypothesis_id)}
    assert tags == {
        2: VariantTag.EXPERIMENTAL_VARIANT.value, 3: VariantTag.BASELINE_VARIANT.value,
        5: VariantTag.EXPERIMENTAL_VARIANT.value, None: VariantTag.EXPERIMENTAL_VARIANT.value,
    }


def test_baseline_changed_in_lockstep_after_approval_is_rejected_by_its_own_check(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    approved = make_proposal(horizon_overrides={"designated_baseline_bars": 3})
    mutated = dataclasses.replace(
        approved, horizon_candidates=dataclasses.replace(approved.horizon_candidates, designated_baseline_bars=5),
    )
    # The gap this check exists for: the economic fingerprint is blind to it.
    assert proposal_content_fingerprint(mutated) == proposal_content_fingerprint(approved)

    reg = HypothesisRegistry()
    before = registry_state(reg)
    with pytest.raises(PreregistrationError) as exc_info:
        _call(mutated, hypothesis_config, hypothesis_config_registry, run_registry, approval_proposal=approved, registry=reg)
    message = str(exc_info.value)
    assert "approved_designated_baseline_bars=3 does not match the LIVE" in message
    assert "does not match the fingerprint of the LIVE proposal content" not in message
    assert registry_state(reg) == before


def test_a_designated_baseline_outside_the_candidate_values_is_rejected(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal(horizon_overrides={"designated_baseline_bars": 7})
    draft = draft_from_proposal(proposal, hypothesis_config)
    from hypothesis.registry.hypotheses import materialize_variants
    variants = materialize_variants(draft, signal_invalidation_exits=proposal.exit_hypotheses, created_at="t")
    draft = dataclasses.replace(draft, variant_ids=tuple(v.strategy_variant_id for v in variants))
    with pytest.raises(PreregistrationError) as exc_info:
        gate(
            draft, variants, proposal, hypothesis_config=hypothesis_config,
            config_registry=hypothesis_config_registry, run_registry=run_registry,
        )
    message = str(exc_info.value)
    assert "materialize_variants() replay from the proposal failed" in message
    assert "designated_baseline_bars=7 is not one of horizon_candidates.values" in message  # live D1 too
