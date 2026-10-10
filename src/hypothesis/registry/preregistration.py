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

Stage 6 -- #004 preregistration gate hardening (joint remediation design
003+004 section 10; decision registry C1, D1, E1, G1, H1; Findings 1, 2,
14, 15, 16, 17). Authorized by Radu, 2026-10-10.
"""
from __future__ import annotations

from collections import Counter
from typing import Optional

from config_identity.registry import ConfigIdentityError, ConfigRegistry

from discovery.config.loader import DiscoveryConfig

from evaluation.models.entities import EvaluationRunRegistry

from hypothesis.config.loader import HypothesisConfig, load_config as load_hypothesis_config
from hypothesis.consensus.consensus import can_preregister
from hypothesis.models.entities import (
    ConsensusRecord,
    HypothesisProposal,
    HypothesisResearchMode,
    HypothesisStatus,
    StrategyHypothesis,
    StrategyVariant,
)
from hypothesis.proposals.validator import ProposalValidationResult, validate_proposal
from hypothesis.registry.hypotheses import HypothesisRegistry, materialize_variants, proposal_content_fingerprint
from hypothesis.validation.rules import validate_for_preregistration

# Stage 6 -- decision registry G1: the ONLY Spec #003 evaluation mode whose
# evidence may reach PREREGISTERED.
REQUIRED_EVALUATION_MODE = "FORMAL_DEVELOPMENT"


class PreregistrationError(ValueError):
    pass


def verify_draft_matches_proposal(
    draft: StrategyHypothesis, proposal: HypothesisProposal, variants: tuple[StrategyVariant, ...],
) -> tuple[bool, tuple[str, ...]]:
    """Stage 6 -- joint remediation design 003+004 section 10, Finding 14
    part 1. Before this check, nothing compared the draft's trading
    content against the proposal it claims to descend from -- the only
    link was the `proposal_id` STRING, which is not content-addressed.

    Field-by-field equality: `draft.direction == proposal.direction`;
    `draft.entry_definition == proposal.entry_definition`;
    `draft.entry_execution_policy == proposal.entry_execution_policy`;
    `draft.horizon_candidate_set == proposal.horizon_candidates`;
    `draft.evidence_provenance == proposal.source_evidence`.

    Exits by REPLAY, not equality (`materialize_variants()`'s TIME_EXIT
    expansion is one-to-many): `materialize_variants()` is re-run on the
    draft with `proposal.exit_hypotheses` and with `baseline_time_exit_
    bars` read EXCLUSIVELY from `proposal.horizon_candidates.designated_
    baseline_bars`, and the supplied `variants` must equal that replay
    exactly, as a multiset of (strategy_variant_id, variant_definition_
    hash, parent_hypothesis_id, exit_hypothesis, variant_tag) --
    every proposal exit present, NO other content the proposal didn't ask
    for, and the BASELINE_VARIANT tag on exactly the designated horizon
    (never chosen by a free call-site argument). `created_at` is
    administrative and not compared.

    This proves the draft and the proposal agree with EACH OTHER -- not,
    by itself, that either is what the human approved; that is the
    separate `HumanDecision.content_fingerprint`/`approved_designated_
    baseline_bars` check in `preregister_hypothesis()` (a proposal and a
    draft mutated TOGETHER pass this function and are caught there)."""
    errors: list[str] = []
    field_pairs = (
        ("direction", draft.direction, "direction", proposal.direction),
        ("entry_definition", draft.entry_definition, "entry_definition", proposal.entry_definition),
        ("entry_execution_policy", draft.entry_execution_policy, "entry_execution_policy", proposal.entry_execution_policy),
        ("horizon_candidate_set", draft.horizon_candidate_set, "horizon_candidates", proposal.horizon_candidates),
        ("evidence_provenance", draft.evidence_provenance, "source_evidence", proposal.source_evidence),
    )
    for draft_field, draft_value, proposal_field, proposal_value in field_pairs:
        if draft_value != proposal_value:
            errors.append(
                f"draft.{draft_field}={draft_value!r} does not equal proposal.{proposal_field}="
                f"{proposal_value!r} -- a draft must carry exactly the content of the proposal it "
                f"descends from (Stage 6, Finding 14)"
            )

    designated = proposal.horizon_candidates.designated_baseline_bars
    try:
        replay = materialize_variants(
            draft, signal_invalidation_exits=proposal.exit_hypotheses, created_at="",
            baseline_time_exit_bars=designated,
        )
    except ValueError as exc:
        errors.append(
            f"materialize_variants() replay from the proposal failed (Stage 6, Finding 14): {exc}"
        )
        return (False, tuple(errors))

    def _key(v: StrategyVariant) -> tuple:
        return (v.strategy_variant_id, v.variant_definition_hash, v.parent_hypothesis_id, v.exit_hypothesis, v.variant_tag)

    expected = Counter(_key(v) for v in replay)
    supplied = Counter(_key(v) for v in variants)
    missing = expected - supplied
    unexpected = supplied - expected
    if missing:
        errors.append(
            f"{sum(missing.values())} variant(s) the proposal requires (replayed from proposal.exit_"
            f"hypotheses + horizon_candidates, baseline from designated_baseline_bars={designated!r}) "
            f"are not among the supplied variants: {sorted(k[0] + ':' + k[4] for k in missing)!r} "
            f"(Stage 6, Finding 14)"
        )
    if unexpected:
        errors.append(
            f"{sum(unexpected.values())} supplied variant(s) are not part of the proposal's own replay -- "
            f"content or a BASELINE_VARIANT/EXPERIMENTAL_VARIANT tag the proposal never asked for "
            f"(designated_baseline_bars={designated!r}): {sorted(k[0] + ':' + k[4] for k in unexpected)!r} "
            f"(Stage 6, Finding 14)"
        )
    return (not errors, tuple(errors))


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
       PATCH #004-B finding #2), which since Stage 6 also enforces
       Finding 15's full contract (exactly one TIME_EXIT per candidate
       value, both directions; uniqueness by full variant fingerprint;
       exit-field semantics).

    Stage 6 additions (joint remediation design 003+004 section 10;
    authorized 2026-10-10), all evaluated BEFORE any registry write:
    - D1 (decision registry D1, tied to C1): `validate_proposal()` is
      RE-RUN live on the `proposal` argument, against the SAME config
      snapshots registered for this operation -- the "hypothesis" snapshot
      step -1 resolved and verified against the mandatory live re-read
      (C1), and the "discovery" snapshot, which must ALSO already be
      registered in `config_registry` by an earlier step (never
      established here). Nothing cached can go stale: emptied/altered
      `facts_from_evidence`/`interpretation`, or any other field the
      validator reads, is caught by construction. The cached
      `proposal_validation` is kept only as a proposal_id binding and as
      an extra refusal when it says invalid -- never trusted when it says
      valid.
    - Finding 14: `verify_draft_matches_proposal()` (draft == proposal
      field by field; variants == the proposal's own `materialize_
      variants()` replay, baseline read EXCLUSIVELY from `proposal.
      horizon_candidates.designated_baseline_bars`); the human decision
      must carry `content_fingerprint` equal to `proposal_content_
      fingerprint()` recomputed from the LIVE proposal, and, as its OWN
      separate check, `approved_designated_baseline_bars` equal to the
      LIVE `designated_baseline_bars` -- a proposal and draft mutated
      TOGETHER after approval are caught here, including a change to the
      designated baseline alone.
    - G1 + Finding 2 (decision registry G1): hard-reject unless
      `proposal.source_evidence.evaluation_mode == "FORMAL_DEVELOPMENT"`
      AND the REAL `run_registry.mode == "FORMAL_DEVELOPMENT"` (a declared
      mode is additionally cross-checked against the real run record by
      `check_provenance_matches_run()`); hard-reject unless
      `draft.research_mode == "PREREGISTERED_STRATEGY"`. Procedural
      discipline only -- this does NOT make FORMAL_DEVELOPMENT evidence
      confirmatory (decision registry G1/G2).
    - E1 (decision registry E1): `registry.dry_run_preregistration()`
      simulates the exact write sequence (hypothesis, then each variant in
      order) against a virtual copy of the registry state; any conflict
      refuses the call with NO write performed.

      Guarantee scope, quoted exactly from decision registry E1, never
      paraphrased into a broader claim:
      "The batch-internal simulated-sequential dry run guarantees no
      partial write under exactly THREE named conditions (content
      mismatch; PREREGISTERED-content mismatch; variant content
      mismatch), ONLY under synchronous execution with no write from
      another caller interleaved between the dry run and the real
      writes."

      Known limitation, a PRESENT fact, quoted exactly from decision
      registry E1: "An exception or failure OUTSIDE the three named
      conditions (e.g. an unexpected error from a bug elsewhere in the
      call path) is NOT guaranteed to leave the registry in an
      all-or-nothing state RIGHT NOW, under the CURRENT plain in-memory
      dict -- this is a gap in today's implementation, not a risk that
      first appears after some future storage-layer migration."

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
    discovery_registered = None
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
        # Stage 6, D1: the live validate_proposal() re-run needs the
        # Discovery vocabulary too -- from the snapshot registered for this
        # operation by an earlier step, never loaded or registered here.
        try:
            discovery_registered = config_registry.resolve("discovery")
        except ConfigIdentityError as exc:
            errors.append(
                f"config_registry has no 'discovery' domain registered yet -- preregister_hypothesis() "
                f"re-runs validate_proposal() against the Discovery config registered for this operation "
                f"by an earlier step, and never establishes that reference itself (Stage 6, D1): {exc}"
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

    # Stage 6, Finding 14 part 1: the draft (and its variants) carry
    # exactly the proposal's content.
    match_ok, match_errors = verify_draft_matches_proposal(draft, proposal, variants)
    if not match_ok:
        errors.extend(match_errors)

    # Stage 6, Finding 14 part 2 + baseline designation: the human
    # approval is bound to THIS content, and -- separately -- to this
    # designated baseline. Both recomputed from the LIVE proposal.
    if consensus.human_decision is not None:
        live_fingerprint = proposal_content_fingerprint(proposal)
        if consensus.human_decision.content_fingerprint is None:
            errors.append(
                "consensus.human_decision carries no content_fingerprint -- an approval not bound to the "
                "content actually reviewed cannot preregister anything (Stage 6, Finding 14); build it "
                "with consensus.record_human_decision(proposal, ...)"
            )
        elif consensus.human_decision.content_fingerprint != live_fingerprint:
            errors.append(
                f"consensus.human_decision.content_fingerprint={consensus.human_decision.content_fingerprint!r} "
                f"does not match the fingerprint of the LIVE proposal content {live_fingerprint!r} -- the "
                f"proposal changed after the human approved it (Stage 6, Finding 14)"
            )
        live_designated = proposal.horizon_candidates.designated_baseline_bars
        if consensus.human_decision.approved_designated_baseline_bars != live_designated:
            errors.append(
                f"consensus.human_decision.approved_designated_baseline_bars="
                f"{consensus.human_decision.approved_designated_baseline_bars!r} does not match the LIVE "
                f"proposal.horizon_candidates.designated_baseline_bars={live_designated!r} -- the baseline "
                f"designation changed after approval (Stage 6, Finding 14 -- checked on its own, since it "
                f"is outside every economic fingerprint)"
            )

    # Stage 6, G1 + Finding 2: evidentiary admission.
    if proposal.source_evidence.evaluation_mode != REQUIRED_EVALUATION_MODE:
        errors.append(
            f"proposal.source_evidence.evaluation_mode={proposal.source_evidence.evaluation_mode!r} -- only "
            f"{REQUIRED_EVALUATION_MODE!r} evidence may reach PREREGISTERED (Stage 6, decision registry G1)"
        )
    if run_registry.mode != REQUIRED_EVALUATION_MODE:
        errors.append(
            f"run_registry.mode={run_registry.mode!r} -- the REAL evaluation run this evidence traces to is "
            f"not {REQUIRED_EVALUATION_MODE!r} (Stage 6, decision registry G1)"
        )
    if draft.research_mode != HypothesisResearchMode.PREREGISTERED_STRATEGY.value:
        errors.append(
            f"draft.research_mode={draft.research_mode!r} -- only "
            f"{HypothesisResearchMode.PREREGISTERED_STRATEGY.value!r} may reach PREREGISTERED "
            f"(Stage 6, Finding 2)"
        )

    if not proposal_validation.valid:
        errors.append(
            f"the source HypothesisProposal failed proposals/validator.py's own check: "
            f"{proposal_validation.errors!r}"
        )

    # Stage 6, D1: LIVE re-validation of the proposal argument, against the
    # registered snapshots -- never the cached flag above.
    if fresh_registered is not None and discovery_registered is not None:
        snapshot_hypothesis_config = HypothesisConfig(
            data=fresh_registered.content, config_version=fresh_registered.version,
            raw_texts=fresh_registered.raw_texts,
        )
        discovery_content = discovery_registered.content
        snapshot_discovery_config = DiscoveryConfig(
            features=discovery_content["features"], states=discovery_content["states"],
            discovery=discovery_content["discovery"], eligibility=discovery_content["eligibility"],
            config_version=discovery_registered.version, raw_texts=discovery_registered.raw_texts,
        )
        live_validation = validate_proposal(proposal, snapshot_discovery_config, snapshot_hypothesis_config)
        if not live_validation.valid:
            errors.append(
                f"the LIVE proposal fails validate_proposal() re-run at the gate against the registered "
                f"config snapshots (Stage 6, decision registry D1): {live_validation.errors!r}"
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

    # Stage 6, E1: simulated-sequential dry run of the exact writes below,
    # same order, against a virtual copy -- nothing is written unless the
    # whole sequence passes. Scope: the three named conditions, under
    # synchronous execution only (see docstring; decision registry E1).
    conflicts = registry.dry_run_preregistration(frozen, variants)
    if conflicts:
        raise PreregistrationError(
            "simulated-sequential dry run found a registry conflict -- NO write performed "
            f"(Stage 6, decision registry E1): {'; '.join(conflicts)}"
        )

    registry._force_register(frozen)
    for v in variants:
        registry.register_variant(v)
    return frozen
