# Spec #004 -- Remediation Design Proposal (2026-10-04)

**Status: DESIGN ONLY. Not authorized for implementation.** Covers
Top Findings 14-19 (GPT's own G1-G6, GPT Review #004, relayed by Radu,
against commit `d272cb8`) plus Top Finding 20 (the separate PATCH
#004-C persistence finding). No code or test is changed by this
document. Findings reconciliation for these six findings is recorded in
`docs/audit_spec004_requirement_code_test.md`'s GPT-review status
block; this document proposes remedies for Radu to evaluate, nothing
here is pre-approved. Reconciliation of Claude's own prior Findings
1-13 (the Claude-solo round) is also recorded there, not repeated here
-- those findings do not yet have a remediation proposal of their own;
this document covers only the six GPT findings + P004C, per Radu's own
explicit instruction this round.

Three stages, kept separate as throughout this project: (1) findings
reconciliation -- done for these six, recorded in the matrix; (2)
remediation DESIGN -- this document, still open, several options listed
per finding, none chosen; (3) implementation/acceptance -- not started,
not authorized.

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

**Design options:**

- **(a) Direct field-by-field equality check at the gate.**
  `preregister_hypothesis()` additionally compares
  `draft.direction`/`draft.entry_definition`/
  `draft.entry_execution_policy`/`draft.horizon_candidate_set` against
  the corresponding fields on `proposal` (after `normalize_proposal()`),
  raising if any differ. Simple, directly closes the demonstrated gap.
  Open question: does the draft's exit-hypothesis selection also need
  equality-checking against `proposal.exit_hypotheses`, given
  `materialize_variants()` legitimately expands the proposal's raw exit
  list into the full eagerly-materialized variant set (SS106-109)? A
  naive equality check would break the normal, intended expansion. This
  needs a precise definition of "the same content" that distinguishes
  "faithfully derived from" (allowed) from "substituted" (forbidden).
- **(b) Content-fingerprint the APPROVED proposal itself, and recompute
  it at the gate.** Add a fingerprint field to `HypothesisProposal`
  (or compute one on demand from its fields) and freeze it into
  `consensus`/`HumanDecision` at approval time -- "radu approved
  fingerprint X," not just "radu approved proposal_id prop_1." At the
  gate, recompute the draft's own fingerprint-of-origin (the subset of
  its fields that must trace back to the proposal) and compare against
  the frozen approved fingerprint. More robust than (a) since it is
  itself content-addressed, consistent with the rest of #004's design
  philosophy, but requires deciding exactly which fields participate
  (same open question as (a)).
- **(c) Freeze the proposal object itself inside the draft's
  provenance** (not just its id), and derive the draft deterministically
  FROM that frozen proposal via a single trusted construction function,
  removing the possibility of hand-building a draft with diverging
  fields at all. Strongest guarantee, but a bigger structural change --
  moves "which fields must match" from a runtime check into the type
  system/construction path itself.

**Radu's open decision:** which fields of a proposal are allowed to be
"faithfully derived into" vs. must be "identical to" the frozen draft,
and which of (a)/(b)/(c) fits #004's existing content-addressing
philosophy best. This also interacts with the vocabulary-recheck gap
below (the `UNAPPROVED_RSI` reproduction) -- any of (a)/(b)/(c) that
re-derives or re-compares `entry_definition` would incidentally need to
re-run the Discovery-vocabulary check too, not just equality.

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

**Design options:**

- **(a) Validate all variants' registerability BEFORE writing
  anything.** Add a dry-run check inside `preregister_hypothesis()`
  that, for each variant, verifies either (i) the id is not yet
  registered, or (ii) it is registered with IDENTICAL content --
  mirroring `register_variant()`'s own existing comparison logic --
  and only if ALL variants pass this dry run does the function proceed
  to `_force_register(frozen)` followed by the actual
  `register_variant()` calls (which would then be guaranteed not to
  raise, since the dry run already proved it). Minimal change, no new
  registry capability needed, keeps the existing in-memory
  `HypothesisRegistry` design.
- **(b) Add a rollback path.** Wrap the write sequence in a
  try/except that, on any `register_variant()` failure, removes the
  just-written hypothesis from `registry._hypotheses` before
  re-raising. Simpler to write than (a), but reaches into the
  registry's internal dict directly from outside (or needs a new
  `registry._rollback_hypothesis()` method), which is a less clean
  separation of concerns than validating before writing.
- **(c) Make the registry itself transactional** (a `with
  registry.transaction():` context that stages writes and only commits
  them together). Most general, but a bigger structural change than
  this specific bug needs -- probably over-engineering unless other
  atomicity gaps are expected elsewhere too.

**Radu's open decision:** (a) is the minimal fix consistent with the
existing design (recommended by elimination, not a default); (b)/(c)
are listed for completeness. This finding is scoped to the in-memory
`HypothesisRegistry` only -- `JsonlAuditLog`'s own atomicity (one
record per preregistration, PATCH #004-B finding #4) is separate and
not affected either way.

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

**Design options -- this is the SAME underlying gap as Finding 11, so a
shared remedy covering both is preferred over two separate ones:**

- **(a) Recompute the version from `data`'s actual current content at
  the point of use**, not from the original file text at load time:
  `config_version = hash(json.dumps(data, sort_keys=True))`, computed
  freshly wherever a version needs to be stamped (both at the gate for
  `hypothesis_config_version` and in `build_research_queue()` for
  `eligibility_config_version`), rather than carried as a frozen field
  from load time. Closes both Finding 11 and this finding with one
  mechanism: any mutation to `data` is immediately reflected, so a
  tampered/mutated config can no longer masquerade as the original.
- **(b) Make `HypothesisConfig.data` genuinely immutable** (freeze the
  nested dict into an immutable mapping, e.g. via
  `types.MappingProxyType` recursively, or convert to a frozen
  dataclass/namedtuple structure at load time), so the ORIGINAL
  load-time hash stays valid because the content literally cannot
  change afterward. Addresses the root cause (mutability) rather than
  recomputing around it, but is a larger structural change touching
  every call site that currently does `config.data["section"]["key"]`
  dict-style access.
- **(c) Both:** immutability (b) as the primary defense, with (a)'s
  recompute-and-compare kept as a defensive check at the two points
  that currently stamp a version (gate + queue), in case something
  outside this module's control still manages to hand in a divergent
  dict (e.g. a caller constructing a `HypothesisConfig` by hand rather
  than via `load_config()`).

**Radu's open decision:** (a) is the smaller fix and directly closes
both Finding 11 and this finding; (b) is more structural and prevents
the class of bug from recurring anywhere else `HypothesisConfig.data`
is passed around, at the cost of touching more call sites. Recommend
deciding this jointly with Finding 11's own remediation (not yet
separately proposed) rather than fixing the Research Queue's instance
in isolation, since they are the same root cause.

---

## 7. Top Finding 20 (P004C) -- persistence type-registry gap for `STOP_MANAGED_INVALIDATION`

**Problem restated:** `registry/persistence.py`'s `_TYPE_REGISTRY`
never lists `StopLossRule`/`PartialProfitRule`. `to_jsonable()`
serializes them via generic dataclass recursion (nothing special-cases
missing types on the way OUT); `from_jsonable()` raises `KeyError` on
the way back IN, since it looks up the registry by the tagged type
name.

**Design option (this one has no real design ambiguity -- it's a
one-line registry omission from an additive patch, not a design
choice):**

- Add `StopLossRule, PartialProfitRule` to the `_TYPE_REGISTRY` tuple in
  `registry/persistence.py`. That is the entire fix; `to_jsonable()`/
  `from_jsonable()`'s generic recursive logic needs no other change
  since it already handles any dataclass uniformly once its name is in
  the registry.

**Reported and proposed separately from PATCH #004-C's own historical
acceptance (commit `2fa5575`, the Spec #005 Exit Amendment v1.0
document) per GPT's and Radu's explicit instruction** -- that
acceptance covered the CONTRACT TEXT for the additive exit family, not
this serializer path, which was added later and never updated when
`StopLossRule`/`PartialProfitRule` were introduced. Fixing this needs
its own approval step, not a reopening of PATCH #004-C's acceptance.

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
