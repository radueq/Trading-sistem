# Joint Remediation Design -- Spec #003 + Spec #004 (2026-10-04)

**Status: DESIGN ONLY. Implementation NOT AUTHORIZED.** Written per
GPT's own recommendation (relayed by Radu, at commit `f83d146`): now
that both specs' findings reconciliation is CLOSED from GPT's side
(#003 at `8a0f152`, #004 at `35cefc3`/`f83d146`), produce the joint
remediation design the earlier sequencing instruction deferred until
both audits finished -- ordered by cross-module dependency, with
concrete recommended solutions (not just option lists) and a
consolidated regression checklist, for Radu's approval.

This document does not replace or restate
`docs/spec003_remediation_proposal_2026-10-04.md` or
`docs/spec004_remediation_proposal_2026-10-04.md` -- it cross-
references them for the full technical rationale behind each option,
and adds what neither one did alone: (a) an explicit cross-module
dependency check between the two specs' remaining fixes, (b) one
recommended, concrete answer per item wherever the existing analysis
actually supports picking one (clearly separated from the items that
remain genuinely Radu's own call), (c) a single build order, and (d) a
consolidated sign-off checklist. No code or test is changed by this
document.

---

## 1. Cross-module dependency check

**Question asked:** does fixing any #003 (Evaluation) finding require,
block, or change the design of any #004 (Hypothesis) fix, or vice
versa?

**Answer: the two fix sets are architecturally independent.**
Hypothesis (#004) consumes Evaluation's (#003) output only through
three already-frozen artifact types
(`EvaluationSignatureDefinition`/`EvidenceProfile`/
`EvaluationRunRegistry`), via `build_evidence_packet()`
(`hypothesis/evidence/packet.py`) -- confirmed in the #004 audit's own
cross-module dependency check (`docs/audit_spec004_requirement_code_
test.md`'s status block): `src/hypothesis/` never imports
`evaluation.engine`, only `evaluation.models.entities` (plain
dataclasses). Every #003 fix below (F1-F6, S1, S2, G1, G2) changes
either (i) which PIT data Evaluation reads/computes, or (ii) the
VALUES inside those already-existing dataclass fields -- none of them
changes the SHAPE of `EvaluationSignatureDefinition`/
`EvaluationRunRegistry` in a way `build_evidence_packet()` doesn't
already handle, except F6, which ADDS a new field
(`family_test_count`) to `BaselineComparison` that `EvidencePacket`
does not currently read at all (so #004 needs no change to pick it up
or ignore it either way). Every #004 fix below (Top Findings 14-20)
is scoped entirely inside `src/hypothesis/`'s own gate/registry/queue/
packet/persistence code -- none of them reads from or writes back into
`src/evaluation/`. **Conclusion: the two fix sets can be designed,
approved, and implemented in either order, or in parallel, with no
technical blocking dependency between them.**

**One conceptual (not technical) thread worth flagging together,
rather than deciding twice:** #003's F1 is about preventing Locked-OOS
price/knowledge-time leakage INTO Evaluation's own Development
computation. #004's Finding 1 (now DEMONSTRATED, see its matrix entry)
is about whether evidence admitted into a `StrategyHypothesis` must
itself have been computed under `FORMAL_DEVELOPMENT` discipline, and
whether that fact is preserved on the frozen record. These are
different mechanisms at different layers, but both ultimately protect
the same thing: that a strategy's hypothesis-formation path never
touches information from beyond the Development boundary. If Radu
wants a single stated principle spanning both specs ("development
discipline must be provable end-to-end, from PIT access through to a
frozen hypothesis"), this is the point to decide it -- not because one
fix depends on the other technically, but because deciding them
separately risks two different, uncoordinated answers to what is, at
bottom, one question. This document flags it; it does not answer it.

---

## 2. Recommended build order

Independent fix sets, ordered here for review/implementation
efficiency and risk, not because of a technical dependency (section 1
established there isn't one):

1. **#003 F1, part 1 (fetch bounding)** -- GPT's own stated top
   priority for #003; stops the single most serious leak (Locked-OOS
   price/knowledge-time reaching Development) with an already-settled
   mechanism (`effective_as_of = min(data_as_of, development_end)`).
2. **#003 F2a + F2b** -- cheap, deterministic entry-gate checks with no
   open design question; natural to do together since both sit at the
   same `run_evaluation()` entry point.
3. **#003 F6** -- additive field, no open design question.
4. **#003 F3, F4+F5** -- the two findings with genuinely open
   Radu-decisions (see section 3); grouped together since both concern
   the baseline-comparison statistics layer and a single sitting likely
   resolves both faster than two separate ones.
5. **#003 F1, part 2 (classification)** -- placed last among #003's
   items deliberately: it is explicitly unresolved design work (no
   working mechanism proposed yet), and resolving F4+F5's within-bin
   estimator choice first may inform the same kind of "what counts as
   a valid observation" thinking F1's classification mechanism also
   needs.
6. **#004 Top Finding 17 (GPT-G4, registry bypass)** -- the single
   highest-severity #004 item (a public API path that reaches
   PREREGISTERED with literally no approval, consensus, or gate
   involved at all) with a one-line, uncontested fix (widen
   `register()`'s guard).
7. **#004 Top Finding 20 (P004C)** -- one-line registry omission, no
   open design question, cheapest item on either list.
8. **#004 Top Finding 15 (GPT-G2, completeness/semantics)** -- no open
   design question once the per-horizon and per-field checks are
   specified.
9. **#004 Top Finding 16 (GPT-G3, atomicity)** -- has one open decision
   (section 3) but a clear minimal direction either way.
10. **#004 Top Finding 19 (GPT-G6) + the still-unproposed Finding 11
    remediation** -- same root cause (config version integrity), should
    be designed and implemented together rather than fixing the queue's
    instance in isolation, per the #004 proposal's own section 6.
11. **#004 Top Finding 18 (GPT-G5, stability bins)** -- additive field,
    no open design question, but worth sequencing after the
    config-integrity work since both touch `EvidencePacket`/
    `HypothesisConfig`-adjacent code and a reviewer doing both at once
    has useful context already loaded.
12. **#004 Top Finding 14 (GPT-G1, content binding)** -- placed last
    deliberately: it is the most structurally involved fix (a new
    field on `HumanDecision`/`ConsensusRecord`, a verifiable
    transformation chain across four different object shapes) and
    benefits from every other #004 fix already being in place and
    tested first, so its own regression suite isn't fighting a moving
    target.

---

## 3. Per-item recommended solution, and what remains Radu's own call

### #003 F1 (Top Finding 11) -- OOS isolation

- **Part 1, fetch bounding: RECOMMENDED, no remaining open question.**
  `effective_as_of = min(data_as_of, development_end)`, applied in
  `_resolve_session_dates()`'s benchmark fetch and
  `_fetch_bars_by_security()`. Already the agreed technical direction
  per `spec003_remediation_proposal_2026-10-04.md`'s F1 section 1.
- **Part 2, classification mechanism: Radu's own call, no candidate
  design exists yet.** Both previously-proposed options are
  structurally unbuildable (see that document's F1 section 2 for the
  full argument). This document does not add a new candidate; it
  flags that the next design session on this item starts from zero,
  not from a shortlist, and may need the conceptual question in
  section 1 above settled first (what, precisely, must be provable
  about an observation to call it OOS-derived).
- **Part 3, `research_period` wiring: RECOMMENDED, no open question.**
  Read `evaluation_config.data["research_period"]` as the default,
  explicit args take precedence.

### #003 F2a + F2b (Top Finding 12a/12b) -- signature-set integrity

**RECOMMENDED, no open question on either.** F2a: recompute
`freeze_signature_set()` at `run_evaluation()`'s entry and raise on
mismatch. F2b: a duplicate-`signature_id` check at the SAME entry
gate (not only inside `freeze_signature_set()`, which a
`dataclasses.replace()`-built set bypasses, per the proposal's own
F2b correction). Both are cheap, deterministic, additive checks with
no behavior change for any legitimately-built `SignatureSet`.

### #003 F6 (Top Finding 7) -- `family_test_count`

**RECOMMENDED, no open question.** Add the field; populate it
exactly when `mode == "FORMAL_DEVELOPMENT"` AND the profile's own
`raw_p is not None`, mirroring the existing `adjusted_p`/`family_id`
population rule. The combined rule is already fully specified in the
#003 proposal's F6 section.

### #003 F3 (Top Finding 13) -- population mismatch

**Radu's own call between (a) and (b); no default.** (a) report the
comparison as unavailable when bins lack baseline controls; (b)
restrict both the reported effect and the tested significance to the
identical common-support bin set. **This document's own observation,
offered as input to that decision, not a recommendation overriding
it:** (b) preserves more information (a comparison is still reported,
just honestly scoped) and is more consistent with F4+F5's own
direction below (which also moves toward "define the population once,
compute everything from that one definition" rather than "withhold
when something doesn't line up") -- if Radu wants one coherent
philosophy across F3 and F4+F5 rather than deciding each in isolation,
(b) is the one that generalizes the same way F4+F5's "one weighted
distribution feeds every statistic" principle does. This is offered
for Radu's own weighing, not asserted as settled.

### #003 F4 + F5 (Top Finding 14/15) -- baseline weighting

**The "define one weighted distribution, compute mean/median/IQR from
it" structural fix: RECOMMENDED, no open question.** This closes the
IQR-vs-mean/median weighting mismatch (F4) regardless of which
within-bin estimator is chosen for F5.

**Radu's own call on the within-bin estimator (F5), between (i)
collapse-to-representative and (ii) reweight-keep-every-row; no
default.** **This document's own observation:** (ii) preserves more
of the actual sampled variance (every raw observation still
contributes to IQR/IQR-adjacent statistics, not just one point per
security), which seems more consistent with SS74C's own stated
concern (that a security with more sessions shouldn't dominate the
POINT ESTIMATE while still letting the underlying statistical texture
of the data show through elsewhere) -- but (i) is simpler to reason
about and audit by hand. Whichever is chosen must be applied
consistently across the point estimate, `baseline_iqr`/
`standardized_effect`, AND `stratified_permutation_p_value()`'s own
per-security handling, per the #003 proposal's own explicit
requirement -- this document adds no new requirement here, only
restates it so it isn't lost in the build order.

### #003 S1 (Top Finding 16) -- numeric validation gaps

**Radu's own call on whose responsibility this is** (Evaluation
defensive regardless of upstream guarantees, vs. an explicit trust-
boundary note in `spec003_known_limitations.md`). No technical blocker
either way; this is a documentation-vs-code-change decision, not a
design question.

### #003 S2 (Top Finding 17) -- run/config identity

**RECOMMENDED as a design, with one open sub-question for Radu: the
versioning-epoch mechanism.** Extending `build_run_id()`'s fingerprint
to include `security_ids`/`benchmark_security_id`/`data_as_of`/
`horizons` is itself uncontested. What needs Radu's own decision is
HOW to mark the scheme change (a `run_id_scheme_version` field, vs.
accepting that pre/post-change ids are simply not comparable) -- a
smaller, bounded version of the SAME versioning-epoch question #004's
Finding 19/11 raises for `hypothesis_config_version` (section 3 below).
Worth deciding both epoch-marking questions in the same sitting for
consistency, even though the underlying bugs are unrelated.

### #003 G1 (Top Finding 18) -- TEST 26 AST guard

**RECOMMENDED, no open question.** Extend `_imported_modules()` to
also collect `alias.name`. Mirrors the already-accepted-as-correct
direction for the identical #002 (TEST 17/18) and #004 (TEST 49) gaps,
though those remain separately undecided for implementation (per each
spec's own status).

### #003 G2 (Top Finding 19) -- TEST 34 tautology

**RECOMMENDED, no open question.** Remove `or True`; assert on
`dataclasses.fields()` for the "no winner field" check rather than a
self-referential list comparison. This is itself a test fix, not a
production-code change.

### #004 Top Finding 14 (GPT-G1) -- content binding

**Direction RECOMMENDED (bind to a fingerprint frozen at approval
time, verified through an explicit transformation chain); the exact
field-by-field transformation mapping is Radu's own call.** Per the
#004 proposal's own section 1: a `HumanDecision`/`ConsensusRecord`
field (`approved_proposal_fingerprint`, or equivalent) frozen at
approval time, recomputed and compared at the gate against the SAME
transformation applied to the content actually being frozen -- not a
same-call draft-vs-proposal comparison (shown insufficient), and not a
"trusted constructor" alone (the gate must validate what it receives
regardless of construction path). What remains open: the precise
transformation for every field, especially which parts of
`exit_hypotheses` count as "faithfully derived" (via
`materialize_variants()`'s eager expansion) vs. "substituted."

### #004 Top Finding 15 (GPT-G2) -- variant completeness/semantics

**RECOMMENDED, no open question.** Add an explicit check that every
`horizon_candidate_set.values` entry has its own materialized
TIME_EXIT variant (not just that the two supplied id sets agree with
each other); promote `horizon_reference_point`/`exit_execution_policy`
to validated values and check `time_exit_bars`' sign for TIME_EXIT,
mirroring the existing `STOP_MANAGED_INVALIDATION` validation pattern.

### #004 Top Finding 16 (GPT-G3) -- gate atomicity

**Radu's own call on how wide the guarantee needs to be; this
document's recommendation if a single default is wanted: option (b),
true rollback, scoped and tested explicitly for the specific exception
types `_force_register()`/`register_variant()` are documented to
raise today.** Rationale: option (a) (pre-validation only) is cheaper
but its guarantee is conditioned on the dry run's precondition set
never drifting from the actual write-path preconditions over time --
a maintenance burden that can silently erode; (b) ties the guarantee
directly to what actually executes, at modest extra code cost, and
is easier to keep correct as the module evolves. Per the #004
proposal's own correction, even (b) must state its exception coverage
explicitly rather than claim "any failure" by virtue of being called
"rollback."

### #004 Top Finding 17 (GPT-G4) -- registry bypass

**RECOMMENDED, no open question.** Widen `register()`'s guard from
`existing is None and hyp.status == PREREGISTERED` to `hyp.status ==
PREREGISTERED and (existing is None or existing.status !=
PREREGISTERED)`, per the #004 proposal's own section 4 option (a).

### #004 Top Finding 18 (GPT-G5) -- stability bins

**RECOMMENDED, no open question.** Add a compact
`primary_stability_summary` field (bin label/mean/median/
positive_rate/valid_n per bin, for the primary reference horizon
only), matching the packet's existing flat/compact design philosophy,
per the #004 proposal's own section 5 option (a). Revisit if Finding
8's own token-budget measurement (still untested either way) shows
this pushes the packet past its ~1-3KB target.

### #004 Top Finding 19 (GPT-G6) + Finding 11 -- config integrity

**Direction RECOMMENDED (identify/compare-three-way/reject/pin-and-use
the snapshot, with a version explicitly registered for the operation);
the exact source and mechanism for registering that expected version,
and the versioning-epoch marker for the hash-scheme change, are
Radu's own call.** Per the #004 proposal's own section 6, revised:
not "recompute a hash of whatever is passed in" (shown circular), and
not "the file currently on disk" alone (shown insufficient, since the
file itself can drift between when a run's config was decided and
when it executes) -- a version registered for the specific operation,
checked for three-way concordance (actual content / the object's own
claimed version / the registered expected version), with the
operation then using the pinned snapshot itself afterward. See also
S2's own versioning-epoch question above -- worth deciding both epoch
markers together.

### #004 Top Finding 20 (P004C) -- persistence type registry

**RECOMMENDED, no open question.** Add `StopLossRule`,
`PartialProfitRule` to `_TYPE_REGISTRY` in `registry/persistence.py`.
Separate from, and does not reopen, the Exit Amendment text's
acceptance or PATCH #004-C's own separate, still-pending implementation
verdict.

---

## 4. Consolidated regression checklist

Each item's detailed scenario list already exists in the two
per-spec proposal documents (#003 proposal's own "Tests needed"
per section; #004 proposal's own "Required regression coverage"
section). This is a single checklist for tracking sign-off and build
order together, not a restatement of the scenarios themselves:

| # | Item | Regression scenarios specified in | Status |
|---|---|---|---|
| 1 | #003 F1 part 1 | `spec003_remediation_proposal...md` F1 "Tests needed" | planned, not written |
| 2 | #003 F2a/F2b | same doc, F2a/F2b sections | planned, not written |
| 3 | #003 F6 | same doc, F6 section | planned, not written |
| 4 | #003 F3 | same doc, F3 section | planned, not written -- depends on (a)/(b) choice |
| 5 | #003 F4+F5 | same doc, F4+F5 section | planned, not written -- depends on (i)/(ii) choice |
| 6 | #003 F1 part 2 | not yet specifiable -- no design exists | OPEN, blocked on design |
| 7 | #003 S1 | same doc, S1 section | planned, not written -- contingent on Radu's trust-boundary call |
| 8 | #003 S2 | same doc, S2 section | planned, not written |
| 9 | #003 G1 | same doc, G1 section | planned, not written |
| 10 | #003 G2 | same doc, G2 section | this IS the test fix |
| 11 | #004 Finding 14 | `spec004_remediation_proposal...md` regression-coverage list, Finding 14 | planned, not written |
| 12 | #004 Finding 15 | same doc, Finding 15 | planned, not written |
| 13 | #004 Finding 16 | same doc, Finding 16 | planned, not written -- depends on (a) vs (b)/(c) choice |
| 14 | #004 Finding 17 | same doc, Finding 17 | planned, not written |
| 15 | #004 Finding 18 | same doc, Finding 18 | planned, not written |
| 16 | #004 Finding 19 | same doc, Finding 19 | planned, not written -- depends on registered-version mechanism |
| 17 | #004 Finding 20 | same doc, Finding 20 | planned, not written |

**None of these regressions exist yet. None of this implies any
authorization to write or run them against production code -- that is
stage 3, not this document.**

---

## 5. Sign-off checklist for Radu

For each row, Radu's decision is one of: **approve the recommended
direction**, **choose an option where this document flagged one as
his own call**, or **reject/send back for a different design**.
Approving a row here authorizes DESIGN, not implementation --
stage 3 (implementation/acceptance) is a separate, later decision per
this project's standing three-stage discipline, for every row, even
once design is approved.

- [ ] #003 F1 part 1 (fetch bounding)
- [ ] #003 F1 part 2 (classification) -- **no design exists yet; this
  row cannot be approved until one does**
- [ ] #003 F2a + F2b
- [ ] #003 F6
- [ ] #003 F3 -- **choose (a) or (b)**
- [ ] #003 F4+F5 structural fix (one weighted distribution)
- [ ] #003 F4+F5 within-bin estimator -- **choose (i) or (ii)**
- [ ] #003 S1 -- **choose: defensive code change, or documented trust
  boundary**
- [ ] #003 S2 -- **choose the versioning-epoch marker mechanism**
- [ ] #003 G1 (TEST 26 guard)
- [ ] #003 G2 (TEST 34 fix)
- [ ] #004 Finding 14 -- **approve direction; field-by-field
  transformation mapping still to be specified in detail**
- [ ] #004 Finding 15
- [ ] #004 Finding 16 -- **choose (a), (b), or (c), with explicit
  exception-coverage statement**
- [ ] #004 Finding 17
- [ ] #004 Finding 18
- [ ] #004 Finding 19 / Finding 11 -- **choose the registered-version
  source/mechanism and the versioning-epoch marker**
- [ ] #004 Finding 20

**Baseline `3cdc532`, historical acceptances, and the Spec #005/Batch 3
pause are unchanged by this document.**
