"""TEST 65 -- a preregistration commit is persisted as ONE JSONL record
(`preregistration_committed`, carrying the hypothesis AND every variant
together), not one `hypothesis_preregistered` line followed by N
separate `variant_registered` lines (PATCH #004-B finding #4, GPT Review
#004 Round 2). The original multi-append version could diverge from the
in-memory state if the process/disk died between appends -- a hypothesis
durable with only SOME of its variants, or none at all. A single record
makes replay all-or-nothing: the hypothesis and ALL its variants appear
together, or the line simply isn't there yet."""
import json

from hypothesis.registry.persistence import JsonlAuditLog, PersistentHypothesisRegistry

from spec004.conftest import approved_human_decision, make_proposal_raw


def _commit(tmp_path, entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    import dataclasses

    from hypothesis.models.entities import (
        Direction, HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode, HypothesisStatus,
        StrategyHypothesis,
    )
    from hypothesis.proposals.normalize import normalize_proposal
    from hypothesis.proposals.validator import ProposalValidationResult
    from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint, materialize_variants
    from hypothesis.consensus.consensus import compute_consensus

    log_path = tmp_path / "audit.jsonl"
    persistent = PersistentHypothesisRegistry.open(log_path)
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
    return log_path, frozen, variants


def test_exactly_one_new_line_is_appended_for_the_whole_commit(tmp_path, entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    log_path, frozen, variants = _commit(tmp_path, entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry)
    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 1, "the hypothesis and every variant must be written in ONE append(), not len(variants)+1"
    record = json.loads(lines[0])
    assert record["record_type"] == "preregistration_committed"
    assert record["payload"]["hypothesis"]["hypothesis_id"] == frozen.hypothesis_id
    assert len(record["payload"]["variants"]) == len(variants)


def test_replay_reconstructs_the_hypothesis_and_every_variant_from_that_one_line(tmp_path, entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    log_path, frozen, variants = _commit(tmp_path, entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry)
    replayed = JsonlAuditLog(log_path).replay()
    assert replayed.get(frozen.hypothesis_id) == frozen
    for v in variants:
        assert replayed.get_variant(v.strategy_variant_id) == v


def test_no_commit_line_means_no_hypothesis_at_all_never_a_partial_one(tmp_path, entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry):
    # Simulates a crash BEFORE the single atomic append() -- the log file
    # never receives the line, so replay must show NOTHING for this
    # hypothesis, never a partially-registered one.
    log_path = tmp_path / "audit.jsonl"
    replayed_before = JsonlAuditLog(log_path).replay()
    assert replayed_before.all_hypotheses() == ()
    _, frozen, variants = _commit(tmp_path, entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, run_registry)
    replayed_after = JsonlAuditLog(log_path).replay()
    assert replayed_after.get(frozen.hypothesis_id) == frozen
    assert len(replayed_after.variants_for(frozen.hypothesis_id)) == len(variants)
