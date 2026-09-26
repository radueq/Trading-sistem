"""TEST 61 -- research history survives a process restart (PATCH #004-A
finding #6, GPT Review #004 Round 1: "considered 40, rejected 37,
preregistered 3" must not vanish when the Python process holding a bare
in-memory `HypothesisRegistry` exits). `JsonlAuditLog.append()` writes
one line per meaningful event; `replay()` reconstructs an equivalent
registry from scratch, from nothing but the file -- simulating a fresh
process that never held the original in-memory objects."""
import dataclasses

from hypothesis.models.entities import HypothesisStatus
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import validate_proposal
from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint, materialize_variants
from hypothesis.registry.persistence import JsonlAuditLog, PersistentHypothesisRegistry
from hypothesis.consensus.consensus import compute_consensus

from spec004.conftest import approved_human_decision, make_proposal_raw


def test_proposals_and_rejection_survive_a_fresh_replay(tmp_path, discovery_config, hypothesis_config):
    log_path = tmp_path / "audit.jsonl"
    persistent = PersistentHypothesisRegistry.open(log_path)

    kept = normalize_proposal(make_proposal_raw(proposal_id="prop_kept"))
    rejected = normalize_proposal(make_proposal_raw(proposal_id="prop_rejected"))
    persistent.register_proposal(kept)
    persistent.register_proposal(rejected)
    persistent.mark_proposal_rejected("prop_rejected")

    # A brand new process would only ever see the file, never the
    # original in-memory objects -- replay from a FRESH log handle.
    replayed = JsonlAuditLog(log_path).replay()
    assert {p.proposal_id for p in replayed.all_proposals()} == {"prop_kept", "prop_rejected"}
    assert replayed.rejected_proposal_ids() == ("prop_rejected",)
    assert kept in replayed.all_proposals()


def test_preregistered_hypothesis_and_variants_survive_a_fresh_replay(tmp_path, entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    from hypothesis.models.entities import Direction, HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode, StrategyHypothesis
    from hypothesis.proposals.normalize import normalize_proposal
    from hypothesis.proposals.validator import ProposalValidationResult

    log_path = tmp_path / "audit.jsonl"
    persistent = PersistentHypothesisRegistry.open(log_path)

    # PATCH #004-B finding #1: `preregister()` now verifies the draft's
    # own provenance names THIS proposal, and that approved_by/approved_at
    # match the human decision actually supplied -- build a real,
    # matching proposal instead of an unrelated "prop_1" placeholder.
    proposal = normalize_proposal(make_proposal_raw(proposal_id="prop_1"))
    fp = hypothesis_fingerprint(evidence_provenance.signature_id, Direction.LONG.value, entry_definition, "NEXT_BAR_OPEN", horizon_candidates, evidence_provenance, hypothesis_config.config_version)
    hid, dh = build_hypothesis_id(fp)
    draft = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.DRAFT.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id=evidence_provenance.signature_id,
        signature_set_id=evidence_provenance.signature_set_id, direction=Direction.LONG.value, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry_definition, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizon_candidates,
        variant_ids=(), evidence_provenance=evidence_provenance,
        hypothesis_provenance=HypothesisProvenance("HUMAN:radu", proposal.proposal_id, None, "radu", "t"),
        constraints=HypothesisComplexitySnapshot(3, 1, hypothesis_config.config_version),
        created_at="t", created_by="radu", strategy_config_version=hypothesis_config.config_version,
    )
    variants = materialize_variants(draft, created_at="t")
    draft = dataclasses.replace(draft, variant_ids=tuple(v.strategy_variant_id for v in variants))

    frozen = persistent.preregister(
        draft, variants, proposal=proposal, proposal_validation=ProposalValidationResult(True, "OK", (), proposal.proposal_id),
        consensus=compute_consensus(proposal.proposal_id, (), human_decision=approved_human_decision(at="t")),
        run_registry=run_registry, hypothesis_config=hypothesis_config.data,
    )

    replayed = JsonlAuditLog(log_path).replay()
    assert replayed.get(frozen.hypothesis_id) == frozen
    for v in variants:
        assert replayed.get_variant(v.strategy_variant_id) == v
    # a THIRD, completely independent registry opened from the same file
    # (simulating a real restart) must land in the identical state:
    reopened = PersistentHypothesisRegistry.open(log_path)
    assert reopened.registry.get(frozen.hypothesis_id) == frozen


def test_append_only_never_rewrites_prior_lines(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(log_path)
    log.append("proposal_rejected", {"proposal_id": "a"})
    first_line = log_path.read_text()
    log.append("proposal_rejected", {"proposal_id": "b"})
    second_read = log_path.read_text()
    assert second_read.startswith(first_line)
    assert second_read.count("\n") == 2
