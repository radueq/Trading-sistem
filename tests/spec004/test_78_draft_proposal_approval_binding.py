"""TEST 78 -- Stage 6, Finding 14 (GPT-G1), joint remediation design
003+004 section 10 parts 1-2. Before Stage 6, the only link from `draft`
back to `proposal` was the `proposal_id` STRING -- nothing compared
content, and nothing tied the human approval to the content approved.

Three regressions, as required by the design's own regression list:
(1) `verify_draft_matches_proposal()` rejects a draft whose content
    differs from its originating proposal, field by field (and variants
    that are not the proposal's own replay);
(2) a human-decision content-fingerprint mismatch is rejected;
(3) content changed under the SAME approved id when `proposal` and
    `draft` are mutated TOGETHER after approval is rejected -- the case
    a draft-vs-proposal comparison alone can never see.
"""
import dataclasses

import pytest

from hypothesis.consensus.consensus import record_human_decision
from hypothesis.models.entities import (
    EntryDefinition, ExitFamily, ExitHypothesis, HorizonCandidateSet, HumanDecision, HumanDecisionValue,
    InvalidationCondition, LaneStateCondition,
)
from hypothesis.registry.hypotheses import HypothesisRegistry, proposal_content_fingerprint
from hypothesis.registry.preregistration import PreregistrationError, verify_draft_matches_proposal

from spec004.gate_inputs import (
    APPROVED_AT, APPROVED_BY, draft_from_proposal, gate, make_proposal, registry_state, set_variant_ids, with_variants,
)

_OTHER_ENTRY = EntryDefinition(core_conditions=(LaneStateCondition("volatility", "COMPRESSION"),))
_OTHER_HCS = HorizonCandidateSet("BARS", (2, 3), "decay concentrated in the 2-5 bar zone", "PRE_SPECIFIED")


@pytest.mark.parametrize("draft_override, field_name", [
    ({"direction": "SHORT"}, "direction"),
    ({"entry_definition": _OTHER_ENTRY}, "entry_definition"),
    ({"entry_execution_policy": "SAME_BAR_CLOSE"}, "entry_execution_policy"),
    ({"horizon_candidate_set": _OTHER_HCS}, "horizon_candidate_set"),
])
def test_a_draft_whose_content_differs_from_its_proposal_is_rejected_field_by_field(
    draft_override, field_name, hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal()
    draft, variants = with_variants(draft_from_proposal(proposal, hypothesis_config, **draft_override), proposal)

    ok, errors = verify_draft_matches_proposal(draft, proposal, variants)
    assert not ok
    assert any(e.startswith(f"draft.{field_name}=") for e in errors), errors

    reg = HypothesisRegistry()
    with pytest.raises(PreregistrationError, match=rf"draft\.{field_name}=.*does not equal proposal\."):
        gate(
            draft, variants, proposal, hypothesis_config=hypothesis_config,
            config_registry=hypothesis_config_registry, run_registry=run_registry, registry=reg,
        )
    assert reg.all_hypotheses() == () and reg.all_variants() == ()


def test_a_draft_whose_evidence_provenance_differs_from_the_proposal_source_evidence_is_rejected(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal()
    other_evidence = dataclasses.replace(proposal.source_evidence, evaluation_config_version="cfg_eval_OTHER")
    draft, variants = with_variants(draft_from_proposal(proposal, hypothesis_config, evidence_provenance=other_evidence), proposal)
    ok, errors = verify_draft_matches_proposal(draft, proposal, variants)
    assert not ok and any(e.startswith("draft.evidence_provenance=") for e in errors)


def test_variants_missing_a_proposal_exit_are_rejected(hypothesis_config, hypothesis_config_registry, run_registry):
    proposal = make_proposal()  # one SIGNAL_INVALIDATION exit
    draft, variants = with_variants(draft_from_proposal(proposal, hypothesis_config), proposal, exits=())
    with pytest.raises(PreregistrationError, match="variant\\(s\\) the proposal requires .* are not among the supplied"):
        gate(
            draft, variants, proposal, hypothesis_config=hypothesis_config,
            config_registry=hypothesis_config_registry, run_registry=run_registry,
        )


def test_variants_carrying_an_exit_the_proposal_never_asked_for_are_rejected(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal()
    smuggled = ExitHypothesis(
        exit_family=ExitFamily.SIGNAL_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source="EVIDENCE_DERIVED", max_holding_bars=3,
        invalidation_conditions=(InvalidationCondition(lane="relative_strength", holds_labels=("VERY_HIGH",)),),
    )
    draft, variants = with_variants(
        draft_from_proposal(proposal, hypothesis_config), proposal, exits=proposal.exit_hypotheses + (smuggled,),
    )
    with pytest.raises(PreregistrationError, match="are not part of the proposal's own replay"):
        gate(
            draft, variants, proposal, hypothesis_config=hypothesis_config,
            config_registry=hypothesis_config_registry, run_registry=run_registry,
        )


def test_an_approval_with_no_content_fingerprint_is_rejected(hypothesis_config, hypothesis_config_registry, run_registry):
    proposal = make_proposal()
    draft, variants = with_variants(draft_from_proposal(proposal, hypothesis_config), proposal)
    unbound = HumanDecision(decision=HumanDecisionValue.APPROVE.value, decided_by=APPROVED_BY, decided_at=APPROVED_AT)
    with pytest.raises(PreregistrationError, match="carries no content_fingerprint"):
        gate(
            draft, variants, proposal, human_decision=unbound, hypothesis_config=hypothesis_config,
            config_registry=hypothesis_config_registry, run_registry=run_registry,
        )


def test_a_human_decision_fingerprint_for_different_content_is_rejected(
    hypothesis_config, hypothesis_config_registry, run_registry,
):
    proposal = make_proposal()
    draft, variants = with_variants(draft_from_proposal(proposal, hypothesis_config), proposal)
    approved_other = record_human_decision(
        dataclasses.replace(proposal, direction="SHORT"), HumanDecisionValue.APPROVE.value, APPROVED_BY, APPROVED_AT,
    )
    with pytest.raises(PreregistrationError, match="does not match the fingerprint of the LIVE proposal content"):
        gate(
            draft, variants, proposal, human_decision=approved_other, hypothesis_config=hypothesis_config,
            config_registry=hypothesis_config_registry, run_registry=run_registry,
        )


def _lockstep_mutations():
    base = make_proposal()
    si = base.exit_hypotheses[0]
    return [
        ("direction", dict(direction="SHORT")),
        ("entry_definition", dict(entry_definition=_OTHER_ENTRY)),
        ("horizon_candidates", dict(horizon_candidates=_OTHER_HCS)),
        # signature_id: the run record does not pin it (the real-run
        # provenance check cannot see this change) -- only the approval
        # fingerprint can.
        ("source_evidence", dict(source_evidence=dataclasses.replace(base.source_evidence, signature_id="OTHER_SIGNATURE"))),
        ("exit max_holding_bars", dict(exit_hypotheses=(dataclasses.replace(si, max_holding_bars=10),))),
    ]


@pytest.mark.parametrize("label, mutation", _lockstep_mutations(), ids=[m[0] for m in _lockstep_mutations()])
def test_proposal_and_draft_mutated_together_after_approval_are_rejected(
    label, mutation, hypothesis_config, hypothesis_config_registry, run_registry,
):
    approved = make_proposal()
    mutated = dataclasses.replace(approved, **mutation)  # same proposal_id, different content
    draft, variants = with_variants(draft_from_proposal(mutated, hypothesis_config), mutated)

    # draft and proposal agree with EACH OTHER -- the old string-identity
    # world and part 1 alone would let this through:
    assert verify_draft_matches_proposal(draft, mutated, variants) == (True, ())
    assert mutated.proposal_id == approved.proposal_id

    reg = HypothesisRegistry()
    before = registry_state(reg)
    with pytest.raises(PreregistrationError, match="the proposal changed after the human approved it"):
        gate(
            draft, variants, mutated, approval_proposal=approved, hypothesis_config=hypothesis_config,
            config_registry=hypothesis_config_registry, run_registry=run_registry, registry=reg,
        )
    assert registry_state(reg) == before


def test_the_content_fingerprint_ignores_narrative_and_listing_order_but_not_content():
    p = make_proposal()
    assert proposal_content_fingerprint(dataclasses.replace(p, interpretation="different words")) == proposal_content_fingerprint(p)
    assert proposal_content_fingerprint(dataclasses.replace(p, direction_basis="HUMAN_DECISION")) == proposal_content_fingerprint(p)
    assert proposal_content_fingerprint(dataclasses.replace(p, direction="SHORT")) != proposal_content_fingerprint(p)
    si = p.exit_hypotheses[0]
    si2 = dataclasses.replace(si, max_holding_bars=3)
    assert (proposal_content_fingerprint(dataclasses.replace(p, exit_hypotheses=(si, si2)))
            == proposal_content_fingerprint(dataclasses.replace(p, exit_hypotheses=(si2, si))))


def test_a_fully_consistent_chain_preregisters(hypothesis_config, hypothesis_config_registry, run_registry):
    proposal = make_proposal()
    draft, variants = with_variants(draft_from_proposal(proposal, hypothesis_config), proposal)
    reg = HypothesisRegistry()
    frozen = gate(
        draft, variants, proposal, hypothesis_config=hypothesis_config,
        config_registry=hypothesis_config_registry, run_registry=run_registry, registry=reg,
    )
    assert frozen.status == "PREREGISTERED"
    assert {v.strategy_variant_id for v in reg.variants_for(frozen.hypothesis_id)} == set(set_variant_ids(draft, variants).variant_ids)
