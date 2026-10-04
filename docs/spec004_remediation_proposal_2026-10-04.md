# Spec #004 -- Remediation Design Proposal (2026-10-04)

**Status: DESIGN ONLY. Not authorized for implementation.** Covers
Top Findings 14-19 (GPT's own G1-G6, GPT Review #004, relayed by Radu,
against commit `d272cb8`) plus Top Finding 20 (the separate PATCH
#004-C persistence finding). No code or test is changed by this
document. **Scope note, stated precisely (not as an instruction from
Radu):** this document covers only these six findings + P004C --
Claude's own choice of scope for this round, given the volume of
material, not something Radu's relayed message required excluding.
Claude's own prior Findings 1-13 (the Claude-solo round) still need
their own remediation design, not yet started, and are not covered
here.

**Current status of the three stages, precisely:** (1) findings --
Claude has independently CONFIRMED each of the six findings + P004C,
by code reading and by re-running GPT's own probe script against this
repository (see the matrix's GPT-review status block). **This is
Claude's own technical confirmation, not a closure of documentary
reconciliation with GPT** -- `docs/contract_index.md` correctly states
Spec #004's reconciliation remains OPEN, and that status is unchanged
by this document; (2) remediation DESIGN -- this document, several
options listed per finding, none chosen, and NOT a precondition for
(1)'s status: finishing or not finishing this design has no bearing on
whether the findings themselves are reconciled; (3) implementation/
acceptance -- not started, not authorized.

---

## 1. Top Finding 14 (GPT-G1) -- bind approval/validation to the final frozen content

**Problem restated:** `preregister_hypothesis()` verifies that
`proposal`/`proposal_validation`/`consensus`/`draft.hypothesis_provenance`
agree on WHICH proposal was approved (same `proposal_id`, matching
approver/timestamp), and `validate_for_preregistration()` verifies the
draft's `hypothesis_id`/`definition_hash` match the fingerprint of the
draft's OWN fields. Neither step ever compares the draft's actual
`direction`/`entry_definition`/`entry_execution_policy`/
`horizon_candidate_set` against the fields the APPROVED PROPOSAL
actually declared. "Approved" currently means "an approval record
exists whose id matches," not "an approval exists for this exact
content."

**Why comparing the draft to "the proposal passed into this call" is
not sufficient, by itself (GPT's correction, relayed by Radu):** every
candidate design below must bind content to something fixed BEFORE
this call, not to another object the SAME caller supplies alongside
the draft. `preregister_hypothesis()` receives `proposal` as a plain
argument -- a caller (buggy or adversarial) can mutate `proposal` and
`draft` TOGETHER, under the same `proposal_id`, before the call. A
check that only compares draft fields against the `proposal` object
handed to that same call proves the two agree with EACH OTHER, not
that either one agrees with what `proposal_validation` actually
validated or what the human `consensus` decision actually approved.
The binding has to reach back to the VALIDATION RESULT and the HUMAN
DECISION's own record, not to a second caller-supplied object.
Similarly, no design below may rely on "this draft can only have been
built by a trusted constructor" as a substitute for the gate itself
validating the content it receives: `preregister_hypothesis()` is a
plain function taking a `StrategyHypothesis` value: Python does not
track or enforce how that value was constructed, so nothing strictly
upstream of the gate can remove the need for the gate to check the
object it was actually handed.

**Design options, revised with the above in mind:**

- **(a) Direct field-by-field equality check against `proposal`,
  alone -- INSUFFICIENT, kept here only to name why.** Comparing
  `draft.direction`/`entry_definition`/etc. against the `proposal`
  argument of the SAME call closes nothing if both can be supplied
  together; listed for completeness, not as a candidate.
- **(b) Freeze a content fingerprint into the human decision record AT
  APPROVAL TIME, before this call exists at all, and recompute +
  compare at the gate.** At the moment `consensus`/`HumanDecision` is
  produced (i.e. when `can_preregister()`'s APPROVE is recorded), also
  compute and freeze a fingerprint of the EXACT proposal content that
  was reviewed and approved at that moment (direction, entry
  definition, execution policy, horizon candidates, and the raw exit
  hypotheses as submitted) -- `HumanDecision` or `ConsensusRecord`
  gains an `approved_content_fingerprint` field, written once, when the
  approval itself is recorded, never later. At the gate,
  `preregister_hypothesis()` recomputes the SAME fingerprint from the
  content it is now about to freeze (not from whatever `proposal`
  object the caller also happened to pass in) and compares it against
  `consensus.human_decision.approved_content_fingerprint`. Because that
  field was written at approval time, mutating `proposal` and `draft`
  together AFTER approval no longer helps -- the frozen approval record
  itself won't match. This is the design that actually closes the gap
  GPT described, not (a). Open question: exactly which fields
  participate in this fingerprint, matching the same "faithfully
  derived from" vs. "substituted" distinction below for exits/
  horizons.
- **(c) Derive the draft deterministically from the approved content
  via a single construction function -- a structural aid, NOT a
  substitute for (b).** A `build_draft_from_approved_proposal()`
  helper that is the only INTENDED way to produce a draft reduces the
  chance of accidental drift in normal use, but it cannot be presented
  as removing the possibility of a hand-built, diverging draft -- the
  gate still receives a plain object and must still validate it per
  (b). Worth doing as good practice, not as the actual guarantee.

**Radu's open decision:** which fields of the approved content
participate in (b)'s fingerprint, with the same "faithfully derived
from" (allowed -- e.g. `materialize_variants()`'s eager expansion of
the proposal's raw exit list into the full variant set, SS106-109) vs.
"substituted" (forbidden) distinction needed for exits/horizons as for
every other field. This also interacts with the vocabulary-recheck gap
(the `UNAPPROVED_RSI` reproduction) -- (b)'s fingerprint check does not
by itself re-run the Discovery-vocabulary check; that needs its own
explicit re-validation of `entry_definition` at the gate, separate from
content-fingerprint equality.

---

## 2. Top Finding 15 (GPT-G2) -- variant completeness and exit-field semantics

**Problem restated:** two separate gaps. (i) `validate_for_
preregistration()` only checks that the declared `variant_ids` set
equals the supplied-variants id set (both caller-controlled) -- it
never independently checks that every value in
`horizon_candidate_set.values` has its own materialized TIME_EXIT
variant. (ii) `horizon_reference_point`/`exit_execution_policy` are
plain `str` fields (commented "X only" but never runtime-checked), and
TIME_EXIT's `time_exit_bars` sign is never validated.

**Design options for (i), completeness:**

- Add an explicit check in `validate_for_preregistration()`:
  `{v.exit_hypothesis.time_exit_bars for v in variants if
  v.exit_hypothesis.exit_family == TIME_EXIT.value} ==
  set(hypothesis.horizon_candidate_set.values)`. Direct, closes the
  reproduced gap exactly. Open question: should this also forbid an
  EXTRA TIME_EXIT variant for a bars value NOT in
  `horizon_candidate_set.values` (symmetric completeness), or only
  require the subset direction demonstrated as missing?

**Design options for (ii), exit-field semantics:**

- Promote `horizon_reference_point`/`exit_execution_policy` from
  commented-convention `str` fields to validated values (either an enum
  constrained to the single current legal value, or an explicit
  equality check against the `HORIZON_REFERENCE_POINT`/
  `EXIT_EXECUTION_POLICY` constants inside `validate_for_
  preregistration()`, mirroring the STOP_MANAGED_INVALIDATION family's
  own `_check_stop_managed_invalidation_exit()` pattern). Add a sign/
  positivity check on `time_exit_bars` for TIME_EXIT specifically
  (currently only SIGNAL_INVALIDATION's `max_holding_bars` is checked
  for presence, not TIME_EXIT's own field for sign).

**Radu's open decision:** whether completeness should be symmetric
(exactly equal sets) or one-directional (superset allowed), and whether
promoting `horizon_reference_point`/`exit_execution_policy` to a real
enum is preferred over a direct equality check (enum is more future-
proof if a second legal value is ever introduced; direct check is
smaller and matches the existing STOP_MANAGED_INVALIDATION precedent).

---

## 3. Top Finding 16 (GPT-G3) -- gate atomicity

**Problem restated:** `preregister_hypothesis()` calls
`registry._force_register(frozen)` BEFORE registering any variant; if a
subsequent `registry.register_variant()` raises (a conflicting
`variant_tag` under an already-used id), the hypothesis is left
PREREGISTERED in the registry with no rollback.

**Required invariant, stated explicitly (GPT's correction, relayed by
Radu):** on any failure inside `preregister_hypothesis()`, the ENTIRE
registry must be in exactly the state it was in BEFORE the call --
not merely "the hypothesis is removed." This is stricter than it
first looks, for two reasons a rollback-only design must not skip:

1. **Variants already written before the conflict.** If the variant
   batch has more than one entry and the SECOND one conflicts, the
   FIRST was already successfully written by `register_variant()`
   before the failure -- a correct remedy must undo that write too,
   not just the hypothesis.
2. **A pre-existing record under the same id.** `_force_register()`
   can legitimately overwrite an EXISTING non-PREREGISTERED record
   (e.g. a prior DRAFT with the same `definition_hash`) with the new
   PREREGISTERED one. If a later `register_variant()` call then fails,
   rollback must RESTORE that original DRAFT object, not delete the
   entry outright -- deleting would erase a pre-existing record the
   call had no business removing, a different and equally real bug.

**Design options, re-evaluated against that invariant:**

- **(a) Validate everything BEFORE writing anything -- the right
  general direction, but the dry run must cover both failure modes
  above, not just the originally-reproduced one.** Before any write:
  for the hypothesis itself, check `_force_register()`'s own
  preconditions (definition_hash match if `existing` is not None;
  not already a DIFFERENT-content PREREGISTERED record) without
  performing the write; for EVERY variant in the batch, check
  `register_variant()`'s own precondition (id absent, or present with
  IDENTICAL content) against BOTH the registry's current state AND the
  other variants already checked earlier in this same batch (so two
  variants in the SAME call that would conflict with each other are
  also caught, not only ones conflicting with something already in the
  registry). Only once every check in the batch passes does the
  function perform the actual writes. Because every precondition was
  already verified, the actual writes are then guaranteed not to raise
  -- this guarantee depends on the dry run covering BOTH failure modes
  above; a dry run that only checks "is the id free" (as a naive first
  cut might) would still miss the pre-existing-DRAFT-record case.
- **(b) True rollback, meeting the invariant.** Capture the registry's
  prior state for every id about to be touched (the hypothesis's own
  prior record if any, and each variant's prior record if any) before
  writing, and on any failure restore each one to its captured prior
  value (which may be "did not exist," "existed as DRAFT," or
  "existed as an identical PREREGISTERED record already") rather than
  simply deleting. More code than (a), and still reaches into the
  registry's internals (or needs a registry-level snapshot/restore
  method) to capture and replay prior state correctly.
- **(c) Make the registry itself transactional** (a `with
  registry.transaction():` context that stages writes and only commits
  them together, naturally satisfying the invariant by construction).
  Most general, but a bigger structural change than this specific bug
  needs -- probably over-engineering unless other atomicity gaps are
  expected elsewhere too.

**Radu's open decision:** (a), done correctly against BOTH failure
modes above, is the minimal fix; (b)/(c) are listed for completeness
and would also need to satisfy the same invariant. This finding is
scoped to the in-memory `HypothesisRegistry` only -- `JsonlAuditLog`'s
own atomicity (one record per preregistration, PATCH #004-B finding
#4) is separate and not affected either way.

---

## 4. Top Finding 17 (GPT-G4) -- close the public `register()` bypass

**Problem restated:** `register()`'s guard against a first-time
PREREGISTERED insert only fires when `existing is None`. A caller that
first legitimately `register()`-s a HANDOFF_TO_BACKTEST (or DRAFT/
REVIEWED/REJECTED) record for an id, then `register()`-s the SAME id
again with status PREREGISTERED, is not blocked -- `existing is not
None`, and `_force_register()`'s own immutability check only fires when
`existing.status == PREREGISTERED`, which it isn't yet at that point.

**Design options:**

- **(a) Widen the guard to cover every status-to-PREREGISTERED
  transition, not just the from-nothing case.** Change `register()`'s
  check from `existing is None and hyp.status == PREREGISTERED` to
  `hyp.status == PREREGISTERED and (existing is None or existing.status
  != PREREGISTERED)` -- i.e. refuse ANY transition into PREREGISTERED
  via the public API, regardless of what the prior status was,
  reserving that transition exclusively for `_force_register()` as
  called by `preregister_hypothesis()`. This directly closes the
  reproduced path with a small, localized change, and matches the
  module's own stated intent ("`register()` remains available for
  DRAFT/REVIEWED/REJECTED/HANDOFF_TO_BACKTEST records" -- i.e. never
  for producing a NEW PREREGISTERED state, from any prior status).
- **(b) Track gate provenance explicitly.** Add an internal
  (non-serialized or audit-only) marker on `HypothesisRegistry`
  recording which hypothesis_ids were produced via
  `preregister_hypothesis()`, and have `register()` refuse a
  PREREGISTERED record whose id is not in that set, regardless of its
  prior status. More explicit about WHY the record is trusted, but
  redundant with (a) once (a) exists -- (a) already makes "reached
  PREREGISTERED outside the gate" structurally impossible, so a
  separate provenance marker would only add value if some other path
  to PREREGISTERED is later discovered that (a) doesn't cover.

**Radu's open decision:** (a) is the minimal, directly-targeted fix;
(b) is a defense-in-depth addition if a broader audit of ALL paths into
PREREGISTERED is wanted. Recommend (a) alone unless Radu wants the
stronger provenance-tracking guarantee too.

---

## 5. Top Finding 18 (GPT-G5) -- preserve stability-bin results in `EvidencePacket`

**Problem restated:** §39's minimum-content list names "stability
bins" as its own top-level item (distinct from §57's separate
"stability availability," a Research Queue filter criterion -- the
spec text treats these as two different things). The current
`EvidencePacket` carries only `primary_has_stability_bins: bool`; no
bin values (mean/median/positive_rate per bin) exist anywhere on the
packet.

**Design options:**

- **(a) Add a compact `primary_stability_summary` field** carrying the
  PRIMARY horizon's own stability bins (the same `primary_*` reference-
  horizon-only convention already used for every other field on the
  packet) as a small tuple of (bin_label, mean, median, positive_rate,
  valid_n) -- analogous to `DecayPoint` but for stability bins. Keeps
  the packet's existing "flat, compact, one reference horizon" design
  philosophy, and keeps the token-budget target (§40, ~1-3KB) in view
  since it's a short tuple, not the full `EvidenceProfile.stability`
  structure.
- **(b) Add the full `stability` tuple as on `EvidenceProfile`
  itself** (every bin, with every field `StabilityBinResult` carries).
  More complete, but breaks the packet's own "flat/primitive fields on
  purpose" design note and risks exceeding the token-budget target if a
  signature has many stability bins -- needs a token-budget check
  before deciding (see Finding 8/Top Finding 8, the untested size
  target, which this would make more urgent to actually measure).

**Radu's open decision:** (a) keeps the packet's own documented
design philosophy and budget target; (b) is more complete but needs
the token-size question answered first (currently untested either way,
per Finding 8). Recommend (a) as the one consistent with the packet's
existing design unless Radu wants full per-bin granularity for a reason
not yet stated.

---

## 6. Top Finding 19 (GPT-G6) -- config integrity and freeze for the Research Queue

**Problem restated:** the same category of gap as Finding 11
(`hypothesis_config_version` never cross-checked against the config
dict actually used), now demonstrated specifically for
`build_research_queue()`'s `eligibility_config_version`.
`HypothesisConfig.config_version` is a hash of the raw file TEXT,
computed once at load time; `HypothesisConfig.data` is a plain mutable
dict, so nothing stops its nested values from diverging from what
`config_version` claims to describe.

**Why "recompute a new hash and stamp it" does not by itself prove
freeze (GPT's correction, relayed by Radu):** a hash recomputed from
whatever `data` currently holds correctly IDENTIFIES that content, but
identifying current content is not the same claim as proving it is
THE CONFIGURATION FROZEN BEFORE EXECUTION STARTED -- a freshly
recomputed hash would happily and silently validate a config that was
mutated five minutes ago, just as readily as the untouched original.
A correct design needs four distinct steps, kept separate rather than
collapsed into one recompute-and-stamp operation:

1. **Identify** the content actually in hand right now (a hash of its
   canonical form).
2. **Compare** that identification against an EXPECTED version --
   one established and pinned BEFORE the operation (preregistration
   run, queue run) began, not derived from the same live object being
   checked.
3. **Reject** on any mismatch between (1) and (2), rather than silently
   accepting and re-stamping whatever is currently there.
4. **Pin** that same snapshot for the full duration of the operation,
   so a mutation occurring mid-run (between the gate's own check and
   the queue's, for instance) cannot slip through either side purely
   because each side recomputed its own fresh hash independently.

**Design options, built around that four-step structure:**

- **(a) Canonical-content hashing used for steps 1-3, with an explicit
  pinned snapshot for step 4.** At the start of a preregistration
  session or a Research Queue run, take ONE canonical-content hash of
  `HypothesisConfig.data` and treat that single value as the pinned
  "expected version" for every check performed during that run (both
  the gate's `hypothesis_config_version` comparison and the queue's
  `eligibility_config_version` stamp read from the SAME pinned value,
  not from independent fresh recomputes each time). Any config object
  handed to a check mid-run is hashed again and compared against that
  one pinned value, rejecting on mismatch rather than accepting and
  re-stamping. **This is a versioning-SEMANTICS change, flagged
  explicitly, not merely a bug fix:** today's `config_version` is a
  hash of the raw YAML file TEXT; canonical-content hashing of `data`
  is a DIFFERENT function over different input and will produce
  DIFFERENT version strings for the same logical config than today's
  scheme does. Every historical `hypothesis_config_version` already
  recorded in a frozen `HypothesisComplexitySnapshot` was computed
  under the OLD scheme -- switching schemes must not reinterpret those
  existing ids as if they'd always meant canonical-content hashes; this
  needs its own explicit versioning rule (e.g. a scheme tag alongside
  the hash, or treating the switch as a one-time config-version epoch
  boundary), not a silent redefinition.
- **(b) Make `HypothesisConfig.data` immutable at load** (e.g.
  recursive `types.MappingProxyType`, or a frozen dataclass/namedtuple
  structure) -- addresses in-process mutation after `load_config()`,
  but **does not by itself cover the full problem**: it does nothing
  for a `HypothesisConfig` constructed directly (bypassing
  `load_config()`) with a `data`/`config_version` pair that is
  mismatched from the start -- immutability only prevents CHANGE after
  construction, not construction with already-inconsistent fields.
  Step 1-3's identify/compare/reject still has to run at the point of
  use regardless of whether (b) is also adopted.
- **(c) Both, with (a) doing the actual enforcement work.** (b) as a
  defense against accidental in-process mutation; (a)'s pinned-
  snapshot identify/compare/reject as the mechanism that actually
  closes both Finding 11 and this finding, since (a) alone already
  covers the hand-built-mismatched-object case that (b) cannot.

**Radu's open decision:** whether to adopt the versioning-semantics
change in (a) (canonical-content hashing, with an explicit epoch/
scheme-tag rule for existing historical ids) now, jointly with Finding
11's own remediation (not yet separately proposed), rather than fixing
the Research Queue's instance in isolation -- they share the same root
cause and the same versioning-semantics question.

---

## 7. Top Finding 20 (P004C) -- persistence type-registry gap for `STOP_MANAGED_INVALIDATION`

**Problem restated:** `registry/persistence.py`'s `_TYPE_REGISTRY`
never lists `StopLossRule`/`PartialProfitRule`. `to_jsonable()`
serializes them via generic dataclass recursion (nothing special-cases
missing types on the way OUT); `from_jsonable()` raises `KeyError` on
the way back IN, since it looks up the registry by the tagged type
name.

**Design option for the demonstrated omission itself (no real design
ambiguity here -- a one-line registry omission from an additive patch,
not a design choice):**

- Add `StopLossRule, PartialProfitRule` to the `_TYPE_REGISTRY` tuple in
  `registry/persistence.py`. This directly closes the exact gap
  demonstrated (the minimal round-trip probe's `KeyError`). **Scope
  correction (GPT's review, relayed by Radu): this closes the minimal
  probe, not necessarily the whole flow** -- whether the full
  preregistration-then-restart-then-replay path for a complete
  STOP_MANAGED_INVALIDATION family (hypothesis + variant + nested
  `StopLossRule`/`PartialProfitRule`, written via `JsonlAuditLog.
  append()` and reconstructed via `replay()`) works end-to-end once
  this registration is added is NOT asserted here and remains to be
  verified at implementation time, not claimed now as already settled
  by this one-line change.

**Reported and proposed separately from the historical acceptance
record, stated precisely rather than abbreviated:** the Spec #005 Exit
Amendment v1.0 document's TEXT was accepted (commit `2fa5575`);
PATCH #004-C's own IMPLEMENTATION verdict remains separate and
pending, per `docs/evidence_004c_verdict_status.md` and
`docs/contract_index.md`'s own Spec #004 "Flag" row. This finding does
not reopen either of those; it flags a persistence-layer regression in
code added after #004's original audit scope, needing its own
approval step.

---

## Required regression coverage (planned, not written -- design stage only)

Whichever design option is chosen per finding, the regression suite
added at implementation time must include AT LEAST the following
scenarios -- listed here so the remediation design is evaluated against
a concrete verification plan, not left to be decided ad hoc once
implementation starts. None of these tests exist yet; none are written
by this document.

- **Finding 14 (GPT-G1):** content changed under the SAME approved id,
  including the case where `proposal` and `draft` are mutated
  TOGETHER under that id (not just a draft diverging from an
  unmodified proposal) -- the chosen design must reject this, since
  that is exactly the scenario Finding 14's own discussion above shows
  a naive draft-vs-proposal comparison would miss.
- **Finding 15 (GPT-G2):** both directions of incompleteness (missing
  AND extra TIME_EXIT variants relative to `horizon_candidate_set.
  values`) and at least one invalid exit-semantics case per field
  (`time_exit_bars` sign, `horizon_reference_point`,
  `exit_execution_policy`).
- **Finding 16 (GPT-G3):** a conflict arising AFTER at least one
  variant in the same batch has already been successfully written,
  and a conflict where the hypothesis id pre-existed as a DRAFT before
  the call -- both must leave the registry in the exact pre-call
  state, per the invariant in section 3 above (not just "hypothesis
  absent").
- **Finding 17 (GPT-G4):** every public-API transition path into
  PREREGISTERED (not only the exact HANDOFF_TO_BACKTEST-then-
  PREREGISTERED sequence reproduced) is rejected, AND the legitimate
  existing use of `register()` -- idempotently re-registering an
  ALREADY-PREREGISTERED record with identical content (e.g. audit-log
  replay) -- continues to succeed unchanged.
- **Finding 18 (GPT-G5):** stability-bin values placed into the
  `EvidencePacket` (whichever field design is chosen) are asserted to
  actually reach it with correct values, not merely that the packet's
  presence flag is set.
- **Finding 19 (GPT-G6):** a config mutation occurring between when a
  version was pinned and when a check runs is REJECTED against that
  pinned snapshot, not silently accepted and re-stamped.
- **Finding 20 (P004C):** both nested types round-trip
  (`StopLossRule` AND `PartialProfitRule`, not just one), AND a full
  STOP_MANAGED_INVALIDATION hypothesis+variant family survives a
  complete persist-then-reload cycle through `JsonlAuditLog.append()`/
  `replay()`, not only the minimal direct `to_jsonable`/`from_jsonable`
  probe already reproduced.

---

## Summary table

| Finding | Root cause | Recommended direction (not yet authorized) | Shared with |
|---|---|---|---|
| 14 (GPT-G1) | approval checks identity, not content | (a) field equality, or (b) fingerprint the approved proposal | -- |
| 15 (GPT-G2) | completeness/semantics not re-checked at gate | explicit per-horizon TIME_EXIT check + exit-field validation | -- |
| 16 (GPT-G3) | write-before-validate ordering | (a) validate all variants before any write | -- |
| 17 (GPT-G4) | `register()` guard scoped to "existing is None" only | (a) widen guard to any-status-to-PREREGISTERED | -- |
| 18 (GPT-G5) | packet keeps presence flag, not values | (a) compact per-bin summary field, respecting token budget | Finding 8 (untested budget) |
| 19 (GPT-G6) | version frozen at load, data dict mutable | (a) recompute version from live content | Finding 11 (same root cause) |
| 20 (P004C) | registry omission in an additive patch | add the two missing types to `_TYPE_REGISTRY` | -- |

**None of the above is authorized for implementation.** This document
proposes designs for Radu to evaluate; the next stage (implementation/
acceptance) begins only when and if he authorizes it, per-finding or as
a batch, following the same three-stage discipline already established
for Spec #003's own remediation design.
