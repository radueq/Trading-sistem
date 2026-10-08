"""Spec #004 SS30-31/SS45-46/SS71-72, PATCH #004-A finding #1 (GPT
Review #004 Round 1) -- the ONE atomic entry point that may introduce a
new PREREGISTERED StrategyHypothesis (+ its StrategyVariants) into a
HypothesisRegistry.

Before this patch, a caller could construct `StrategyHypothesis(status=
"PREREGISTERED", ...)` by hand and hand it straight to `HypothesisRegistry.
register()`, bypassing consensus, human approval, provenance checks, and
`validate_for_preregistration()` entirely -- the architecture's own
central guarantee, on paper, was not actually enforced anywhere in code.
`HypothesisRegistry.register()` now refuses a first-time PREREGISTERED
insert (see `registry/hypotheses.py`); this module is the only supported
path that can produce one.
"""
from __future__ import annotations

from typing import Optional

from config_identity.registry import ConfigIdentityError, ConfigRegistry

from evaluation.models.entities import EvaluationRunRegistry

from hypothesis.config.loader import HypothesisConfig, load_config as load_hypothesis_config
from hypothesis.consensus.consensus import can_preregister
from hypothesis.models.entities import ConsensusRecord, HypothesisProposal, HypothesisStatus, StrategyHypothesis, StrategyVariant
from hypothesis.proposals.validator import ProposalValidationResult
from hypothesis.registry.hypotheses import HypothesisRegistry
from hypothesis.validation.rules import validate_for_preregistration


class PreregistrationError(ValueError):
    pass


def preregister_hypothesis(
    draft: StrategyHypothesis,
    variants: tuple[StrategyVariant, ...],
    *,
    proposal: HypothesisProposal,
    proposal_validation: ProposalValidationResult,
    consensus: ConsensusRecord,
    registry: HypothesisRegistry,
    run_registry: EvaluationRunRegistry,
    hypothesis_config: HypothesisConfig,
    config_registry: Optional[ConfigRegistry] = None,
) -> StrategyHypothesis:
    """The ONLY function that may produce a PREREGISTERED
    StrategyHypothesis. Enforces, in order, and raises
    `PreregistrationError` (never proceeds partially) on the first
    failing group:

    -1. Config identity (Stage 3 -- config identity infrastructure,
        decision registry, Stage 3; authorized 2026-10-07; CORRECTED
        round 4 -- GPT changes-required verdict on `565c306`: the gate
        itself must never be the place that FIRST establishes trust in
        a config). `config_registry` is now REQUIRED to already have
        the "hypothesis" domain registered by an EARLIER step in this
        workflow -- resolved via `ConfigRegistry.resolve()` (raises if
        nothing is registered yet), NEVER `register_or_verify()`
        (which would silently accept whatever is offered FIRST, AT the
        gate, as the reference). Omitting `config_registry`, or
        supplying one with no "hypothesis" entry yet, is refused here,
        before any other check and before any registry write -- round
        3's `draft.strategy_config_version` check alone was
        insufficient: that label is just a string on the draft, it
        proves nothing was ALREADY registered anywhere, since any
        caller can set it to match whatever the live file currently
        says. Once resolved, THREE checks run against this ONE
        resolved snapshot, none substituting for another:
        (a) the mandatory live re-read -- `hypothesis.yaml` is read
            FRESH, right now, and verified against the resolved
            snapshot, catching a file that changed on disk since the
            earlier registration;
        (b) the CALLER-SUPPLIED `hypothesis_config` argument, verified
            against the SAME resolved snapshot: its declared `config_
            version` (label) and its actual `.data` (content), checked
            SEPARATELY, both normalized to the same representation
            before the content comparison;
        (c) `draft.strategy_config_version` -- the config version the
            DRAFT itself was built under, recorded at construction
            time -- must equal the resolved snapshot's own version. A
            draft built under one config can never be silently
            preregistered under a different one.
        GPT's own reproduction (round 3): a draft built under config A,
        preregistered while BOTH the caller-supplied `hypothesis_config`
        AND the live file ITSELF had already moved to a self-consistent
        config B, with NO `config_registry` shared -- was wrongly
        ACCEPTED, because the gate was free to treat its OWN fresh read
        as the reference when nothing was registered yet. Requiring
        `resolve()` to succeed closes this: there is no path left where
        the gate can establish its own reference at preregistration
        time.
        `validate_for_preregistration()` below then consumes
        EXCLUSIVELY this resolved snapshot's content -- never a freshly
        re-registered one, never the caller's own, independently-
        mutable `hypothesis_config.data`.
    0. `proposal`, `proposal_validation`, `consensus`, and
       `draft.hypothesis_provenance` all name the SAME proposal, and the
       recorded approver/approval-time on `draft` match the human
       decision actually supplied (PATCH #004-B finding #1, GPT Review
       #004 Round 2) -- before this check, a caller could hand in an
       approval for proposal A while preregistering an unrelated draft B:
       nothing verified `proposal_validation`/`consensus` were computed
       from the SAME proposal the draft claims to descend from, so
       "human approval exists" never actually proved "human approval
       exists FOR THIS HYPOTHESIS" (TEST 62);
    1. the HypothesisProposal that led to `draft` was itself structurally
       valid (`proposal_validation.valid`, from `proposals/validator.py`);
    2. an explicit `HumanDecision(decision=APPROVE, ...)` exists on
       `consensus` (`can_preregister()`) -- a REJECT, or no decision at
       all, stops here;
    3. `draft.status` is DRAFT -- never re-preregistering something
       already final, and a caller must never pass in an object already
       claiming PREREGISTERED (that claim would be meaningless here: this
       function is what performs that transition);
    4. provenance-matches-the-actual-run, `parent_signature_id`/
       `signature_set_id` <-> `evidence_provenance` consistency,
       outcome-contamination, per-signature hypothesis budget, variant
       completeness, AND content-addressed identity (`hypothesis_id`/
       `definition_hash`/`strategy_variant_id`/`variant_definition_hash`
       actually match the fingerprint of the fields they claim to
       address, PATCH #004-B finding #2) -- all now performed by
       `validate_for_preregistration()` (PATCH #004-A findings #2/#5,
       PATCH #004-B finding #2).

    On success, freezes `draft` into PREREGISTERED (a NEW
    `StrategyHypothesis`, since the dataclass is frozen -- `hypothesis_id`/
    `definition_hash` are unchanged, since freezing only flips `status`),
    registers it plus every variant into `registry`, and returns the
    frozen hypothesis. Callers that need durable persistence should use
    `registry.persistence.PersistentHypothesisRegistry.preregister()`
    instead of calling this function directly against a bare in-memory
    `HypothesisRegistry`."""
    errors: list[str] = []

    # Step -1 (Stage 3 -- config identity infrastructure, authorized
    # 2026-10-07; CORRECTED round 4 -- GPT changes-required verdict on
    # `565c306`). `config_registry` is now REQUIRED to already have
    # the "hypothesis" domain registered by an EARLIER step in this
    # workflow. `resolve()` -- never `register_or_verify()` -- so the
    # gate can only ever COMPARE against a pre-existing reference, it
    # can never CREATE one for itself.
    fresh_registered = None
    if config_registry is None:
        errors.append(
            "preregister_hypothesis() requires an explicit config_registry with the 'hypothesis' "
            "domain already registered by an earlier step in this workflow (Stage 3) -- the gate "
            "itself must never be the place that first establishes trust in a config"
        )
    else:
        try:
            fresh_registered = config_registry.resolve("hypothesis")
        except ConfigIdentityError as exc:
            errors.append(
                f"config_registry has no 'hypothesis' domain registered yet -- preregister_hypothesis() "
                f"requires it to already exist from an earlier step in this workflow (Stage 3): {exc}"
            )

    if fresh_registered is not None:
        # (a) mandatory live re-read, against the RESOLVED snapshot --
        # never a fresh registration of its own.
        fresh_hypothesis_config = load_hypothesis_config()
        reread_ok, reread_errors = fresh_registered.verify(fresh_hypothesis_config.config_version, fresh_hypothesis_config.data)
        if not reread_ok:
            errors.append(
                f"hypothesis.yaml changed since it was registered earlier in this operation "
                f"(Stage 3 mandatory live re-read): {'; '.join(reread_errors)}"
            )
        # (b) the caller-supplied hypothesis_config argument, against
        # the SAME resolved snapshot.
        candidate_ok, candidate_errors = fresh_registered.verify(hypothesis_config.config_version, hypothesis_config.data)
        if not candidate_ok:
            errors.append(
                "hypothesis_config supplied to preregister_hypothesis() does not match the registered "
                f"context (Stage 3 mandatory live re-read): {'; '.join(candidate_errors)}"
            )
        # (c) round-3 fix, kept: draft.strategy_config_version -- the
        # config version the DRAFT itself was built under -- must
        # equal the resolved snapshot's own version. A draft built
        # under one config can never be silently preregistered under
        # a different one.
        if draft.strategy_config_version != fresh_registered.version:
            errors.append(
                f"draft.strategy_config_version={draft.strategy_config_version!r} does not match the "
                f"active hypothesis.yaml config_version={fresh_registered.version!r} actually in use at "
                f"this gate (Stage 3 mandatory live re-read) -- a draft built under one config can never "
                f"be silently preregistered under a different one"
            )

    if proposal.proposal_id != proposal_validation.proposal_id:
        errors.append(
            f"proposal.proposal_id={proposal.proposal_id!r} does not match "
            f"proposal_validation.proposal_id={proposal_validation.proposal_id!r} -- the supplied "
            f"validation result must be THIS proposal's own (PATCH #004-B finding #1)"
        )
    if proposal.proposal_id != consensus.proposal_id:
        errors.append(
            f"proposal.proposal_id={proposal.proposal_id!r} does not match "
            f"consensus.proposal_id={consensus.proposal_id!r} -- the supplied consensus/human "
            f"decision must be THIS proposal's own (PATCH #004-B finding #1)"
        )
    if draft.hypothesis_provenance.proposal_id != proposal.proposal_id:
        errors.append(
            f"draft.hypothesis_provenance.proposal_id={draft.hypothesis_provenance.proposal_id!r} "
            f"does not match proposal.proposal_id={proposal.proposal_id!r} -- a hypothesis's own "
            f"provenance must truthfully name the proposal it descends from (PATCH #004-B finding #1)"
        )
    if consensus.human_decision is not None:
        if draft.hypothesis_provenance.approved_by != consensus.human_decision.decided_by:
            errors.append(
                f"draft.hypothesis_provenance.approved_by={draft.hypothesis_provenance.approved_by!r} "
                f"does not match consensus.human_decision.decided_by="
                f"{consensus.human_decision.decided_by!r} (PATCH #004-B finding #1)"
            )
        if draft.hypothesis_provenance.approved_at != consensus.human_decision.decided_at:
            errors.append(
                f"draft.hypothesis_provenance.approved_at={draft.hypothesis_provenance.approved_at!r} "
                f"does not match consensus.human_decision.decided_at="
                f"{consensus.human_decision.decided_at!r} (PATCH #004-B finding #1)"
            )

    if not proposal_validation.valid:
        errors.append(
            f"the source HypothesisProposal failed proposals/validator.py's own check: "
            f"{proposal_validation.errors!r}"
        )

    approve_ok, approve_errors = can_preregister(consensus)
    if not approve_ok:
        errors.extend(approve_errors)

    if draft.status != HypothesisStatus.DRAFT.value:
        errors.append(
            f"draft.status={draft.status!r} -- preregister_hypothesis() only accepts a DRAFT "
            f"hypothesis and performs the transition to PREREGISTERED itself; a caller must never "
            f"pass one in already claiming that status (TEST 53)"
        )

    if errors:
        raise PreregistrationError("; ".join(errors))

    frozen = draft.__class__(**{**draft.__dict__, "status": HypothesisStatus.PREREGISTERED.value})

    # Consumes EXCLUSIVELY the freshly-verified, recursively-frozen
    # snapshot (Stage 3) -- never the caller's own hypothesis_config.data.
    gate_ok, gate_errors = validate_for_preregistration(frozen, variants, registry, fresh_registered.content, run_registry)
    if not gate_ok:
        raise PreregistrationError("; ".join(gate_errors))

    registry._force_register(frozen)
    for v in variants:
        registry.register_variant(v)
    return frozen
