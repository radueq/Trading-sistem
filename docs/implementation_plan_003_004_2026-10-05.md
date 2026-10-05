# Implementation Plan -- Spec #003 + Spec #004 remediation (2026-10-05)

**Status: NOT AUTHORIZED.** This is a staging and acceptance-criteria
plan, built from `docs/joint_remediation_design_003_004_2026-10-04.md`
(revision 11, including its already-closed calendar admission/trust
contract) and `docs/decision_sheet_003_004_2026-10-05.md` (revision 4,
the Technical Decision Registry). It does not authorize writing or
running any code. Execution authorization is Radu's own call, requested
separately once he has this plan. No code or test was written or run to
produce it.

**Two items are explicitly EXCLUDED from staging below, not merely
deprioritized -- they are not ready to plan, let alone build:**
- **G2 (out-of-sample confirmation protocol):** unscoped. No design
  exists. Named here so its absence from the plan is a decision, not an
  oversight.
- **B3's approved-provider sub-path (calendar source admission):** no
  concrete source has been identified yet (GPT/Claude's own pending
  research). The operator-attestation sub-path of the SAME mechanism
  has no such blocker and IS staged below (Stage 1).

**Acceptance criteria throughout are TECHNICAL-CORRECTNESS criteria
only (regressions passing) -- per Radu's own standing instruction, none
of this demonstrates strategy performance. A profitable backtest is a
separate, later, not-yet-scoped evaluation; passing every criterion
below is not evidence of it, and is not required to be.**

---

## Stage 1 -- Numeric safety net (#003)

**No dependency on any other stage -- can start first.**

- **J1:** `compute_forward_outcome()` (and the benchmark-price path used
  for relative return) rejects non-finite or non-positive prices with
  `INVALID_INPUT`, never a raised exception or a nonsensical `VALID`.

**Acceptance criteria.** Regressions for `0.0`, negative, `NaN`, and
`+inf`/`-inf` at: entry price, exit price, benchmark price -- six cases
minimum, each asserting `INVALID_INPUT`; existing `VALID`-path tests
unaffected (no behavior change for already-valid inputs).

---

## Stage 2 -- Calendar foundation (#003, Spec #005 boundary)

**Depends on Stage 1 only insofar as both touch price/date validation
code; otherwise independent.**

- Revision 11's own admission/registry contract (section 2, CLOSED --
  implemented as specified, not redesigned): Step 0 source admission
  (operator-attestation path only, per B3's current scope -- see
  exclusion above), `verify_calendar_against_source()`,
  `CalendarVerificationRecord`, atomic joint registration into
  `VerifiedCalendarRegistry`, Evaluation's resolve-by-identity-with-
  required-record consumption rule. `build_trading_calendar()` stays
  unrestricted.
- **B1:** `OFFICIAL_VERIFIED`-only strictness for #003 FORMAL_
  DEVELOPMENT runs.
- **B2:** new `OutcomeStatus.DATA_GAP` replacing today's 4a/4b split
  (4b no longer silently labeled `INSUFFICIENT_FUTURE_DATA`).
- Section 1's own target-session resolution: exact-match `T_entry`,
  `target_index = entry_index + horizon_bars`, explicit failure if past
  the end -- replacing the coverage-window-based framing.
- Run-identity linkage: calendar identity feeds `build_run_id()`'s own
  fingerprint (shared with Stage 4's `run_id_scheme_version` work --
  sequence together or Stage 2 first).
- **B4:** relocate `TradingCalendar`/`build_trading_calendar()` out of
  `src/backtest/` into a neutral location -- a pure, behavior-preserving
  move; may be done in parallel with the rest of this stage since it
  has no logic dependency on it.

**Acceptance criteria.** The five admission/registry regressions named
in the registry's B1-B4 entries and the joint design's section 2 (direct
construction without a record refused; record linked to wrong calendar/
artifact rejected; session/exception discrepancy rejected; failed
registration leaves no partial state; valid case resolves from
registry); a FORMAL_DEVELOPMENT run refusing a `SYNTHETIC_TEST_FIXTURE`
calendar; B2's DATA_GAP test (both 4a and 4b produce it, neither
produces `INSUFFICIENT_FUTURE_DATA`); target-session index-arithmetic
regressions (`T_entry` absent; `target_index` past the end; target
present but security bar missing); two runs on different calendars
producing different `evaluation_run_id`s; B4's byte-identical relocation
regression plus the new `evaluation` -> `backtest` import-direction
guard test.

---

## Stage 3 -- Config identity infrastructure (shared #003 + #004)

**No dependency on Stages 1-2.**

- Section 7's `RegisteredConfigVersion` mechanism: one `load_config()`
  call per operation, full recursive freeze, label-check +
  structural-equality two-part verification (both sides normalized to
  the same representation), mandatory live re-read at #004's
  preregistration gate (**C1**, feeds Stage 6).
- **I1:** separate, literal `run_id_scheme_version` constant inside
  `build_run_id()`'s own fingerprint input (not beside it).

**Acceptance criteria.** The correct-content-wrong-label case rejected
by the label check specifically; the correct-label-wrong-content case
rejected by the structural-equality check specifically, both sides
normalized before comparing; config-mutated-between-approval-and-
registration caught by the mandatory live re-read; two runs differing
ONLY in `run_id_scheme_version` producing different `evaluation_run_
id`s; a separate regression confirming two runs differing only in
`horizons` (same scheme) also differ -- the two axes independently
captured.

---

## Stage 4 -- #003 statistics (F3/F4+F5/quantiles/permutation)

**Depends on Stage 2 (uses the same calendar-resolved session dates for
bootstrap/bin assignment) and internally sequences A3 after/with A4
(A3's `baseline_iqr` consumes F4+F5's own weighted baseline pool).**

- F2a/F2b (frozen signature-set content/id verification; duplicate
  `signature_id` rejection) and F6 (`family_test_count`) -- already
  design-complete, section 9.
- **A2:** weighted `session_mass` diagnostic (measurement only, no
  correction applied).
- F4+F5's own per-security weighting formula (uncontested, the original
  #003 patch) feeding a now-weighted baseline pool.
- **A3:** midpoint-with-tie-aggregation weighted-quantile convention,
  computing the baseline's own `baseline_iqr` (section 4.1/4.2) --
  replacing today's unweighted `robust_iqr()` call.
- **A1:** F3 common support, (a) UNAVAILABLE -- partial AND zero common
  support both collapse the FULL comparison (`mean_difference`/`median_
  difference`/`raw_p`/CI/`standardized_effect`) to `None` together;
  signature's own full-population `DescriptiveStats` stay unaffected.
- **A4:** weighted-permutation estimator (mechanics); new
  `exchangeability_status` field on `BaselineComparison`, always
  `"UNVERIFIED"` for V1; `evidence/queue.py`'s `compute_review_
  priority()` (Stage 8) must treat `p_key` as neutral while unverified.

**Acceptance criteria.** F2a/F2b/F6 regressions (section 9, already
specified); the WEIGHTED `session_mass` reproducing the 5%/95% split,
regression-locking the raw-`Counter` wrong answer; weight-rescaling
invariance (>= 3 scale factors) and the tie/weight-permutation matrix
for the quantile convention, applied to `baseline_iqr`'s own
computation specifically; A1's partial-support regression (full
comparison blackout, descriptive stats intact) plus the zero-support
degenerate case; the exhaustive-enumeration permutation regression
(signature `[8]`, baseline `[0,2]`/`[4]`, weights `[1/4,1/4,1/2]`,
observed `5.5`, exact `p = 8/24 = 1/3`) kept distinct from any Monte
Carlo estimate; `exchangeability_status == "UNVERIFIED"` asserted on
every profile this mechanism touches; the equal-weight case verified
byte-identical to today's existing `stratified_permutation_p_value()`
test and every existing test covering it re-run passing.

---

## Stage 5 -- #003 AST guard (TEST 26) and architectural direction

**No dependency on Stages 1-4.**

- `discovery` -> `evaluation` import guard, shared algorithm with
  Stage 7's TEST 49 fix -- already design-complete, no remaining open
  item (section 8/9).

**Acceptance criteria.** Section 8's consolidated positive/negative case
matrix, with `"evaluation"` as the forbidden name; the exact scratch-
file regression (`from src import evaluation as ev`) confirmed caught.

---

## Stage 6 -- #004 preregistration gate hardening

**Depends on Stage 3 (consumes `RegisteredConfigVersion`/C1's snapshot
directly).**

- **D1:** gate-time revalidation, option (i) -- live re-validation
  against the Stage-3 snapshot, never a separately-loaded config.
- Finding 14's draft-vs-proposal binding (`verify_draft_matches_
  proposal()`, `HumanDecision.content_fingerprint`), the baseline-
  designation timing correction, and `approved_designated_baseline_
  bars`'s own separate check.
- **E1 (Finding 16/GPT-G3):** batch-internal simulated-sequential dry
  run, accepted at EXACTLY its stated 3-condition/synchronous-only
  scope -- the acceptance criteria below quote that scope verbatim, per
  the registry's own explicit instruction, never a broader paraphrase.
- Finding 15 (full-content variant-uniqueness key), Finding 17
  (`register()` guard widened to any-status-to-PREREGISTERED).
- **G1 (Finding 1):** hard-reject `source_evidence.evaluation_mode !=
  "FORMAL_DEVELOPMENT"`, enforced against the real `EvaluationRunRegistry`
  record. Finding 2 (`research_mode` reject) -- unchanged, shipped
  alongside it.
- **H1 (Finding 10):** exit-family count by distinct TYPE -- confirmed,
  no code change needed beyond what Finding 15 already requires.

**Acceptance criteria.** D1: live re-validation confirmed on the gate
path; a stale/altered `facts_from_evidence`/`interpretation` caught by
construction. Finding 14: the lockstep-mutation regression (`proposal`/
`draft` mutated together after approval, changing `designated_baseline_
bars` while leaving every economically-hashed field unchanged) rejected.
**E1's acceptance criterion, stated exactly:** no partial write under
content mismatch, PREREGISTERED-content mismatch, or variant content
mismatch, UNDER SYNCHRONOUS EXECUTION ONLY -- an explicit test/doc
statement that this guarantee does NOT cover concurrent callers or a
non-dict storage backend, verified present in the shipped code's own
docstring, not only in this plan. Finding 15/17: existing regression
matrix (section 10/12). G1: rejection on `EXPLORATORY`-sourced evidence
and on a FALSELY-claimed `FORMAL_DEVELOPMENT` mode cross-checked against
the real run registry.

---

## Stage 7 -- #004 TEST 49 AST guard

**Shares its algorithm with Stage 5; the naming convention is
#004-specific.**

- Corrected AST algorithm (base+alias candidate construction, `level -
  1` relative-import climb, filesystem demoted to informational).
- **F1:** bare top-level `hypothesis` name reserved by convention, not
  renamed.

**Acceptance criteria.** Section 8's consolidated case matrix for the
`hypothesis` namespace; a dependency-management-surface note (e.g. in
the requirements file) flagging that adding a `hypothesis` PyPI
dependency requires revisiting F1's convention.

---

## Stage 8 -- #004 evidence/queue integration

**Depends on Stage 4 (A1's `None`-propagation and A4's
`exchangeability_status`) and Stage 6 (G1's admission policy already
gating what reaches this point).**

- Finding 18 (stability-bin values reach `EvidencePacket` with CORRECT
  values, not just a presence flag), Finding 20 (`StopLossRule`/
  `PartialProfitRule` round-trip).
- Wire `evidence/queue.py`'s `compute_review_priority()` to treat
  `p_key` as neutral (`float("inf")`) whenever `exchangeability_status
  != "VERIFIED"` (always true for V1, per A4) -- ranking falls back to
  `effect_key`/`support_key` only.
- Confirm `EvidencePacket.primary_standardized_effect is None`
  (A1's/A3's partial-support or zero-support case) propagates into
  `compute_review_priority()` without crashing, using the SAME existing
  `None`-fallback the field already has.

**Acceptance criteria.** Finding 18/20 regressions (section 10); a test
confirming a profile with an artificially small `adjusted_p` ranks NO
HIGHER than it would with `adjusted_p = None`, given `exchangeability_
status == "UNVERIFIED"`; a test confirming a `None` `standardized_
effect` does not crash queue construction and ranks via `support_key`
alone.

---

## What this plan does NOT cover

- **G2** (confirmation protocol): excluded per above. Any future plan
  for it must reconcile with Spec #003's own existing Formation/
  Selection -> Development Validation -> Locked OOS architecture
  (`Spec_003_Outcome_Aware_Evaluation_v1.1.md` SS12) -- never a parallel
  mechanism, never Locked OOS reused for calibration.
- **B3's approved-provider sub-path**: excluded until a concrete source
  is identified; Stage 2 ships with the operator-attestation path only.
- **A2's real correction mechanism** and **A4's dependency-adequate
  method**: both remain undesigned, named as GPT/Claude's own future
  work, not scheduled into any stage above.
- **Strategy performance evaluation**: explicitly separate from every
  acceptance criterion above; not scoped by this plan at all.

---

**Authorization.** Every stage above is a PROPOSAL for sequencing
already-decided design work. No stage may begin until Radu explicitly
authorizes implementation -- this plan itself is not that authorization.
Findings reconciliation remains CLOSED (both specs, within each
review's own declared scope); the calendar admission/trust contract
(revision 11, section 2) remains CLOSED and unmodified by this plan.
Baseline `3cdc532`, historical acceptances, and the Spec #005/Batch 3
pause are unchanged.
