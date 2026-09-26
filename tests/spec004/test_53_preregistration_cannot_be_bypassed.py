"""TEST 53 -- PREREGISTRATION cannot be bypassed (PATCH #004-A finding
#1, GPT Review #004 Round 1, the MAIN blocker). Before this patch, a
caller could construct `StrategyHypothesis(status="PREREGISTERED", ...)`
by hand and hand it straight to `HypothesisRegistry.register()`,
completely skipping consensus, human approval, provenance checks, and
`validate_for_preregistration()`. This test proves the fix from both
directions: `register()` refuses the direct insert, and
`preregister_hypothesis()` is the only path that succeeds -- and only
when every one of its checks passes.

PATCH #004-B (GPT Review #004 Round 2): `preregister_hypothesis()` now
also requires a `proposal=` argument and verifies the proposal/consensus/
draft binding (finding #1, see TEST 62) -- `_draft()` and every call
below were updated to supply a real, matching `HypothesisProposal` and
consistent `approved_by`/`approved_at`, so these tests keep exercising
ONLY their own original concern (bypass/approval/validity/status)."""
import dataclasses

from hypothesis.models.entities import (
    Direction, HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode, HypothesisStatus,
    StrategyHypothesis,
)
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import ProposalValidationResult
from hypothesis.registry.hypotheses import HypothesisRegistry, ImmutableHypothesisError, build_hypothesis_id, hypothesis_fingerprint, materialize_variants
from hypothesis.registry.preregistration import PreregistrationError, preregister_hypothesis
from hypothesis.consensus.consensus import compute_consensus

from spec004.conftest import approved_human_decision, make_proposal_raw, rejected_human_decision


def _proposal(proposal_id="prop_1"):
    return normalize_proposal(make_proposal_raw(proposal_id=proposal_id))


def _draft(
    entry_definition, horizon_candidates, evidence_provenance, hypothesis_config,
    status=HypothesisStatus.DRAFT.value, proposal_id="prop_1", approved_by="radu", approved_at="2026-09-25T00:05:00Z",
):
    fp = hypothesis_fingerprint(evidence_provenance.signature_id, Direction.LONG.value, entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, hypothesis_config.config_version)
    prov = HypothesisProvenance("HUMAN:radu", proposal_id, None, approved_by, approved_at)
    return StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=status,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id=evidence_provenance.signature_id,
        signature_set_id=evidence_provenance.signature_set_id, direction=Direction.LONG.value, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry_definition, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizon_candidates,
        variant_ids=(), evidence_provenance=evidence_provenance, hypothesis_provenance=prov, constraints=comp,
        created_at="2026-09-25T00:00:00Z", created_by="radu", strategy_config_version=hypothesis_config.config_version,
    )


def test_register_refuses_a_hand_built_first_time_preregistered_hypothesis(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    fabricated = _draft(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, status=HypothesisStatus.PREREGISTERED.value)
    reg = HypothesisRegistry()
    try:
        reg.register(fabricated)
        assert False, "expected ImmutableHypothesisError -- register() must never introduce a first-time PREREGISTERED record"
    except ImmutableHypothesisError as e:
        assert "preregister_hypothesis" in str(e)
    assert reg.get(fabricated.hypothesis_id) is None


def test_preregister_hypothesis_succeeds_through_the_real_gate(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    draft = _draft(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    variants = materialize_variants(draft, created_at="2026-09-25T00:00:00Z")
    draft = dataclasses.replace(draft, variant_ids=tuple(v.strategy_variant_id for v in variants))
    reg = HypothesisRegistry()
    proposal = _proposal()
    consensus = compute_consensus(proposal.proposal_id, (), human_decision=approved_human_decision())

    frozen = preregister_hypothesis(
        draft, variants, proposal=proposal, proposal_validation=ProposalValidationResult(True, "OK", (), proposal.proposal_id),
        consensus=consensus, registry=reg, run_registry=run_registry, hypothesis_config=hypothesis_config.data,
    )
    assert frozen.status == HypothesisStatus.PREREGISTERED.value
    assert reg.get(frozen.hypothesis_id) == frozen
    for v in variants:
        assert reg.get_variant(v.strategy_variant_id) == v


def test_preregister_hypothesis_rejects_without_human_approve(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    draft = _draft(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    variants = materialize_variants(draft, created_at="t")
    draft = dataclasses.replace(draft, variant_ids=tuple(v.strategy_variant_id for v in variants))
    reg = HypothesisRegistry()
    proposal = _proposal()
    consensus_no_decision = compute_consensus(proposal.proposal_id, (), human_decision=None)
    consensus_reject = compute_consensus(proposal.proposal_id, (), human_decision=rejected_human_decision())

    for consensus in (consensus_no_decision, consensus_reject):
        try:
            preregister_hypothesis(
                draft, variants, proposal=proposal, proposal_validation=ProposalValidationResult(True, "OK", (), proposal.proposal_id),
                consensus=consensus, registry=reg, run_registry=run_registry, hypothesis_config=hypothesis_config.data,
            )
            assert False, "expected PreregistrationError"
        except PreregistrationError:
            pass
    assert reg.get(draft.hypothesis_id) is None


def test_preregister_hypothesis_rejects_an_invalid_proposal(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    draft = _draft(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    variants = materialize_variants(draft, created_at="t")
    draft = dataclasses.replace(draft, variant_ids=tuple(v.strategy_variant_id for v in variants))
    reg = HypothesisRegistry()
    proposal = _proposal()
    consensus = compute_consensus(proposal.proposal_id, (), human_decision=approved_human_decision())
    try:
        preregister_hypothesis(
            draft, variants, proposal=proposal,
            proposal_validation=ProposalValidationResult(False, "HYPOTHESIS_COMPLEXITY_EXCEEDED", ("too many conditions",), proposal.proposal_id),
            consensus=consensus, registry=reg, run_registry=run_registry, hypothesis_config=hypothesis_config.data,
        )
        assert False, "expected PreregistrationError"
    except PreregistrationError as e:
        assert "too many conditions" in str(e)


def test_preregister_hypothesis_rejects_a_draft_already_claiming_preregistered(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    already_claiming = _draft(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, status=HypothesisStatus.PREREGISTERED.value)
    variants = materialize_variants(already_claiming, created_at="t")
    already_claiming = dataclasses.replace(already_claiming, variant_ids=tuple(v.strategy_variant_id for v in variants))
    reg = HypothesisRegistry()
    proposal = _proposal()
    consensus = compute_consensus(proposal.proposal_id, (), human_decision=approved_human_decision())
    try:
        preregister_hypothesis(
            already_claiming, variants, proposal=proposal, proposal_validation=ProposalValidationResult(True, "OK", (), proposal.proposal_id),
            consensus=consensus, registry=reg, run_registry=run_registry, hypothesis_config=hypothesis_config.data,
        )
        assert False, "expected PreregistrationError"
    except PreregistrationError as e:
        assert "only accepts a DRAFT" in str(e)
