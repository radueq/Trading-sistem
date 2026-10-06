# Implementation Plan -- Spec #003 + Spec #004 remediation (2026-10-05/06, revision 2)

**Status: NOT AUTHORIZED.** Built from `docs/joint_remediation_design_
003_004_2026-10-04.md` (revision 11, closed calendar contract included)
and `docs/decision_sheet_003_004_2026-10-05.md` (revision 5, the
Technical Decision Registry). **Precedence: the registry's own decisions
replace revision 11's open alternatives; this plan only sequences
already-made decisions, it does not re-decide anything.** No code or
test was written or run to produce it.

**Revision 2 corrects revision 1's own dependency errors (per GPT's
review, relayed by Radu):** a wrong stage cross-reference for the
run-id scheme marker; a false sequential dependency between the
quantile convention and the permutation estimator (both are siblings
under F4+F5, not sequential); a false functional dependency of the
evidence/queue stage on the preregistration gate; an incomplete S2
field enumeration; a missing explicit Research Queue integration for
the shared config-identity mechanism; a missing explicit carry-forward
of the bootstrap/CI design; an under-specified J1 acceptance matrix; an
E1 acceptance criterion that didn't state the present, in-memory scope
of the gap precisely enough; a B3 framing that implied the manual path
resolves calendar-source availability by itself; and a G2 exclusion
note that repeated restrictions revision 4 of the registry has since
retracted.

**Two items remain explicitly EXCLUDED from staging -- not merely
deprioritized:**
- **G2 (out-of-sample confirmation protocol):** unscoped. No design
  exists, and no stage below assumes one.
- **B3's real-calendar availability:** the admission MECHANISM is
  staged (Stage 2) and buildable with fixtures now; having an actual,
  genuinely-attested calendar available for real formal runs is
  separate, operationally blocked, pending source identification
  (GPT/Claude's own research, not staged as a deliverable here).

**Acceptance criteria throughout are TECHNICAL-CORRECTNESS criteria
only.** None of this demonstrates strategy performance; a profitable
backtest is a separate, later, not-yet-scoped evaluation.

---

## Finding/item -> stage -> regression, short correspondence

*(Pointer table only -- full regression text lives in the joint
design's own section 12 and in the registry's per-item "Verification
needed." Not duplicated here.)*

| Item | Stage | Regression reference |
|---|---|---|
| J1 (S1 numeric validation) | 1 | Registry J1; 15-case parameterized matrix below |
| Calendar admission/registry (section 2) | 2 | Registry B1-B4; joint design section 2's 5 named regressions |
| Target-session resolution (section 1.3) | 2 | Joint design section 1.3/12 |
| Run-identity linkage + S2 (I1) | 2 | Registry I1; joint design section 12 |
| RegisteredConfigVersion (Finding 19/11) | 3 | Joint design section 7/12 |
| F2a/F2b/F6 | 4 | Joint design section 9 |
| A2 (session_mass diagnostic) | 4 | Registry A2 |
| F4+F5 weighting | 4 | Joint design section 3 |
| A3 (quantile/`baseline_iqr`) | 4 | Registry A3 |
| Bootstrap/CI | 4 | Joint design section 6/12 |
| A4 (permutation + `exchangeability_status`, #003+#004 bundle) | 4 | Registry A4, in full |
| TEST 26 AST guard | 5 | Joint design section 8/9 |
| D1/Finding 14 | 6 | Registry D1; joint design section 10/12 |
| E1/Finding 16 | 6 | Registry E1 |
| Finding 15/17 | 6 | Joint design section 10/12 |
| G1/Finding 1 | 6 | Registry G1 |
| H1/Finding 10 | 6 | Registry H1 |
| TEST 49 + F1 | 7 | Joint design section 8; registry F1 |
| Finding 18/20 | 8 | Joint design section 10/12 |

---

## Stage 1 -- Numeric safety net (#003)

**No dependency on any other stage.**

- **J1:** `compute_forward_outcome()` and the benchmark-price path used
  for relative return reject non-finite or non-positive prices with
  `INVALID_INPUT`, never a raised exception or a nonsensical `VALID`.

**Acceptance criteria -- full parameterized matrix, not a sample.** Five
bad values (`0.0`, negative, `NaN`, `+inf`, `-inf`) crossed against
three price roles (security entry price, security exit price,
benchmark price): 15 cases minimum, each asserting `INVALID_INPUT`;
existing `VALID`-path tests unaffected.

---

## Stage 2 -- Calendar foundation AND the run-identity fingerprint change (#003, Spec #005 boundary)

**Independent of Stage 1.** **Corrected this round: I1's `run_id_
scheme_version` marker is delivered TOGETHER WITH this stage, not in
Stage 3 -- the marker must accompany the FIRST actual change to
`build_run_id()`'s own hash preimage, and that first change IS the
calendar-identity addition below. Shipping the fingerprint change
without the marker, even briefly, would leave a window where two
schemes could collide on one `evaluation_run_id`.**

- Revision 11's own admission/registry contract (section 2, CLOSED --
  implemented as specified): Step 0 source admission (operator-
  attestation path; see registry B3 on the approved-provider path's
  separate, still-blocked status), `verify_calendar_against_source()`,
  `CalendarVerificationRecord`, atomic joint registration into
  `VerifiedCalendarRegistry`, Evaluation's resolve-by-identity-with-
  required-record consumption rule. `build_trading_calendar()` stays
  unrestricted.
- **B1:** `OFFICIAL_VERIFIED`-only strictness for #003 FORMAL_
  DEVELOPMENT runs.
- **B2:** new `OutcomeStatus.DATA_GAP` replacing today's 4a/4b split.
- Section 1's own target-session resolution: exact-match `T_entry`,
  `target_index = entry_index + horizon_bars`, explicit failure if past
  the end.
- **Run-identity fingerprint change, delivered as ONE unit (registry
  I1):** `build_run_id()`'s own fingerprint gains, together: the
  calendar's own identity; `security_ids` (sorted); `benchmark_
  security_id`; `data_as_of`; `horizons` (sorted) -- the FULL field set
  per `spec003_remediation_proposal_2026-10-04.md`'s own S2 section,
  not the marker and `horizons` alone; AND the new `run_id_scheme_
  version` literal constant, INSIDE this same hash preimage.
- **B4:** relocate `TradingCalendar`/`build_trading_calendar()` out of
  `src/backtest/` -- a pure, behavior-preserving move, independently
  parallelizable with the rest of this stage.

**Acceptance criteria.** The five admission/registry regressions
(direct construction without a record refused; record linked to wrong
calendar/artifact rejected; session/exception discrepancy rejected;
failed registration leaves no partial state; valid case resolves from
registry) -- run against FIXTURE artifacts per B3's current, still-
blocked real-source status; a FORMAL_DEVELOPMENT run refusing a
`SYNTHETIC_TEST_FIXTURE` calendar; B2's DATA_GAP test; target-session
index-arithmetic regressions; SEPARATE regressions confirming two runs
differing only in `security_ids`, only in `benchmark_security_id`, only
in `data_as_of`, only in `horizons`, and only in `run_id_scheme_version`
each produce different `evaluation_run_id`s (five independent-axis
checks, not one); B4's byte-identical relocation regression plus the
`evaluation` -> `backtest` import-direction guard test.

---

## Stage 3 -- Config identity infrastructure (shared #003 + #004)

**Independent of Stage 2.** **Corrected this round: Finding 19/11's own
text states "one `load_config()` call PER OPERATION" generically, not
scoped to the preregistration gate alone -- this stage must wire the
SAME `RegisteredConfigVersion` mechanism into Research Queue
construction (`build_research_queue()`'s own read of `config.data[
"research_queue_eligibility"]`), not only into Stage 6's gate.**

- Section 7's `RegisteredConfigVersion` mechanism: one `load_config()`
  call per operation, full recursive freeze, label-check + structural-
  equality two-part verification (both sides normalized to the same
  representation).
- Mandatory live re-read at #004's preregistration gate (**C1**, feeds
  Stage 6).
- The SAME mechanism wired into Research Queue construction -- one
  registered, frozen config snapshot per queue-build operation, not an
  unguarded direct `load_config()` call.

**Acceptance criteria.** The correct-content-wrong-label case rejected
by the label check; the correct-label-wrong-content case rejected by
structural equality, both sides normalized before comparing; config-
mutated-between-approval-and-registration caught by the mandatory live
re-read; a SEPARATE regression confirming `build_research_queue()`
rejects or correctly reports when its own config snapshot doesn't match
its registered version, mirroring the preregistration gate's own check.

---

## Stage 4 -- #003 statistics AND its #004 consumers, delivered as one bundle

**Depends on Stage 2 (same calendar-resolved session dates feed
bootstrap/bin assignment). Internal structure corrected this round: A3
and A4 are SIBLINGS, both consuming the SAME weighted pool F4+F5
establishes -- neither depends on the other; there is no sequencing
between them.** **Also corrected: A4's own `exchangeability_status`
field (#003) and its #004 consumers (`evidence/queue.py`'s ranking
fallback, the two report scripts) are delivered TOGETHER, inside this
same stage -- not deferred to Stage 8, so that no intermediate state
ever exists where #003 produces the new status and #004 doesn't yet
respect it.**

- F2a/F2b (frozen signature-set content/id verification; duplicate
  `signature_id` rejection) and F6 (`family_test_count`) -- design-
  complete, section 9.
- **A2:** `session_mass` diagnostic (measurement only).
- **F4+F5's own per-security weighting formula**, establishing the
  weighted baseline pool both A3 and A4 draw from independently.
- **A3:** midpoint-with-tie-aggregation convention, computing `baseline_
  iqr` from that weighted pool (section 4.1/4.2) -- replacing today's
  unweighted `robust_iqr()` call. Does not touch `stratified_baseline_
  point_estimate()`'s own `baseline_mean`/`baseline_median` computation
  (Level 1, unchanged) or the signature's own unweighted `DescriptiveStats`.
- **Bootstrap/CI, carried forward explicitly (joint design section 6):**
  the per-replicate weighted estimator (recompute `k_rep`/`n_i_rep` from
  EACH replicate's own composition, applying F4+F5's weight formula
  with replicate-local values) stays the mechanism that consumes
  weights; interval construction from the `B` replicate statistic values
  is the UNWEIGHTED `2.5`th/`97.5`th percentile of those plain numbers
  -- weighting is NOT reapplied at that second step.
- **A1:** F3 common support, (a) UNAVAILABLE -- full comparison
  blackout on partial OR zero common support; signature's own full-
  population `DescriptiveStats` unaffected.
- **A4, #003 side:** weighted-permutation estimator mechanics; new
  `exchangeability_status` field on `BaselineComparison`, hard-coded
  `"UNVERIFIED"`, propagated to `DecayPoint` and `EvidencePacket.
  primary_exchangeability_status` (registry A4, full propagation
  design).
- **A4, #004 side, SAME bundle:** `evidence/queue.py`'s `compute_review_
  priority()` treats `p_key` as `float("inf")` whenever `primary_
  exchangeability_status != "VERIFIED"` (always true for V1); `tests/
  spec003/generate_report_artifacts.py` and `tests/spec004/generate_
  report_artifacts.py` updated to print the qualifier or label the
  figure as diagnostic-only wherever `adjusted_p`/`standardized_effect`
  appear.

**Acceptance criteria.** F2a/F2b/F6 regressions (section 9); the
WEIGHTED `session_mass` reproducing the 5%/95% split, regression-
locking the raw-`Counter` wrong answer; weight-rescaling invariance
(>= 3 scale factors) and the tie/weight-permutation matrix applied to
`baseline_iqr`'s own computation; A1's partial-support regression
(full blackout, descriptive stats intact) plus the zero-support
degenerate case; the exhaustive-enumeration permutation regression
(signature `[8]`, baseline `[0,2]`/`[4]`, weights `[1/4,1/4,1/2]`,
observed `5.5`, exact `p = 8/24 = 1/3`) kept distinct from any Monte
Carlo estimate; the equal-weight case verified byte-identical to
today's existing `stratified_permutation_p_value()` test; the FULL
integration regression (real `run_evaluation()` -> `build_evidence_
packet()` -> `compute_review_priority()`, never a hand-built packet)
confirming `exchangeability_status == "UNVERIFIED"` survives intact and
that an artificially small `adjusted_p` ranks NO HIGHER than `adjusted_
p = None` would; a structural check that no function in `packet.py`/
`entities.py` accepts `exchangeability_status` as an external argument.

---

## Stage 5 -- #003 AST guard (TEST 26) and architectural direction

**No dependency on Stages 1-4.**

- `discovery` -> `evaluation` import guard, shared algorithm with
  Stage 7's TEST 49 fix -- design-complete, no remaining open item.

**Acceptance criteria.** Section 8's consolidated case matrix with
`"evaluation"` as the forbidden name; the exact scratch-file regression
(`from src import evaluation as ev`) confirmed caught.

---

## Stage 6 -- #004 preregistration gate hardening

**Depends on Stage 3 (consumes `RegisteredConfigVersion`/C1's snapshot
directly). No dependency on Stage 4.**

- **D1:** gate-time revalidation, option (i), against the Stage-3
  snapshot.
- Finding 14's draft-vs-proposal binding, baseline-designation timing
  correction, `approved_designated_baseline_bars`'s own separate check.
- **E1 (Finding 16/GPT-G3):** batch-internal simulated-sequential dry
  run, accepted at EXACTLY its stated 3-condition/synchronous-only
  scope.
- Finding 15 (full-content variant-uniqueness key), Finding 17
  (`register()` guard widened).
- **G1 (Finding 1):** hard-reject `source_evidence.evaluation_mode !=
  "FORMAL_DEVELOPMENT"`; Finding 2 (`research_mode` reject) alongside it.
- **H1 (Finding 10):** exit-family count by TYPE -- confirmed, no code
  change beyond what Finding 15 already requires.

**Acceptance criteria.** D1: live re-validation confirmed on the gate
path; a stale/altered `facts_from_evidence`/`interpretation` caught by
construction. Finding 14: the lockstep-mutation regression rejected.
**E1's acceptance criterion, stated exactly, per the registry's own
corrected wording -- a PRESENT fact, not a future one:** no partial
write under content mismatch, PREREGISTERED-content mismatch, or
variant content mismatch, UNDER SYNCHRONOUS EXECUTION ONLY; an explicit
test/doc statement that, TODAY, under the current plain in-memory dict,
an exception outside these three conditions is NOT guaranteed to leave
the registry in an all-or-nothing state -- this statement must appear
in the shipped code's own docstring, not only in this plan, and must
never be paraphrased into a broader claim. Finding 15/17: existing
regression matrix (section 10/12). G1: rejection on `EXPLORATORY`-
sourced evidence and on a FALSELY-claimed `FORMAL_DEVELOPMENT` mode
cross-checked against the real run registry.

---

## Stage 7 -- #004 TEST 49 AST guard

**Shares its algorithm with Stage 5; the naming convention is
#004-specific.**

- Corrected AST algorithm (base+alias candidate construction, `level -
  1` relative-import climb, filesystem demoted to informational).
- **F1:** bare top-level `hypothesis` name reserved by convention.

**Acceptance criteria.** Section 8's consolidated case matrix for the
`hypothesis` namespace; a dependency-management-surface note flagging
that adding a `hypothesis` PyPI dependency requires revisiting F1.

---

## Stage 8 -- #004 evidence/queue correctness (Finding 18/20 only)

**Corrected this round: this stage is NOT functionally downstream of
Stage 6/G1 -- G1 governs admission INTO the preregistration gate; it
has no bearing on what already reaches the Research Queue, which
operates on signatures and `EvidencePacket`s upstream of any
preregistration decision. Any ordering relative to Stage 6 below is an
IMPLEMENTATION-convenience grouping (both touch #004's codebase), not a
functional dependency. This stage DOES depend on Stage 4's own
`EvidencePacket`/`packet.py` structure (Finding 18 concerns what reaches
that same structure).** A4's own queue-ranking wiring is NOT staged
here -- it shipped as part of Stage 4's bundle, per that stage's own
correction.

- Finding 18 (stability-bin values reach `EvidencePacket` with CORRECT
  values, not just a presence flag).
- Finding 20 (`StopLossRule`/`PartialProfitRule` round-trip).

**Acceptance criteria.** Finding 18/20 regressions (section 10) -- no
additional criteria beyond what those findings already specify.

---

## What this plan does NOT cover

- **G2** (confirmation protocol): excluded. **Corrected this round: no
  restriction beyond what was actually agreed is implied here --** any
  future design must reconcile with Spec #003's own existing Formation/
  Selection -> Development Validation -> Locked OOS architecture
  (`Spec_003_Outcome_Aware_Evaluation_v1.1.md` SS12), keep Locked OOS
  protected, and never reuse it for calibration. The exact protocol and
  the unit any access restriction applies to remain fully open,
  GPT/Claude's own future work -- not pre-decided by this plan or by
  the registry's own G2 entry.
- **B3's real-calendar availability:** excluded. The admission
  mechanism ships in Stage 2, testable with fixtures; an actual,
  genuinely-attested real calendar for real formal runs remains
  operationally blocked pending source identification -- this is
  research work, not a staged deliverable.
- **A2's real correction mechanism** and **A4's dependency-adequate
  method**: both remain undesigned, GPT/Claude's own future work, not
  scheduled into any stage above.
- **Strategy performance evaluation**: explicitly separate from every
  acceptance criterion above; not scoped by this plan at all.

---

**Authorization.** Every stage above is a PROPOSAL for sequencing
already-decided design work. No stage may begin until Radu explicitly
authorizes implementation. Findings reconciliation remains CLOSED (both
specs, within each review's own declared scope); the calendar admission/
trust contract (revision 11, section 2) remains CLOSED and unmodified.
Baseline `3cdc532`, historical acceptances, and the Spec #005/Batch 3
pause are unchanged.
