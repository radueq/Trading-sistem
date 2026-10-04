# Spec #004 -- Remediation Design Proposal (2026-10-04)

**Status: DESIGN ONLY. Not authorized for implementation.** Covers
Top Findings 14-19 (GPT's own G1-G6, GPT Review #004, relayed by Radu,
against commit `d272cb8`) plus Top Finding 20 (the separate PATCH
#004-C persistence finding). No code or test is changed by this
document. **Scope note, stated precisely (not as an instruction from
Radu):** this document covers only these six findings + P004C --
Claude's own choice of scope for this round, given the volume of
material, not something Radu's relayed message required excluding.
Claude's own prior Findings 1-13 (the Claude-solo round) are not
covered here -- not because they lack a GPT round: **correction (GPT's
observation, relayed by Radu): GPT's review individually addressed
each of Findings 1-13** in its own reconciliation table (confirming
some, narrowing others), it just was not the full remediation-design
treatment this document gives Findings 14-20. **Not all of them would
need a functional remediation design even if covered** -- several are
TEST-COVERAGE
GAPS (e.g. Finding 7's `HypothesisUniverse` test coverage, Finding 8's
untested token-budget target), FUTURE/PROCEDURAL requirements code
cannot express (Finding 4, the statistical-skeptic checklist), or open
CONTRACTUAL questions for Radu's own reading (Finding 3's per-condition
provenance granularity, Finding 6's `FutureResearchNote` dead-code
status) rather than demonstrated code defects calling for a fix. Any
future remediation-design round for Findings 1-13 should sort them
into these categories first, the way this section does for the six
GPT findings below, rather than assume every one needs a design option.

**Current status of the three stages, precisely, as of commit
`35cefc3`:** (1) findings -- Claude has independently CONFIRMED each
of the six findings + P004C, by code reading and by re-running GPT's
own probe script against this repository (see the matrix's GPT-review
status block). **GPT has since closed findings reconciliation for
these six findings + P004C, within this review's own declared (not
full-row) scope** -- `docs/contract_index.md` reflects that closure;
it does not certify every one of the matrix's 111 rows, and the
remaining open contractual questions (not only within Findings 1-13
above, but also e.g. the FORMAL_DEVELOPMENT admission-policy reading
surfaced by Finding 1) are unaffected by it; (2) remediation DESIGN --
this document, several options listed per finding, none chosen, and
explicitly NOT a precondition for (1)'s status: finishing or not
finishing this design has no bearing on whether the findings
themselves are reconciled, and (1)'s closure already happened without
waiting on (2); (3) implementation/acceptance -- not started, not
authorized.

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
  compare at the gate -- but the fingerprint and the comparison must
  cover the WHOLE chain, not just "human decision vs. draft."** The
  object that gets approved (the raw `HypothesisProposal`), the object
  `proposal_validation` certified, the `StrategyHypothesis` draft, and
  its materialized `StrategyVariant`s are four DIFFERENT shapes:
  `hypothesis_fingerprint()` hashes `(parent_signature_id, direction,
  entry_definition, entry_execution_policy, horizon_candidate_set,
  evidence_provenance, strategy_config_version)` -- fields that do not
  exist in that same form on the raw proposal (e.g. `evidence_
  provenance`/`strategy_config_version` are not proposal fields at
  all). A hash of the raw proposal and the draft's own
  `definition_hash` are NOT directly comparable values -- treating
  them as if they were is itself a design bug, not just an
  implementation detail. The binding needs an explicit, verifiable
  transformation at each step, not a single opaque fingerprint
  assumed to survive unchanged end to end:
  1. **At approval time:** freeze a fingerprint of the proposal content
     actually reviewed (direction, entry definition, execution policy,
     horizon candidates, raw exit hypotheses) onto the human decision
     record itself (`HumanDecision`/`ConsensusRecord` gains an
     `approved_proposal_fingerprint` field, written once).
  2. **At validation:** `proposal_validation` (already produced from
     that same proposal by `validate_proposal()`) must itself record
     which proposal content it validated -- e.g. carrying the SAME
     `approved_proposal_fingerprint`-shaped value computed from the
     proposal it actually checked -- so "validated" and "approved" can
     be shown to be about the identical content, not merely the same
     `proposal_id`.
  3. **At the gate:** define an explicit, documented transformation
     `proposal_fields -> expected_draft_fields` (the "faithfully
     derived from" mapping -- e.g. `proposal.direction ->
     draft.direction` unchanged, `proposal.exit_hypotheses ->` the set
     of exit hypotheses `materialize_variants()` is allowed to
     eagerly expand them into). `preregister_hypothesis()` applies
     this transformation to the proposal content named in step 1/2's
     fingerprint, recomputes `hypothesis_fingerprint()`/
     `variant_fingerprint()` from the RESULT of that transformation,
     and compares against the draft's/variants' own claimed hash --
     the same recomputation `validate_for_preregistration()` already
     does for content-addressing (PATCH #004-B finding #2), now also
     checked against the approved content's transformed expectation,
     not only against the draft's own fields in isolation.
  This closes the gap across the full chain (proposal -> validation ->
  draft -> variants), not just between the human decision and the
  draft -- GPT's correction is specifically that stopping at "human
  decision vs. draft" leaves the validation-result link and the
  proposal-to-draft transformation itself unverified. Open question:
  the exact transformation in step 3 for every field, not only
  exits/horizons.
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

- **(a) Validate everything BEFORE writing anything -- a SCOPED
  guarantee, stated precisely (GPT's correction, relayed by Radu): it
  eliminates deterministic, anticipated conflicts, not every possible
  failure.** Before any write: for the hypothesis itself, check
  `_force_register()`'s own preconditions (definition_hash match if
  `existing` is not None; not already a DIFFERENT-content
  PREREGISTERED record) without performing the write; for EVERY
  variant in the batch, check `register_variant()`'s own precondition
  (id absent, or present with IDENTICAL content) against BOTH the
  registry's current state AND the other variants already checked
  earlier in this same batch. **What this actually guarantees:**
  given (i) the registry's state does not change between the dry run
  and the subsequent writes (true for a single synchronous,
  non-concurrent call with no other actor touching the registry
  mid-call, which is this module's current execution model), and (ii)
  the dry run's checks are the complete set of preconditions
  `_force_register()`/`register_variant()` actually enforce, THEN the
  writes that follow cannot raise from those specific, anticipated
  causes. **What this does NOT guarantee on its own:** it does not by
  itself prove the atomicity invariant holds against an exception from
  a cause the dry run did not anticipate (a bug elsewhere in the write
  path, a future code change adding a new failure mode to
  `register_variant()` without updating the dry run to match, or a
  violation of precondition (i) if this module's concurrency model
  ever changes). Whatever option is chosen must therefore either (a-i)
  prove the dry run's precondition set stays in lock-step with the
  actual write-path preconditions (e.g. by deriving both from one
  shared check function, not two independently-maintained copies), or
  (a-ii) be paired with (b)/(c) below as a genuine fallback for the
  residual case, not left as an implicit, unstated assumption.
- **(b) True rollback -- a wider guarantee than (a), but its own scope
  must still be stated explicitly, not assumed absolute (GPT's
  correction, relayed by Radu: naming a mechanism "rollback" does not
  by itself prove an unconditional guarantee either).** Capture the
  registry's prior state for every id about to be touched (the
  hypothesis's own prior record if any, and each variant's prior
  record if any) before writing, and on a failure caught by this
  mechanism's own `try`/`except` -- covering, at minimum, every
  exception type `_force_register()`/`register_variant()` are actually
  documented to raise today -- restore each one to its captured prior
  value (which may be "did not exist," "existed as DRAFT," or "existed
  as an identical PREREGISTERED record already") rather than simply
  deleting. This widens coverage well past (a)'s anticipated-conflicts-
  only scope, but a `try`/`except` still only catches what it names and
  what actually executes inside its block -- it says nothing about a
  failure outside that block (e.g. the process itself being killed
  mid-write) or about an exception type nobody anticipated adding a
  handler for. Whatever this mechanism's actual tested exception
  coverage turns out to be must be stated as a bounded list in its own
  right, verified by the regression coverage below, not asserted as
  "any failure" by virtue of the word "rollback."
- **(c) Make the registry itself transactional** (a `with
  registry.transaction():` context that stages writes and only commits
  them together) -- the same caveat as (b) applies: this needs its own
  explicit statement of which failure modes the transaction boundary
  actually catches and reverts, verified by test, not assumed complete
  because the mechanism is named "transactional." Most general of the
  three, but a bigger structural change than this specific bug needs --
  probably over-engineering unless other atomicity gaps are expected
  elsewhere too.

**Radu's open decision:** how wide the in-memory atomicity guarantee
for this module needs to be -- (a)'s narrower, cheaper scoped guarantee
(deterministic, anticipated conflicts only, under the current
non-concurrent execution model) vs. (b)/(c)'s wider but still NOT
unconditional coverage (bounded by whatever exception types their own
`try`/`except`/transaction boundary actually catches, to be stated and
tested explicitly, not assumed). Any choice to narrow the originally-
stated invariant ("entire registry restored on any failure") to a
bounded, documented set of covered failure modes must be recorded as
an explicit decision at implementation time, not arrived at implicitly
by whichever option gets picked. This finding is scoped to the
in-memory `HypothesisRegistry` only -- `JsonlAuditLog`'s own atomicity
(one record per preregistration, PATCH #004-B finding #4) is separate
and not affected either way.

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

**Where step 2's "expected version" actually comes from -- still an
open design point, not yet a complete answer (GPT's follow-up
correction, relayed by Radu, on an earlier draft of this section):**
step 1's identify-the-current-content hash must NOT also be the
source of step 2's expected value for the SAME object under test --
that would be circular (hashing a config and comparing it against "a
hash of itself" proves nothing, and would happily freeze an
already-tampered dict as if it were the correct baseline, exactly the
Finding 11 reproduction's own tampered-dict scenario). An earlier
version of this section proposed sourcing step 2's expected value from
a fresh `load_config()` read of `hypothesis.yaml` taken when the
operation begins. **That by itself is not yet the complete answer,
only a candidate building block:** "the file currently on disk" is not
automatically the same thing as "the configuration frozen for THIS
run" -- the file on disk can itself be edited between when a run's
intended configuration was decided and when the run actually executes,
so re-reading it fresh at run-start only re-introduces the same
identify-vs-expected gap one level up, now against the filesystem
instead of against an in-memory dict. What step 2 actually needs is a
version EXPLICITLY REGISTERED/declared for this specific operation
(e.g. recorded alongside the run's own identity, the way
`EvaluationRunRegistry`/`run_registry` fixes other provenance fields
for a run in Spec #003's own design) -- a fresh disk read may be how
that registered value gets ESTABLISHED (one reasonable source for it),
but the registered value itself, not "whatever load_config() returns
right now," is what step 2 must compare against. **Three distinct
values must be checked for concordance, not two:** (i) the actual
content in hand (step 1's hash), (ii) the `config_version` the object
under test itself CLAIMS (its own declared label), and (iii) the
version registered as expected for this operation. All three must
agree -- not only (i) vs (iii). This explicitly covers a case the
two-way comparison alone would miss: **content that is actually
correct, carrying a WRONG `config_version` label** (a labeling/
bookkeeping bug, distinct from Finding 11's data-tampering scenario) --
(i) would match (iii) correctly, but (ii) would disagree with both,
and that mismatch must also be rejected, not waved through because the
underlying data happened to be fine. Finally: **the operation must
actually USE the verified, pinned snapshot from step 4 for its own
subsequent work, not continue reading from the original mutable
object after verification passes** -- a check-then-still-read-the-
same-mutable-dict pattern leaves a window where the object could be
mutated again between the check and its use; pinning (step 4) must
mean switching to an immutable copy taken at verification time, not
merely remembering that a check once succeeded. This also covers, as
before, **the hand-built-object case**: a `HypothesisConfig` (or a
bare dict) constructed directly with a `data`/`config_version` pair
that never came from `load_config()` at all is still caught, because
step 2/(ii)-vs-(iii)'s comparison is against the registered reference,
regardless of what the object under test claims about its own version.

**Design options, built around that four-step structure -- proposals
for the design stage, none settled:**

- **(a) Canonical-content hashing for step 1, a run-registered expected
  value for step 2 (one candidate source: a fresh `load_config()` read
  taken when that registration happens, not re-read again later), the
  three-way (i)/(ii)/(iii) concordance check for step 3, and switching
  to the pinned snapshot itself for all subsequent work in step 4 --
  not continuing to read the original mutable object.** Both the
  gate's `hypothesis_config_version` comparison and the queue's
  `eligibility_config_version` stamp read from the SAME pinned,
  registered value, not from independent fresh recomputes of whatever
  object each one happens to receive. **This is a
  versioning-SEMANTICS change, flagged explicitly, not merely a bug
  fix:** today's `config_version` is a hash of the raw YAML file TEXT;
  canonical-content hashing of `data` is a DIFFERENT function over
  different input and will produce DIFFERENT version strings for the
  same logical config than today's scheme does. Every historical
  `hypothesis_config_version` already recorded in a frozen
  `HypothesisComplexitySnapshot` was computed under the OLD scheme --
  switching schemes must not reinterpret those existing ids as if
  they'd always meant canonical-content hashes; this needs its own
  explicit versioning rule (e.g. a scheme tag alongside the hash, or
  treating the switch as a one-time config-version epoch boundary),
  not a silent redefinition.
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
  pinned snapshot, not silently accepted and re-stamped; the correct-
  content-wrong-`config_version`-label case (the three-way concordance
  check, not just content-vs-pinned-snapshot) is rejected too; and a
  check that passes actually operates on the pinned snapshot
  afterward, not on the original mutable object re-read a second time.
- **Finding 20 (P004C):** both nested types round-trip
  (`StopLossRule` AND `PartialProfitRule`, not just one), AND a full
  STOP_MANAGED_INVALIDATION hypothesis+variant family survives a
  complete persist-then-reload cycle through `JsonlAuditLog.append()`/
  `replay()`, not only the minimal direct `to_jsonable`/`from_jsonable`
  probe already reproduced.

---

## Summary table

| Finding | Root cause | Direction under discussion (not yet authorized, none chosen) | Shared with |
|---|---|---|---|
| 14 (GPT-G1) | approval checks identity, not content; (a)-style field equality against the SAME call's `proposal` argument is insufficient, withdrawn | (b): fingerprint frozen onto the human decision record at approval time, with an explicit, verifiable transformation chain from approved proposal -> validation result -> draft -> materialized variants (not raw-proposal-hash vs. final-object-hash treated as directly comparable) | -- |
| 15 (GPT-G2) | completeness/semantics not re-checked at gate | explicit per-horizon TIME_EXIT check + exit-field validation | -- |
| 16 (GPT-G3) | write-before-validate ordering | pre-validation of deterministic conflicts (narrower, cheaper), or rollback/transaction with its own tested exception coverage stated explicitly (wider, but not unconditional either -- see below) | -- |
| 17 (GPT-G4) | `register()` guard scoped to "existing is None" only | (a) widen guard to any-status-to-PREREGISTERED | -- |
| 18 (GPT-G5) | packet keeps presence flag, not values | (a) compact per-bin summary field, respecting token budget | Finding 8 (untested budget) |
| 19 (GPT-G6) | version frozen at load, data dict mutable; recomputing from `data` at the START of an operation can freeze already-divergent content, withdrawn as the whole answer | identify content / compare a three-way concordance (actual content, the object's own claimed `config_version`, and the version registered for this operation) / reject on any mismatch / use the pinned snapshot itself afterward, not the original mutable object -- a fresh `load_config()` read is proposed as one candidate source for the registered value, not yet settled | Finding 11 (same root cause) |
| 20 (P004C) | registry omission in an additive patch | add the two missing types to `_TYPE_REGISTRY`; full persist/reload for the complete family still unverified | -- |

**None of the above is authorized for implementation.** This document
proposes designs for Radu to evaluate; the next stage (implementation/
acceptance) begins only when and if he authorizes it, per-finding or as
a batch, following the same three-stage discipline already established
for Spec #003's own remediation design.
