# Spec #004 v1.0 -- Registry Contract

The Hypothesis Registry's exact guarantees for any consumer (Spec #005,
a future dashboard, a human audit) -- what it promises, and what it
deliberately refuses to do.

## Identity

| Entity | Id field | Derived from | Excludes |
|---|---|---|---|
| `StrategyHypothesis` | `hypothesis_id` = `f"hyp_{digest}"` | `hypothesis_fingerprint()`: `parent_signature_id`, `direction`, `entry_definition`, `entry_execution_policy`, `horizon_candidate_set`, every field of `evidence_provenance`, `strategy_config_version` | `direction_basis`, `created_at`, `created_by`, `hypothesis_provenance` (all administrative/audit-trail) |
| `StrategyVariant` | `strategy_variant_id` = `f"var_{digest}"` | `variant_fingerprint()`: parent's `definition_hash` + this variant's own `exit_hypothesis` (all fields, including `parameter_source`) | `variant_tag`, `created_at` |
| `StrategyDefinition` | `strategy_id` = `f"strat_{digest}"` | `hypothesis_id` + `strategy_variant_id` | -- |

`build_hypothesis_id()`/`build_variant_id()` are pure functions of their
fingerprint string -- identical inputs always reproduce the identical id
(TEST 44), with no random or time-based component anywhere.

**Content-addressed identity is now RE-VERIFIED at the gate, not just
computed once (PATCH #004-B finding #2, GPT Review #004 Round 2).**
Before this patch, `preregister_hypothesis()` trusted a `StrategyHypothesis`/
`StrategyVariant`'s own claimed `hypothesis_id`/`definition_hash`/
`strategy_variant_id`/`variant_definition_hash` -- nothing recomputed the
fingerprint from the object's actual fields and compared it. A hand-built
object with an arbitrary, non-matching id/hash could pass every other
check (provenance, budget, completeness) and reach the registry, quietly
breaking "the id proves the content" for every future lookup.
`validate_for_preregistration()` now recomputes `hypothesis_fingerprint()`
from the hypothesis's OWN fields and hard-fails if `hypothesis_id`/
`definition_hash` don't match, then does the same per variant with
`variant_fingerprint()` -- against the INDEPENDENTLY-recomputed
`definition_hash`, never the hypothesis's own possibly-wrong claim, so a
tampered parent can't launder a tampered variant through it either
(TEST 63).

`StrategyVariant`'s `variant_tag` is excluded from `variant_definition_hash`
on purpose (it is methodological metadata -- BASELINE_VARIANT vs
EXPERIMENTAL_VARIANT -- not trading meaning), but that does NOT mean it is
mutable: see "Variant materialization contract" below for the separate,
full-object immutability rule `register_variant()` enforces (PATCH #004-B
finding #3).

## Mutability rules

1. **DRAFT / REVIEWED / REJECTED** records may be freely re-registered
   with the SAME id as long as content (`definition_hash`) hasn't
   changed; registering different content under an id already used for
   different content raises `ImmutableHypothesisError` regardless of
   status.
2. **PREREGISTERED is immutable, AND may only be created through the one
   atomic gate (PATCH #004-A finding #1, GPT Review #004 Round 1).**
   `HypothesisRegistry.register()` refuses any write to an existing
   `PREREGISTERED` id whose content differs at all, even by one field,
   from what's stored -- but it ALSO refuses to insert a brand-new
   `PREREGISTERED` hypothesis for the first time (`existing is None and
   status == PREREGISTERED` is a hard `ImmutableHypothesisError`, not a
   silent success). The only supported path that may produce one is
   `registry/preregistration.py:preregister_hypothesis(draft, variants,
   *, proposal, proposal_validation, consensus, registry, run_registry,
   hypothesis_config)`, which requires, in order: `proposal.proposal_id
   == proposal_validation.proposal_id == consensus.proposal_id ==
   draft.hypothesis_provenance.proposal_id`, and (when a human decision
   is present) `draft.hypothesis_provenance.approved_by`/`approved_at`
   match `consensus.human_decision.decided_by`/`decided_at` exactly
   (PATCH #004-B finding #1, GPT Review #004 Round 2 -- see below); the
   source `HypothesisProposal` passed `proposals/validator.py`'s own
   check; an explicit `HumanDecision(decision=HumanDecisionValue.APPROVE,
   ...)` on the supplied `ConsensusRecord` (`consensus/consensus.py:
   can_preregister()` -- a `REJECT` decision, free-text approval, or no
   decision at all is a hard rejection, never treated as approval); the
   input hypothesis still being `status=DRAFT` (a caller may never hand
   in an object already claiming `PREREGISTERED`); and the full
   `validate_for_preregistration()` gate (content-addressed identity,
   provenance, budget, variant completeness, outcome-contamination --
   see below). Before PATCH #004-A, a caller could construct
   `StrategyHypothesis(status="PREREGISTERED", ...)` by hand and pass it
   straight to the (then-generic) `register()`, bypassing every one of
   these checks; `build_strategy_definition()` now also independently
   re-verifies the hypothesis/variant it is given against what the
   registry itself has stored (object equality, not the object's own
   claimed status), so a fabricated object cannot reach a
   `StrategyDefinition` even if it slipped past registration (TEST 53-55).

   **PATCH #004-B finding #1 (GPT Review #004 Round 2):** the checks
   above closed a real gap -- `proposal_validation.valid` and
   `consensus`'s APPROVE decision proved SOME proposal was validated and
   approved, but nothing verified it was THIS proposal, the one `draft`
   actually descends from. A caller could otherwise hand in APPROVE for
   proposal A while preregistering an unrelated draft B. `Proposal
   ValidationResult` gained a `proposal_id` field for exactly this check
   (TEST 62).
3. **The only way to change a hypothesis after the fact is
   `create_new_version(parent, **overrides)`**, which recomputes the
   fingerprint from the merged fields, ALWAYS produces a new
   `hypothesis_id` (raising `ValueError` if nothing that affects the hash
   actually changed), sets `hypothesis_version = parent.hypothesis_version
   + 1`, and sets `supersedes_hypothesis_id = parent.hypothesis_id`. The
   new record starts back at `status = DRAFT` -- it must go through
   consensus/human-approval again before it can reach PREREGISTERED.
4. **Nothing is ever deleted.** `HypothesisRegistry` has no delete/remove
   method for hypotheses, variants, or proposals. A rejected proposal
   stays in `all_proposals()` forever; `mark_proposal_rejected()` only
   adds it to `rejected_proposal_ids()`, it never removes the record.

## Variant materialization contract

`materialize_variants(hypothesis, signal_invalidation_exits=(),
created_at=..., baseline_time_exit_bars=None)` must be called with the
hypothesis's FINAL `horizon_candidate_set` BEFORE `status` is set to
`PREREGISTERED`, and the resulting `strategy_variant_id`s must be
written into `StrategyHypothesis.variant_ids` in full. Every TIME_EXIT
variant inherits `horizon_candidate_set.parameter_source` verbatim
(PATCH #004-A finding #5 -- it is no longer hardcoded to
`EVIDENCE_DERIVED` regardless of how the candidates were actually
chosen, and `parameter_source` is part of the family fingerprint, so the
same `[2,3,5]` proposed for a different reason is a different family
commitment). `variant_tag` is never deduced from `min(horizon)`: by
default every TIME_EXIT variant is `EXPERIMENTAL_VARIANT`; a caller may
explicitly pre-designate exactly one candidate value as
`baseline_time_exit_bars`, which must already be one of
`horizon_candidate_set.values` (`ValueError` otherwise) and is the only
way a variant becomes `BASELINE_VARIANT` (TEST 59-60). Two enforcement
points:

- `validation/rules.py:validate_for_preregistration()` rejects a
  hypothesis whose `variant_ids` doesn't exactly match the variants
  actually supplied to it (TEST 47).
- `registry/strategy_registry.py:build_strategy_definition()` raises
  `ValueError` if asked to build a `StrategyDefinition` for a variant
  whose id is not already present in the parent hypothesis's
  `variant_ids` -- this is the structural guarantee that Spec #005 can
  only ever select among pre-existing variants, never mint one after
  seeing a result.

**A registered `StrategyVariant` is immutable in FULL, including
`variant_tag` (PATCH #004-B finding #3, GPT Review #004 Round 2).**
`variant_tag` is excluded from `variant_definition_hash` (see "Identity"
above), which means the ORIGINAL `register_variant()` check -- same id,
compare only the hash -- could not detect a re-registration that kept
the hash identical but changed `variant_tag` (e.g. rewriting
EXPERIMENTAL_VARIANT to BASELINE_VARIANT after seeing backtest results,
exactly the after-the-fact methodological rewrite the `baseline_time_
exit_bars` design in PATCH #004-A exists to prevent). `register_variant()`
now compares full object equality against any existing record with the
same id: identical content is an idempotent no-op (safe for audit-log
replay), any difference at all -- hash, tag, or anything else --
raises `ImmutableHypothesisError` (TEST 64).

## Provenance contract

Every `StrategyHypothesis.evidence_provenance` (an `EvidenceProvenance`)
names, in full: `evaluation_run_id`, `evaluation_engine_version`,
`evaluation_config_version`, `signature_id`, `signature_set_id`,
`discovery_engine_version`, `discovery_config_version`, `timeframe`.
`validation/provenance.py:check_provenance_matches_run()` compares this
against the ACTUAL `EvaluationRunRegistry` a caller supplies, field by
field -- a mismatch on any single field is a hard rejection (TEST 42-43),
mirroring Spec #003's own FORMAL_DEVELOPMENT provenance guard
(PATCH #003-B) one layer up the chain. **PATCH #004-A finding #2 (GPT
Review #004 Round 1):** this check existed before the patch but nothing
called it from the preregistration path -- `validate_for_preregistration()`
now REQUIRES `run_registry` as an argument and calls
`check_provenance_matches_run()` itself, so it is impossible to reach
`preregister_hypothesis()`'s success path without it running. The same
gate also now checks an internal-consistency rule the review flagged:
`StrategyHypothesis.parent_signature_id`/`signature_set_id` (the fields
the per-signature budget above actually keys on) must equal
`evidence_provenance.signature_id`/`signature_set_id` -- otherwise a
hypothesis could claim budget accounting against one signature while its
evidence actually rests on another (TEST 56).

`EvidencePacket` construction (`evidence/packet.py:build_evidence_packet()`)
has an analogous, earlier cross-artifact contract (PATCH #004-A finding
#3): the supplied `EvaluationSignatureDefinition`, the list of
`EvidenceProfile`s, and the `EvaluationRunRegistry` must agree on
timeframe, Discovery engine/config version, and the exact set of
horizons the run tested (no missing horizon, no extra one, no
duplicate), and every profile must share one `evaluation_mode` equal to
the run's own mode -- any mismatch is a hard `ValueError`, never a
best-effort "looks compatible" packet (TEST 57).

## Budget contract

`validate_for_preregistration()` counts, among a signature's currently
`PREREGISTERED`/`HANDOFF_TO_BACKTEST` hypotheses (never counting
`DRAFT`/`REJECTED` ones), and rejects a NEW hypothesis whose addition
would push that count past `hypothesis_budget.max_hypotheses_per_
signature` (config-versioned, default 3). This is a Level 1 research
control, not a validated trading rule (Spec #004 SS52) -- raising it
never manufactures more findings, it only limits how many distinct
families one signature may spawn before a human must consciously decide
to raise the limit.

## HypothesisUniverse accounting

`registry/hypotheses.py:build_hypothesis_universe()` snapshots, straight
from the append-only registry, with no filtering toward "the winners":
`all_proposals` (every `proposal_id` ever registered), `all_rejected`
(every hypothesis or proposal id marked `REJECTED`), `all_preregistered`
(every hypothesis id currently `PREREGISTERED`). This is the artifact
Spec #005 needs for selection-bias accounting -- "we considered 40,
preregistered 3" must remain provable from this snapshot alone.

**PATCH #004-A finding #6 (GPT Review #004 Round 1): "append-only" is
now durable across a process restart, not just within one.** A bare
`HypothesisRegistry` is still a plain in-memory object -- it holds
nothing once the Python process exits. `registry/persistence.py`
provides `JsonlAuditLog` (one JSON line per meaningful event --
`proposal_registered`, `proposal_rejected`, `preregistration_committed`
-- append-only by construction, `append()` only ever opens the file in
append mode) and `PersistentHypothesisRegistry`, which wraps a bare
`HypothesisRegistry` + a `JsonlAuditLog` and exposes `register_proposal()`,
`mark_proposal_rejected()`, and `preregister()` (which calls the real
`preregister_hypothesis()` gate, then logs the result). `JsonlAuditLog.
replay()` rebuilds an equivalent `HypothesisRegistry` from nothing but
the file -- a completely independent, freshly opened log handle
reconstructs the identical state (TEST 61), which is the property that
matters: a real process restart never has the original in-memory
objects. This composes with, and never replaces, the pure in-memory
`HypothesisRegistry` every existing test and example above still uses
directly.

**PATCH #004-B finding #4 (GPT Review #004 Round 2): the preregistration
write is now atomic at the file-line level, not just durable.** The
original version appended one `hypothesis_preregistered` line followed
by N separate `variant_registered` lines -- a crash between those
appends (or between the in-memory write and the first append) could
leave the in-memory registry and the persisted log in different states:
a hypothesis durable with only SOME of its variants, or none at all.
`preregister()` now appends exactly ONE `preregistration_committed`
record, `{"hypothesis": ..., "variants": [...]}`, in a single `append()`
call. On replay, the hypothesis and every one of its variants appear
together, or the line simply isn't there yet -- never a partial state
(TEST 65). `to_jsonable()`/`from_jsonable()` gained generic recursion
into plain dicts (not just dataclasses/tuples/lists) to support this
single-record shape without a bespoke serializer.
