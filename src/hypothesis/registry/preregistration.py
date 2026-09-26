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

from evaluation.models.entities import EvaluationRunRegistry

from hypothesis.consensus.consensus import can_preregister
from hypothesis.models.entities import ConsensusRecord, HypothesisStatus, StrategyHypothesis, StrategyVariant
from hypothesis.proposals.validator import ProposalValidationResult
from hypothesis.registry.hypotheses import HypothesisRegistry
from hypothesis.validation.rules import validate_for_preregistration


class PreregistrationError(ValueError):
    pass


def preregister_hypothesis(
    draft: StrategyHypothesis,
    variants: tuple[StrategyVariant, ...],
    *,
    proposal_validation: ProposalValidationResult,
    consensus: ConsensusRecord,
    registry: HypothesisRegistry,
    run_registry: EvaluationRunRegistry,
    hypothesis_config: dict,
) -> StrategyHypothesis:
    """The ONLY function that may produce a PREREGISTERED
    StrategyHypothesis. Enforces, in order, and raises
    `PreregistrationError` (never proceeds partially) on the first
    failing group:

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
       outcome-contamination, per-signature hypothesis budget, and
       variant completeness -- all now performed by
       `validate_for_preregistration()` (PATCH #004-A findings #2/#5).

    On success, freezes `draft` into PREREGISTERED (a NEW
    `StrategyHypothesis`, since the dataclass is frozen -- `hypothesis_id`/
    `definition_hash` are unchanged, since freezing only flips `status`),
    registers it plus every variant into `registry`, and returns the
    frozen hypothesis. Callers that need durable persistence should use
    `registry.persistence.PersistentHypothesisRegistry.preregister()`
    instead of calling this function directly against a bare in-memory
    `HypothesisRegistry`."""
    errors: list[str] = []

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

    gate_ok, gate_errors = validate_for_preregistration(frozen, variants, registry, hypothesis_config, run_registry)
    if not gate_ok:
        raise PreregistrationError("; ".join(gate_errors))

    registry._force_register(frozen)
    for v in variants:
        registry.register_variant(v)
    return frozen
