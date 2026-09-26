"""TEST 62 -- `preregister_hypothesis()` verifies that `proposal`,
`proposal_validation`, `consensus`, and `draft.hypothesis_provenance` all
name the SAME proposal, and that the recorded `approved_by`/`approved_at`
match the human decision actually supplied (PATCH #004-B finding #1, GPT
Review #004 Round 2). Before this patch, nothing tied these together: a
caller could hand in `human_decision=APPROVE` for proposal A while
preregistering an unrelated draft B, and the gate would happily proceed
-- "human approval exists" never proved "human approval exists FOR THIS
HYPOTHESIS"."""
import dataclasses

import pytest

from hypothesis.models.entities import (
    Direction, HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode, HypothesisStatus,
    StrategyHypothesis,
)
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import ProposalValidationResult
from hypothesis.registry.hypotheses import HypothesisRegistry, build_hypothesis_id, hypothesis_fingerprint, materialize_variants
from hypothesis.registry.preregistration import PreregistrationError, preregister_hypothesis
from hypothesis.consensus.consensus import compute_consensus

from spec004.conftest import approved_human_decision, make_proposal_raw


def _proposal(proposal_id="prop_1"):
    return normalize_proposal(make_proposal_raw(proposal_id=proposal_id))


def _draft(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config,
    proposal_id="prop_1", approved_by="radu", approved_at="2026-09-25T00:05:00Z",
):
    fp = hypothesis_fingerprint(evidence_provenance.signature_id, Direction.LONG.value, entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, hypothesis_config.config_version)
    prov = HypothesisProvenance("HUMAN:radu", proposal_id, None, approved_by, approved_at)
    draft = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.DRAFT.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id=evidence_provenance.signature_id,
        signature_set_id=evidence_provenance.signature_set_id, direction=Direction.LONG.value, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry_definition, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizon_candidates,
        variant_ids=(), evidence_provenance=evidence_provenance, hypothesis_provenance=prov, constraints=comp,
        created_at="t", created_by="radu", strategy_config_version=hypothesis_config.config_version,
    )
    variants = materialize_variants(draft, created_at="t")
    draft = dataclasses.replace(draft, variant_ids=tuple(v.strategy_variant_id for v in variants))
    return draft, variants


def test_consistent_binding_succeeds(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    proposal = _proposal("prop_1")
    draft, variants = _draft(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, proposal_id="prop_1")
    consensus = compute_consensus("prop_1", (), human_decision=approved_human_decision())
    frozen = preregister_hypothesis(
        draft, variants, proposal=proposal, proposal_validation=ProposalValidationResult(True, "OK", (), "prop_1"),
        consensus=consensus, registry=HypothesisRegistry(), run_registry=run_registry, hypothesis_config=hypothesis_config.data,
    )
    assert frozen.status == HypothesisStatus.PREREGISTERED.value


def test_proposal_validation_for_a_different_proposal_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    proposal = _proposal("prop_1")
    draft, variants = _draft(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, proposal_id="prop_1")
    consensus = compute_consensus("prop_1", (), human_decision=approved_human_decision())
    with pytest.raises(PreregistrationError, match="proposal_validation.proposal_id"):
        preregister_hypothesis(
            draft, variants, proposal=proposal,
            proposal_validation=ProposalValidationResult(True, "OK", (), "prop_DIFFERENT"),
            consensus=consensus, registry=HypothesisRegistry(), run_registry=run_registry, hypothesis_config=hypothesis_config.data,
        )


def test_consensus_for_a_different_proposal_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    proposal = _proposal("prop_1")
    draft, variants = _draft(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, proposal_id="prop_1")
    consensus_for_other_proposal = compute_consensus("prop_DIFFERENT", (), human_decision=approved_human_decision())
    with pytest.raises(PreregistrationError, match="consensus.proposal_id"):
        preregister_hypothesis(
            draft, variants, proposal=proposal, proposal_validation=ProposalValidationResult(True, "OK", (), "prop_1"),
            consensus=consensus_for_other_proposal, registry=HypothesisRegistry(), run_registry=run_registry, hypothesis_config=hypothesis_config.data,
        )


def test_draft_naming_a_different_proposal_than_the_one_supplied_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    proposal = _proposal("prop_1")
    # draft's own provenance claims "prop_OTHER", even though the ACTUAL
    # proposal/consensus supplied below are both "prop_1" -- this is
    # exactly the attack the review described: approval for A, applied to B.
    draft, variants = _draft(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, proposal_id="prop_OTHER")
    consensus = compute_consensus("prop_1", (), human_decision=approved_human_decision())
    with pytest.raises(PreregistrationError, match="hypothesis_provenance.proposal_id"):
        preregister_hypothesis(
            draft, variants, proposal=proposal, proposal_validation=ProposalValidationResult(True, "OK", (), "prop_1"),
            consensus=consensus, registry=HypothesisRegistry(), run_registry=run_registry, hypothesis_config=hypothesis_config.data,
        )


def test_approved_by_disagreeing_with_the_human_decision_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    proposal = _proposal("prop_1")
    draft, variants = _draft(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, proposal_id="prop_1", approved_by="someone_else")
    consensus = compute_consensus("prop_1", (), human_decision=approved_human_decision(by="radu"))
    with pytest.raises(PreregistrationError, match="approved_by"):
        preregister_hypothesis(
            draft, variants, proposal=proposal, proposal_validation=ProposalValidationResult(True, "OK", (), "prop_1"),
            consensus=consensus, registry=HypothesisRegistry(), run_registry=run_registry, hypothesis_config=hypothesis_config.data,
        )


def test_approved_at_disagreeing_with_the_human_decision_is_rejected(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    proposal = _proposal("prop_1")
    draft, variants = _draft(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config,
        proposal_id="prop_1", approved_at="2020-01-01T00:00:00Z",
    )
    consensus = compute_consensus("prop_1", (), human_decision=approved_human_decision(at="2026-09-25T00:05:00Z"))
    with pytest.raises(PreregistrationError, match="approved_at"):
        preregister_hypothesis(
            draft, variants, proposal=proposal, proposal_validation=ProposalValidationResult(True, "OK", (), "prop_1"),
            consensus=consensus, registry=HypothesisRegistry(), run_registry=run_registry, hypothesis_config=hypothesis_config.data,
        )
