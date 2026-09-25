"""Spec #004 SS7/SS31-32/SS104-109, restructured per Radu's SS110-C/D/E
final decision (2026-09-25) -- content-addressed StrategyHypothesis
(family) + StrategyVariant (per-exit) identity, and an append-only
registry that makes in-place mutation of a PREREGISTERED record
impossible.

`definition_hash`/`variant_definition_hash` cover ONLY fields that define
trading meaning -- administrative timestamps (`created_at`, `approved_at`)
are explicitly excluded (Radu's SS110-E), same discipline as Spec #003's
`freeze_signature_set()`/`build_run_id()`.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from hypothesis.models.entities import (
    EntryDefinition,
    EvidenceProvenance,
    ExitFamily,
    ExitHypothesis,
    HORIZON_REFERENCE_POINT,
    EXIT_EXECUTION_POLICY,
    HorizonCandidateSet,
    HypothesisProposal,
    HypothesisStatus,
    HypothesisUniverse,
    LaneStateCondition,
    ParameterSource,
    ReasonCodeCondition,
    StrategyHypothesis,
    StrategyVariant,
    VariantTag,
)


def _condition_key(c: "LaneStateCondition | ReasonCodeCondition") -> str:
    if isinstance(c, LaneStateCondition):
        return f"LANE:{c.lane}={c.label}:negate={c.negate}"
    if isinstance(c, ReasonCodeCondition):
        return f"REASON:{c.reason_code}:negate={c.negate}"
    raise TypeError(f"unknown condition type: {type(c)!r}")


def _entry_fp(entry: EntryDefinition) -> str:
    core = "&".join(sorted(_condition_key(c) for c in entry.core_conditions))
    conf = "&".join(sorted(_condition_key(c) for c in entry.confirmation_conditions))
    return f"CORE[{core}]CONF[{conf}]"


def _horizon_fp(hs: HorizonCandidateSet) -> str:
    return f"{hs.unit}:{','.join(str(v) for v in sorted(hs.values))}"


def _evidence_fp(ep: EvidenceProvenance) -> str:
    return (
        f"{ep.evaluation_run_id}::{ep.evaluation_engine_version}::{ep.evaluation_config_version}::"
        f"{ep.signature_id}::{ep.signature_set_id}::{ep.discovery_engine_version}::"
        f"{ep.discovery_config_version}::{ep.timeframe}"
    )


def hypothesis_fingerprint(
    parent_signature_id: str, direction: str, entry_definition: EntryDefinition,
    entry_execution_policy: str, horizon_candidate_set: HorizonCandidateSet,
    evidence_provenance: EvidenceProvenance, strategy_config_version: str,
) -> str:
    """Excludes `direction_basis` (audit-trail-only, SS10, never part of
    the hash TEST 21 checks -- only `direction` itself) and every
    administrative timestamp/approval field."""
    return (
        f"{parent_signature_id}::{direction}::{_entry_fp(entry_definition)}::"
        f"{entry_execution_policy}::{_horizon_fp(horizon_candidate_set)}::"
        f"{_evidence_fp(evidence_provenance)}::{strategy_config_version}"
    )


def build_hypothesis_id(fingerprint: str) -> tuple[str, str]:
    """Returns (hypothesis_id, definition_hash). Purely a function of the
    fingerprint -- identical inputs ALWAYS reproduce the identical id
    (TEST 44), no random/incrementing component anywhere."""
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    return f"hyp_{digest}", digest


def _exit_fp(ex: ExitHypothesis) -> str:
    inv = "&".join(sorted(
        f"LANE:{c.lane}:{','.join(c.holds_labels or ())}" if c.lane is not None
        else f"REASON:{c.reason_code}:{c.triggers_on_presence}"
        for c in ex.invalidation_conditions
    ))
    return (
        f"{ex.exit_family}::{ex.horizon_reference_point}::{ex.exit_execution_policy}::"
        f"{ex.time_exit_bars}::{inv}::{ex.max_holding_bars}::{ex.parameter_source}"
    )


def variant_fingerprint(parent_definition_hash: str, exit_hypothesis: ExitHypothesis) -> str:
    return f"{parent_definition_hash}::{_exit_fp(exit_hypothesis)}"


def build_variant_id(fingerprint: str) -> tuple[str, str]:
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    return f"var_{digest}", digest


def build_variant(
    parent: StrategyHypothesis, exit_hypothesis: ExitHypothesis, variant_tag: str, created_at: str,
) -> StrategyVariant:
    fingerprint = variant_fingerprint(parent.definition_hash, exit_hypothesis)
    variant_id, digest = build_variant_id(fingerprint)
    return StrategyVariant(
        strategy_variant_id=variant_id,
        parent_hypothesis_id=parent.hypothesis_id,
        variant_definition_hash=digest,
        exit_hypothesis=exit_hypothesis,
        variant_tag=variant_tag,
        created_at=created_at,
    )


def materialize_variants(
    parent: StrategyHypothesis,
    signal_invalidation_exits: tuple[ExitHypothesis, ...] = (),
    created_at: str = "",
) -> tuple[StrategyVariant, ...]:
    """Eager materialization at freeze/preregistration time (Radu's
    SS110-C/D, 2026-09-25): every value in `parent.horizon_candidate_set.
    values` becomes its own TIME_EXIT StrategyVariant -- the shortest
    horizon tagged BASELINE_VARIANT, the rest EXPERIMENTAL_VARIANT (a
    documented Level 1 choice, SS83: TIME_EXIT is the mandatory baseline
    exit family, SS24). Every supplied SIGNAL_INVALIDATION ExitHypothesis
    becomes one more EXPERIMENTAL_VARIANT. #005 must only ever select
    among these pre-existing ids -- never create a new one dynamically
    (this is what proves [2,3,5] were ALL considered before any backtest
    ran, not invented after seeing which one won)."""
    variants: list[StrategyVariant] = []
    sorted_horizons = sorted(parent.horizon_candidate_set.values)
    for i, bars in enumerate(sorted_horizons):
        exit_h = ExitHypothesis(
            exit_family=ExitFamily.TIME_EXIT.value,
            horizon_reference_point=HORIZON_REFERENCE_POINT,
            exit_execution_policy=EXIT_EXECUTION_POLICY,
            parameter_source=ParameterSource.EVIDENCE_DERIVED.value,
            time_exit_bars=bars,
        )
        tag = VariantTag.BASELINE_VARIANT.value if i == 0 else VariantTag.EXPERIMENTAL_VARIANT.value
        variants.append(build_variant(parent, exit_h, tag, created_at))
    for exit_h in signal_invalidation_exits:
        variants.append(build_variant(parent, exit_h, VariantTag.EXPERIMENTAL_VARIANT.value, created_at))
    return tuple(variants)


class ImmutableHypothesisError(ValueError):
    pass


class HypothesisRegistry:
    """Append-only (Spec #004 SS31/SS53): nothing is ever deleted, and a
    PREREGISTERED record can never be overwritten with different content
    under the same id -- the only way to change trading meaning is
    `create_new_version()`, which always produces a different
    `hypothesis_id` (TEST 24/25)."""

    def __init__(self) -> None:
        self._hypotheses: dict[str, StrategyHypothesis] = {}
        self._variants: dict[str, StrategyVariant] = {}
        self._proposals: dict[str, HypothesisProposal] = {}
        self._rejected_proposal_ids: set[str] = set()

    def register(self, hyp: StrategyHypothesis) -> StrategyHypothesis:
        existing = self._hypotheses.get(hyp.hypothesis_id)
        if existing is not None:
            if existing.definition_hash != hyp.definition_hash:
                raise ImmutableHypothesisError(
                    f"hypothesis_id={hyp.hypothesis_id!r} already registered with a DIFFERENT "
                    f"definition_hash -- ids are content-addressed and must never be reused for "
                    f"different content"
                )
            if existing.status == HypothesisStatus.PREREGISTERED.value and existing != hyp:
                raise ImmutableHypothesisError(
                    f"hypothesis_id={hyp.hypothesis_id!r} is PREREGISTERED and immutable -- "
                    f"use create_new_version() instead of re-registering with changed fields"
                )
        self._hypotheses[hyp.hypothesis_id] = hyp
        return hyp

    def register_variant(self, variant: StrategyVariant) -> StrategyVariant:
        existing = self._variants.get(variant.strategy_variant_id)
        if existing is not None and existing.variant_definition_hash != variant.variant_definition_hash:
            raise ImmutableHypothesisError(
                f"strategy_variant_id={variant.strategy_variant_id!r} already registered with a "
                f"DIFFERENT variant_definition_hash"
            )
        self._variants[variant.strategy_variant_id] = variant
        return variant

    def get(self, hypothesis_id: str) -> Optional[StrategyHypothesis]:
        return self._hypotheses.get(hypothesis_id)

    def get_variant(self, strategy_variant_id: str) -> Optional[StrategyVariant]:
        return self._variants.get(strategy_variant_id)

    def variants_for(self, hypothesis_id: str) -> tuple[StrategyVariant, ...]:
        return tuple(v for v in self._variants.values() if v.parent_hypothesis_id == hypothesis_id)

    def all_hypotheses(self) -> tuple[StrategyHypothesis, ...]:
        return tuple(self._hypotheses.values())

    def all_variants(self) -> tuple[StrategyVariant, ...]:
        return tuple(self._variants.values())

    # -- Proposal accounting (Spec #004 SS53-55/SS108) -------------------
    # A HypothesisProposal that never becomes a StrategyHypothesis (e.g.
    # complexity-rejected, or rejected by human decision after review)
    # must still be retrievable -- "we considered 40, preregistered 3"
    # has to remain provable (SS53), never silently dropped.

    def register_proposal(self, proposal: HypothesisProposal) -> HypothesisProposal:
        existing = self._proposals.get(proposal.proposal_id)
        if existing is not None and existing != proposal:
            raise ImmutableHypothesisError(
                f"proposal_id={proposal.proposal_id!r} already registered with different content"
            )
        self._proposals[proposal.proposal_id] = proposal
        return proposal

    def mark_proposal_rejected(self, proposal_id: str) -> None:
        if proposal_id not in self._proposals:
            raise ValueError(f"proposal_id={proposal_id!r} was never registered")
        self._rejected_proposal_ids.add(proposal_id)

    def all_proposals(self) -> tuple[HypothesisProposal, ...]:
        return tuple(self._proposals.values())

    def rejected_proposal_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._rejected_proposal_ids))


def build_hypothesis_universe(universe_id: str, registry: "HypothesisRegistry", selection_policy: str) -> HypothesisUniverse:
    """Spec #004 SS54-55 -- a full accounting snapshot for one research
    cycle, straight from the append-only registry. Nothing here is ever
    filtered down to "just the winners" (SS55)."""
    all_hyps = registry.all_hypotheses()
    preregistered = tuple(sorted(h.hypothesis_id for h in all_hyps if h.status == HypothesisStatus.PREREGISTERED.value))
    hypothesis_rejected = tuple(sorted(h.hypothesis_id for h in all_hyps if h.status == HypothesisStatus.REJECTED.value))
    all_rejected = tuple(sorted(set(hypothesis_rejected) | set(registry.rejected_proposal_ids())))
    all_proposals = tuple(sorted(p.proposal_id for p in registry.all_proposals()))
    return HypothesisUniverse(
        universe_id=universe_id, all_proposals=all_proposals, all_rejected=all_rejected,
        all_preregistered=preregistered, selection_policy=selection_policy,
    )


def create_new_version(parent: StrategyHypothesis, **overrides) -> StrategyHypothesis:
    """Any change to a hypothesis after it exists must go through this
    (Spec #004 SS31, TEST 25) -- never mutate `parent` (its dataclass is
    frozen anyway). Recomputes the fingerprint/id from the merged fields;
    if nothing that affects `definition_hash` actually changed, raises
    rather than silently returning an indistinguishable "new" version."""
    merged = dict(
        parent_signature_id=parent.parent_signature_id,
        direction=parent.direction,
        entry_definition=parent.entry_definition,
        entry_execution_policy=parent.entry_execution_policy,
        horizon_candidate_set=parent.horizon_candidate_set,
        evidence_provenance=parent.evidence_provenance,
        strategy_config_version=parent.strategy_config_version,
    )
    merged.update({k: v for k, v in overrides.items() if k in merged})
    fingerprint = hypothesis_fingerprint(**merged)
    hypothesis_id, definition_hash = build_hypothesis_id(fingerprint)
    if hypothesis_id == parent.hypothesis_id:
        raise ValueError(
            "create_new_version() called with fields identical to the parent's definition_hash "
            "-- nothing changed, this would not be a new version"
        )
    return StrategyHypothesis(
        hypothesis_id=hypothesis_id,
        hypothesis_version=parent.hypothesis_version + 1,
        definition_hash=definition_hash,
        status=HypothesisStatus.DRAFT.value,
        research_mode=overrides.get("research_mode", parent.research_mode),
        parent_signature_id=merged["parent_signature_id"],
        signature_set_id=overrides.get("signature_set_id", parent.signature_set_id),
        direction=merged["direction"],
        direction_basis=overrides.get("direction_basis", parent.direction_basis),
        entry_definition=merged["entry_definition"],
        entry_execution_policy=merged["entry_execution_policy"],
        horizon_candidate_set=merged["horizon_candidate_set"],
        variant_ids=(),
        evidence_provenance=merged["evidence_provenance"],
        hypothesis_provenance=overrides.get("hypothesis_provenance", parent.hypothesis_provenance),
        constraints=overrides.get("constraints", parent.constraints),
        created_at=overrides.get("created_at", parent.created_at),
        created_by=overrides.get("created_by", parent.created_by),
        strategy_config_version=merged["strategy_config_version"],
        supersedes_hypothesis_id=parent.hypothesis_id,
    )
