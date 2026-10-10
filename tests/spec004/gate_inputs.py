"""Stage 6 test helpers (not a test module): build a fully consistent set
of `preregister_hypothesis()` inputs FROM a proposal, so each Stage 6
regression can perturb exactly ONE thing and show that one check firing.

- `make_proposal()` -- `normalize_proposal(make_proposal_raw(...))`.
- `draft_from_proposal()` -- a DRAFT carrying exactly the proposal's
  content (content-addressed id recomputed AFTER any override, so an
  overridden field still yields a self-consistent draft -- only the
  draft-vs-proposal binding is broken, never TEST 63's own check).
- `with_variants()` -- the proposal's own `materialize_variants()`
  replay (its exits; baseline from `designated_baseline_bars` unless
  `baseline` is passed explicitly), `variant_ids` filled in.
- `gate()` -- one `preregister_hypothesis()` call with an approval bound
  to `approval_proposal` (default: the proposal itself).
"""
from __future__ import annotations

import dataclasses

from hypothesis.consensus.consensus import compute_consensus
from hypothesis.models.entities import (
    HypothesisComplexitySnapshot,
    HypothesisProvenance,
    HypothesisResearchMode,
    HypothesisStatus,
    StrategyHypothesis,
)
from hypothesis.proposals.normalize import normalize_proposal
from hypothesis.proposals.validator import ProposalValidationResult
from hypothesis.registry.hypotheses import HypothesisRegistry, build_hypothesis_id, hypothesis_fingerprint, materialize_variants
from hypothesis.registry.preregistration import preregister_hypothesis

from spec004.conftest import approved_human_decision, make_proposal_raw

APPROVED_BY = "radu"
APPROVED_AT = "2026-09-25T00:05:00Z"
_USE_PROPOSAL = object()


def make_proposal(source_evidence_overrides: dict | None = None, horizon_overrides: dict | None = None, **raw_overrides):
    raw = make_proposal_raw(**raw_overrides)
    if source_evidence_overrides:
        raw["source_evidence"] = {**raw["source_evidence"], **source_evidence_overrides}
    if horizon_overrides:
        raw["horizon_candidates"] = {**raw["horizon_candidates"], **horizon_overrides}
    return normalize_proposal(raw)


def draft_from_proposal(proposal, hypothesis_config, **overrides) -> StrategyHypothesis:
    fields = dict(
        direction=proposal.direction, entry_definition=proposal.entry_definition,
        entry_execution_policy=proposal.entry_execution_policy, horizon_candidate_set=proposal.horizon_candidates,
        evidence_provenance=proposal.source_evidence,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, created_at="2026-09-25T00:00:00Z",
    )
    fields.update(overrides)
    ev = fields["evidence_provenance"]
    fp = hypothesis_fingerprint(
        ev.signature_id, fields["direction"], fields["entry_definition"], fields["entry_execution_policy"],
        fields["horizon_candidate_set"], ev, hypothesis_config.config_version,
    )
    hid, dh = build_hypothesis_id(fp)
    return StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.DRAFT.value,
        research_mode=fields["research_mode"], parent_signature_id=ev.signature_id, signature_set_id=ev.signature_set_id,
        direction=fields["direction"], direction_basis=proposal.direction_basis,
        entry_definition=fields["entry_definition"], entry_execution_policy=fields["entry_execution_policy"],
        horizon_candidate_set=fields["horizon_candidate_set"], variant_ids=(), evidence_provenance=ev,
        hypothesis_provenance=HypothesisProvenance(proposal.proposer, proposal.proposal_id, None, APPROVED_BY, APPROVED_AT),
        constraints=HypothesisComplexitySnapshot(
            hypothesis_config.data["hypothesis_complexity"]["max_entry_conditions"],
            hypothesis_config.data["hypothesis_complexity"]["max_optional_confirmation_conditions"],
            hypothesis_config.config_version,
        ),
        created_at=fields["created_at"], created_by=APPROVED_BY, strategy_config_version=hypothesis_config.config_version,
    )


def with_variants(draft, proposal, *, exits=None, baseline=_USE_PROPOSAL, created_at="2026-09-25T00:00:00Z"):
    exits = proposal.exit_hypotheses if exits is None else exits
    baseline = proposal.horizon_candidates.designated_baseline_bars if baseline is _USE_PROPOSAL else baseline
    variants = materialize_variants(draft, signal_invalidation_exits=exits, created_at=created_at, baseline_time_exit_bars=baseline)
    return set_variant_ids(draft, variants), variants


def set_variant_ids(draft, variants):
    return dataclasses.replace(draft, variant_ids=tuple(v.strategy_variant_id for v in variants))


def gate(
    draft, variants, proposal, *, hypothesis_config, config_registry, run_registry, registry=None,
    approval_proposal=None, human_decision=_USE_PROPOSAL, cached_valid=True,
):
    if human_decision is _USE_PROPOSAL:
        human_decision = approved_human_decision(
            by=APPROVED_BY, at=APPROVED_AT, proposal=approval_proposal if approval_proposal is not None else proposal,
        )
    return preregister_hypothesis(
        draft, variants, proposal=proposal,
        proposal_validation=ProposalValidationResult(cached_valid, "OK", (), proposal.proposal_id),
        consensus=compute_consensus(proposal.proposal_id, (), human_decision=human_decision),
        registry=registry if registry is not None else HypothesisRegistry(), run_registry=run_registry,
        hypothesis_config=hypothesis_config, config_registry=config_registry,
    )


def registry_state(registry: HypothesisRegistry) -> tuple[dict, dict]:
    """A snapshot of the registry's full state (values are frozen
    dataclasses, so a shallow copy is an exact, independent snapshot)."""
    return dict(registry._hypotheses), dict(registry._variants)
