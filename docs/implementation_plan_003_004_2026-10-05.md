# Implementation Plan -- Spec #003 + Spec #004 remediation (2026-10-05/06/07, revision 11)

**Status: Stage 1 IMPLEMENTED and ACCEPTED. Stage 2 (corrected
admission/registry mechanism, calendar tested with fixtures) ACCEPTED
in that scope. Minimal `#003` v2 -> `#005` compatibility delta
ACCEPTED. Stage 3 (config identity infrastructure) IMPLEMENTED WITH
TWO ROUNDS OF CORRECTIONS APPLIED (commit `8650f17`, round-2 fix at
`955f482`, round-3 fix this revision), delivered for GPT's next review
-- NOT yet itself reviewed. Stage 4 onward: NOT AUTHORIZED.** Built
from `docs/joint_remediation_design_003_004_2026-10-04.md` (revision
11, closed calendar contract included, section 7 config identity) and
`docs/decision_sheet_003_004_2026-10-05.md` (revision 14, the
Technical Decision Registry). **Precedence: the registry's own
decisions replace revision 11's open alternatives; this plan only
sequences already-made decisions, it does not re-decide anything.**

**Revision 11 records GPT's own CHANGES REQUIRED verdict on Stage 3's
round-2 delivery (commit `955f482`): the four findings from round 2
are confirmed FIXED (verification runs by default; a tampered object
is rejected whether or not `config_registry` is new or omitted;
`freeze()` closes the `MappingProxyType` alias). One further defect
remained: nothing tied the preregistration gate back to the SPECIFIC
config the DRAFT was built under. GPT's own reproduction through the
real gate: a draft built under config A, preregistered while BOTH the
caller-supplied `hypothesis_config` AND the live file itself had moved
to a self-consistent config B, with no `config_registry` shared to
catch the drift -- was wrongly ACCEPTED, the resulting hypothesis
carrying `strategy_config_version=A` while the gate had actually run
under B. Fixed this revision -- see the updated Stage 3 section below
for exact detail.**

**Revision 10 records GPT's own CHANGES REQUIRED verdict on Stage 3's
first delivery (commit `8650f17`): the mechanism was PARTIAL, not the
complete section 7 implementation. Four concrete defects, all
corrected this revision -- see the updated Stage 3 section below for
exact detail; this revision does not re-sequence or re-decide anything
else.** In summary: (1) protection was opt-in, not the default --
omitting `config_registry` left Discovery/Evaluation/Research Queue's
original defect fully active, reproduced concretely through `build_
research_queue()`; (2) the first `register_or_verify()` call trusted
whatever (version, content) the caller's object merely claimed, even
on a brand-new registry; (3) `ConfigRegistry.register()` exposed an
unconditional public overwrite; (4) `freeze()` did not recurse into an
externally-supplied `MappingProxyType`. Fixed: verification is now
mandatory by default (a local, throwaway registry is used internally
when none is shared); every domain's loader now exposes `raw_texts` on
its config object plus a pure `reparse_raw_texts()`, so the trusted
reference is always re-derived independently from source text, never
from a caller's claim; `register()` is no longer public (`register_or_
verify()` is the only write path, idempotent-or-reject); `freeze()`
recurses into `MappingProxyType` identically to `dict`, and rejects any
other unrecognized mutable type outright.

**Revision 9 records the verdict GPT deferred to "the next authorized
update" (the `#003` v2 -> `#005` compatibility delta, commit
`483761a`: ACCEPTED, confirmed by independent execution -- legacy
verification unchanged, v2 verification correct including unsorted-
horizons handling, `calendar_id=None` accepted, tampering in any single
field rejected, missing required fields and unknown schemes rejected,
no fallback to the legacy recipe for a failed v2 claim, and the
canonical-JSON `admission_id` serialization fix also ACCEPTED -- the
`#003` v2/`#005` identity incompatibility is now CLOSED, scoped to the
verifier and the tested path, not the whole backtesting pipeline or
strategy performance), AND Stage 3's own delivery -- Radu's explicit
authorization, 2026-10-07, on the already-accepted plan's own section
7 design: config identity infrastructure (`RegisteredConfigVersion`),
applied to Discovery, Evaluation, Hypothesis's preregistration gate,
and Research Queue, implemented at commit `8650f17`. See the new Stage
3 section below for exact detail -- this revision does not re-sequence
or re-decide anything else.**

**Revision 8 records GPT's own ACCEPTED verdict on Stage 2's
third-corrected delivery (`fd992db`) and the separately-authorized
minimal `#003` v2 -> `#005` compatibility delta (Radu's own
authorization, 2026-10-07), implemented at `483761a` -- it does not
re-sequence or re-decide anything.** GPT independently confirmed the
admission-identity fix (revision 7) by execution: distinct `admission_
id`s for the same text under different metadata, both snapshots
retained, idempotent repeats, the calendar record tied to the exact
admission used, an unknown identity refused. Stage 2 is now ACCEPTED
in that scope. GPT also raised a non-blocking follow-up on the same
delivery (`_compute_admission_id()`'s separator-boundary serialization)
and recommended the `#005` compatibility delta before any further
stage -- both addressed in this same round: canonical-JSON
serialization for `admission_id`, and `backtest/provenance/
evaluation_run.py`'s `verify_evaluation_run_identity()` now dispatches
by `run_id_scheme_version` (legacy recipe unchanged for `None`; a new
14-field v2 recipe for `"v2"`; no fallback between them) -- see the
new section below for exact detail.

**Revision 7 records GPT's own THIRD CHANGES REQUIRED verdict, on
Stage 2's twice-corrected delivery (`0574171`/`0bdabe5`), and the
correction applied at `fd992db` -- it does not re-sequence or
re-decide anything.** GPT independently confirmed revision 6's
`effective_as_of` fix is correct and CLOSED (repeated the reproduction,
both the direct read and Discovery-triggered reads stay at the same
vantage point). One further defect was found, reproduced through the
public API alone: `AdmissionRegistry` keyed its entries by
`artifact_digest` alone, so two LEGITIMATE admissions of the identical
text under different metadata (different source, operator, coverage)
collided -- the second silently overwrote the first's retained
snapshot. Fixed by separating `admission_id` (the admission DECISION's
own identity, binding the digest to the full metadata) from
`artifact_digest` (the raw text's own hash) -- see Stage 2's own
section below for the corrected acceptance criteria and exact tests.

**Revision 6 records GPT's own SECOND CHANGES REQUIRED verdict, on
Stage 2's first-corrected delivery (`af7b938`/`8877551`), and the
corrections applied at `0bdabe5` -- it does not re-sequence or
re-decide anything.** Two further defects were found, both reproduced
directly by GPT: `register_verified()` still accepted a directly-
constructed `AdmittedCalendarSource` (never passed through the actual
admission gates) as long as it was internally self-consistent; and
`_resolve_session_dates_from_calendar()` bounded its returned session
list by `development_end` only, never by `effective_as_of`, letting
Discovery-triggered PIT reads (via `_collect_observations()`) go past
the run's own declared vantage point even though direct bar fetches
were already correctly bounded. Both are now fixed (the `effective_
as_of` fix was independently reconfirmed and closed by GPT in revision
7, above) -- see Stage 2's own section below for the corrected
acceptance criteria and exact tests. GPT also reconfirmed, by code
inspection, that all seven of revision 5's own corrections remain
valid.

**Revision 5 records GPT's own CHANGES REQUIRED verdict on Stage 2's
first delivery (`7fcf78d`) and the corrections applied at `8877551` --
it does not re-sequence or re-decide anything.** Seven defects were
found (none caught by the 789-passed test run revision 4 reported):
B1's strictness was bypassable when both calendar arguments were
omitted in FORMAL_DEVELOPMENT; the resolved calendar never reached
`compute_forward_outcome()`; the OOS wall was not applied to the PIT
fetch itself; `CalendarRegistry.register_verified()` accepted a
caller-built record on faith (reproduced: an invented digest and blank
verifier/timestamp, with no admission or verification call, was
accepted); the registry's two dict writes were not atomic (reproduced:
an injected failure at the second write left a calendar registered
with zero records); `DATA_GAP` was invisible to `MissingnessReport`'s
own reconciliation; and the v2/#005 incompatibility was asserted in a
comment, never demonstrated. All seven are now fixed -- see Stage 2's
own section below for the corrected acceptance criteria and exact
tests. Revision 4's own text (below) describes Stage 2 as it stood
before GPT's review and is kept for its own historical record.

**Revision 3 corrects four further items (per GPT's own decisions,
relayed by Radu, given explicitly rather than left as alternatives):**
Stage 4's A3 is rebuilt around ONE pooled weighted baseline distribution
feeding `baseline_mean`/`baseline_median`/`baseline_iqr` together,
replacing `stratified_baseline_point_estimate()`'s own Level-1
mechanism (confirmed unable to implement per-security weighting at all,
since its signature carries no security identity); Stage 4's A4 #004
wiring is now UNCONDITIONAL (`p_key = inf` always, in V1, never a
branch on `exchangeability_status`'s text), replacing a rejected
"no constructor argument" structural check with behavioral tests; Stage
1's J1 matrix grows from 15 to 20 cases (four price positions, not
three -- the benchmark has its own separate entry and exit price);
Stage 3's acceptance criterion drops the "rejects or correctly reports"
alternative -- a mismatched config is rejected, full stop, verified as
two separate checks (label, structural equality).

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
| J1 (S1 numeric validation) | 1 | Registry J1; 20-case parameterized matrix below (4 price positions) |
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

**IMPLEMENTED -- Radu's explicit authorization, 2026-10-06, Stage 1
only. Commit `7195fe4` on `claude/spec004-audit`.**

**No dependency on any other stage.**

- **J1:** `compute_forward_outcome()` and the benchmark-price path used
  for relative return reject non-finite or non-positive prices with
  `INVALID_INPUT`, never a raised exception or a nonsensical `VALID`.

**Acceptance criteria -- full parameterized matrix, corrected this
round (per GPT's own decision, relayed by Radu): FOUR price positions,
not three -- `attach_benchmark_return()` reads a separate benchmark
entry price (the division's own denominator) AND benchmark exit price
(the numerator), confirmed by reading the function in full.** Five bad
values (`0.0`, negative, `NaN`, `+inf`, `-inf`) crossed against FOUR
price roles (security entry price, security exit price, benchmark
entry price, benchmark exit price): 20 cases, each modifying exactly
one position with the rest valid, each asserting `INVALID_INPUT`;
`None` cases stay separate, through the existing missing-data contract;
existing `VALID`-path tests unaffected. **Verified: `tests/spec003/
test_41_numeric_validation_finite_positive_prices.py`, 22 tests (the 20
parameterized cases plus the `None`-distinct and `VALID`-unaffected
regressions), all passing; full project suite (`pytest tests/`): 749
passed, 1 skipped (pre-existing, unrelated) -- no regression.**

**ACCEPTED, GPT's own independent verification, relayed by Radu
(delivery `063d1a7`).** Verdict: Stage 1 / J1 -- ACCEPTED in the agreed
scope (price validation only, not a general exception/numeric-issue
guarantee). See registry revision 7, J1's own entry for the full
verdict text.

---

## Stage 2 -- Calendar foundation AND the run-identity fingerprint change (#003, Spec #005 boundary)

**ACCEPTED, in scope: the corrected admission/registry mechanism and
the calendar mechanism tested with fixtures (GPT's own verdict on
commit `fd992db`, relayed by Radu). Radu's explicit authorization,
2026-10-06, Stage 2 only. First delivery: commit `7fcf78d`. GPT's own
verdict: CHANGES REQUIRED (seven defects, listed below). First
corrections: commit `8877551`. GPT's own verdict on THAT delivery:
STILL CHANGES REQUIRED (two further defects, listed below). Second
corrections: commit `0bdabe5`. GPT's own verdict on THAT delivery: the
`effective_as_of` fix ACCEPTED and CLOSED; one further admission-
identity defect found. Third corrections: commit `fd992db`. **GPT's
own verdict on THAT delivery: ACCEPTED**, confirmed by independent
execution (same artifact with different metadata produces distinct
`admission_id`s; both snapshots remain accessible and unchanged;
repeating the same admission is idempotent; `CalendarVerificationRecord.
admission_id` points to the exact admission used; an unknown identity
is refused). All on `claude/spec004-audit`. A non-blocking follow-up
GPT raised on this same delivery -- `_compute_admission_id()`'s
serialization -- is fixed under the separate delta below, not a
reopening of this acceptance. **What ACCEPTED does NOT cover:** `#003`
v2 output's compatibility with `#005`'s own identity verifier (stayed
OPEN until the delta below); a real, genuinely-attested calendar for
actual formal runs (B3, still operationally blocked); any other stage.**

**Seven corrections applied this round, per GPT's own changes-required
review -- none of these are new decisions, all are fixes to already-
authorized Stage 2 mechanics:**
1. `run_evaluation()` now REQUIRES `calendar_registry`/`calendar_id`
   together whenever `mode == "FORMAL_DEVELOPMENT"` (previously both
   omitted silently fell back to the legacy path, bypassing B1
   entirely).
2. `_build_baseline_pool()`/`_evaluate_signature_horizon()` now thread
   `calendar=`/`effective_as_of=` into every `compute_forward_outcome()`
   call (previously the resolved calendar reached session-date/bin
   resolution and the run-id fingerprint, but NOT the actual return
   calculation).
3. A new `effective_as_of = min(data_as_of, development_end)` bounds
   every PIT bar fetch in the engine (previously `data_as_of` reached
   `_fetch_bars_by_security()`/`_resolve_session_dates_from_calendar()`
   unbounded, reading data beyond `development_end` before any OOS
   classification occurred).
4. `CalendarRegistry.register_verified()` now takes the
   `AdmittedCalendarSource` itself and executes the admit->verify
   chain internally, building the `CalendarVerificationRecord` itself
   (previously it accepted a caller-built record on faith -- GPT
   reproduced a hand-built record with an invented digest and blank
   verifier/timestamp being accepted).
5. The registry's storage is now one dict of an indivisible entry, one
   atomic assignment (previously two successive dict writes -- GPT
   reproduced an injected failure at the second write leaving a
   calendar registered with zero records).
6. `MissingnessReport` gained a `data_gap` field, counted by
   `_missingness_from_outcomes()` (previously `DATA_GAP` outcomes were
   invisible to the reconciliation sum).
7. The v2/#005 incompatibility is now demonstrated by a real test, not
   only claimed in a comment; `EvaluationRunRegistry` retains the
   fields needed to recompute a v2 id. The fix to #005's own
   `verify_evaluation_run_identity()` itself remains a minimal-delta
   proposal, NOT implemented (Spec #005-side code, out of this stage's
   scope) -- see this stage's own "Explicitly NOT done" paragraph
   below for the exact delta.

**Two further corrections applied this round, per GPT's own SECOND
changes-required review -- again, fixes to already-authorized Stage 2
mechanics, not new decisions:**
1. `CalendarRegistry.register_verified()` no longer accepts an
   `AdmittedCalendarSource` object directly -- GPT reproduced a
   hand-built object (`admission_method="APPROVED_PROVIDER"`, a
   source NOT on the allow-list) that was accepted and resolved
   through the gate successfully, since digest/coverage/session
   self-consistency checks only prove the object agrees with itself,
   never that it actually passed Step 0's own admission rules. A new
   `AdmissionRegistry` (`admission.py`) is now the ONLY place an
   `AdmittedCalendarSource` can come from; `admit_source_via_approved_
   provider()`/`admit_source_via_operator_attestation()` write into it
   internally, and `register_verified()` now takes `(calendar,
   admission_registry, admission_id)`, resolving the admitted source
   by its own content-addressed digest.
2. `_resolve_session_dates_from_calendar()` now ALSO filters its
   returned session-date list by `effective_as_of`, not only by
   `development_end` (previously, whenever `data_as_of <
   development_end`, this list could still include calendar sessions
   after the run's own declared vantage point; `_collect_
   observations()` then called Discovery once per date in it, and
   Discovery performs its OWN PIT reads as of each one -- GPT
   reproduced Discovery reading dates past `data_as_of` with extracted
   functions and observed call arguments). The FULL calendar object
   used separately for target-session resolution and OOS/not-yet-
   reached classification is never truncated by this bound -- only the
   observation-dates list is.

**One further correction applied this round, per GPT's own THIRD
changes-required review -- again, a fix to already-authorized Stage 2
mechanics, not a new decision (the `effective_as_of` fix above was
independently reconfirmed and CLOSED by GPT this same round):**
1. `AdmissionRegistry` no longer keys its entries by `artifact_digest`
   alone -- GPT reproduced, through the public API alone, two
   LEGITIMATE admissions of the identical raw text under different
   metadata (admission A: source A, coverage to 2024-01-31; admission
   B: the same text, source B, coverage to 2024-12-31) both
   succeeding, with the second silently overwriting the first's
   retained snapshot (resolving A's own original identity returned B's
   metadata instead). `AdmittedCalendarSource` now carries a separate
   `admission_id` field, computed by binding the artifact's digest to
   every field that distinguishes one admission DECISION from another
   (source, method, version, publication, coverage, market, timezone,
   attestation); `AdmissionRegistry` keys and resolves by
   `admission_id`, never the bare digest. Two admissions of the same
   text with different metadata now get different ids, BOTH retained;
   the identical admission repeated is idempotent.
   `CalendarVerificationRecord` gained an `admission_id` field, pinning
   the EXACT admission decision used, not merely the shared raw text.

See registry revision 10 (`docs/decision_sheet_003_004_2026-10-05.md`)
for the full finding-by-finding detail across all three rounds. The
text below this point describes the stage as authorized and as first
delivered; corrections are layered on top, not a rewrite of the
original scope.

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

**Acceptance criteria -- met, after all three correction rounds.** The
admission/registry regressions (direct construction without a record
refused; an admitted source tampered with after admission rejected;
coverage incompatible with the admitted source rejected; a genuine
session discrepancy rejected before registration; blank verifier/
timestamp rejected; a failed registration leaves no partial state AND
preserves a pre-existing entry; a valid case resolves from registry;
a directly-constructed `AdmittedCalendarSource` for an unapproved
provider refused; a nonexistent `admission_id` refused; content+digest
changed together after admission cannot replace the admitted
snapshot; NOW ALSO: the SAME text admitted twice under DIFFERENT
metadata gets distinct identities, both snapshots retained, with the
calendar's own record tied to the one actually used; the identical
admission(+registration) repeated is idempotent) -- run against
FIXTURE artifacts per B3's current, still-blocked real-source status,
through the THREE-TIMES-CORRECTED `register_verified()` gate, which
resolves its admitted source EXCLUSIVELY via `AdmissionRegistry`/
`admission_id` (now the admission DECISION's own identity, distinct
from the raw text's `artifact_digest`), never a directly-supplied
object; a FORMAL_DEVELOPMENT run with the calendar OMITTED now REFUSES
before any data access, with exactly one argument supplied also
refused, and an unregistered id also refused; a `SYNTHETIC_TEST_
FIXTURE` calendar refused and an `OFFICIAL_VERIFIED` one accepted;
B2's DATA_GAP test, including a real end-to-end engine regression
proving DATA_GAP is counted in the reconciliation; target-session
index-arithmetic regressions; SEPARATE regressions confirming two runs
differing only in `security_ids`, only in `benchmark_security_id`, only
in `data_as_of`, only in `horizons`, and only in `run_id_scheme_
version` each produce different `evaluation_run_id`s (five
independent-axis checks, not one); B4's byte-identical relocation
regression plus the `evaluation` -> `backtest` import-direction guard
test; a real `run_evaluation()` output confirmed to actually fail
#005's own legacy identity recompute; a real `run_evaluation()` call
with `data_as_of < development_end` proving EVERY PIT read this run
performs -- direct AND Discovery-triggered alike -- never requests a
date past `effective_as_of` (independently reconfirmed by GPT and
CLOSED this round), while CROSSES_LOCKED_OOS/INSUFFICIENT_FUTURE_DATA
classification (which depends on the full, untruncated calendar)
still works correctly.

**Verified: `tests/data_foundation/` (34 tests: admission incl. the
V1-always-rejects-even-a-plausible-identifier case, the `Admission
Registry`-mediated admit->record->resolve contract, AND the same-text-
different-metadata/idempotent-repeat regressions; source verification;
the corrected atomic registry's own regressions incl. the admission-
bypass regressions and the same-text-different-metadata/idempotent-
repeat pair run through the full admit->verify->register chain;
relocation-identity + `evaluation`->`backtest` import guard);
`tests/spec003/test_42_calendar_aware_target_session_resolution.py`
(11 tests, unchanged by any round's corrections); `tests/spec003/
test_43_run_identity_fingerprint_s2.py` (5 tests, run through the
mandatory-calendar path); `tests/spec003/test_44_formal_development_
calendar_strictness.py` (5 tests: both arguments omitted, one supplied
alone, an unregistered id, SYNTHETIC_TEST_FIXTURE refused, OFFICIAL_
VERIFIED accepted); `tests/spec003/test_45_data_gap_missingness_
reconciliation.py` (1 test: a real two-security universe with a
genuine DATA_GAP, reconciled through run_evaluation()); `tests/spec003/
test_46_v2_run_id_incompatible_with_005_legacy_recompute.py` (1 test:
a real v2 registry fails #005's own recompute, concretely);
`tests/spec003/test_47_effective_as_of_bounds_discovery_triggered_
pit_reads.py` (1 test: intercepts the shared `data_foundation.pit.
access` module object that both `evaluation.engine` and `discovery.
engine` call through, asserting zero PIT reads past `effective_as_of`
while confirming OOS classification correctness -- verified as a
genuine regression by deliberately reverting the fix and observing
the test fail with concrete offending dates, then restoring it; GPT
independently repeated this reproduction and confirmed it CLOSED).
Every pre-existing FORMAL_DEVELOPMENT test in `tests/spec003/` and
every pre-existing admission call site in `tests/` updated to the new
`AdmissionRegistry`-mediated, `admission_id`-keyed pattern.
`tests/spec005/` re-run unchanged: 419 passed. Full project suite
(`pytest tests/`): 806 passed, 1 skipped (pre-existing, unrelated) --
zero regression across all three correction rounds' own baselines
(789 -> 798 -> 802 -> 806).**

**Explicitly NOT done this stage, carried forward as-is:** `#005`'s own
adoption of `CalendarRegistry` (B5, separate, not authorized); a real,
genuinely-attested `OFFICIAL_VERIFIED` calendar for actual formal runs
(B3's real-source gap, unchanged, operationally blocked); episode
formation's own `bar_dates` convention (security-own bar-index gap
measurement, documented in `build_episodes()`'s own module docstring)
-- verified this round per GPT's own request but deliberately left
unchanged, a separate, undecided statistical-convention question not
named in Stage 2's scope. **Corrected this round (was previously
listed as not done, now IS done):** the calendar-aware `compute_
forward_outcome()` path now DOES drive every forward-return
computation `run_evaluation()` performs when a calendar is resolved
(fix #2 above) -- this is no longer a gap. **The `backtest/provenance/
evaluation_run.py` `LEGACY_RUN_ID_FIELDS` consequence (registry I1),
previously demonstrated by a real test (fix #7) but left unfixed, is
NOW IMPLEMENTED -- see the `#003` v2 -> `#005` compatibility delta
section below, separately authorized 2026-10-07 and delivered at
`483761a`.** This delta did not require `#005` to adopt
`CalendarRegistry` and did not reopen Batch 3 -- both remain exactly
as stated above.

---

## Minimal `#003` v2 -> `#005` compatibility delta

**IMPLEMENTED, commit `483761a` on `claude/spec004-audit`, delivered
for GPT's next review -- NOT yet itself reviewed. Radu's explicit
authorization, 2026-10-07, scoped to EXACTLY this delta: does NOT
resume Batch 3, does NOT adopt `CalendarRegistry` into `#005`, does NOT
authorize any other stage.**

- `backtest/provenance/evaluation_run.py`'s `verify_evaluation_run_
  identity()` now dispatches by the registry's own `run_id_scheme_
  version`, rather than recomputing only the legacy 8-field recipe:
  - `None` (every registry predating the S2 fingerprint change): the
    ORIGINAL 8-field legacy recipe (`LEGACY_RUN_ID_FIELDS`), UNCHANGED
    -- every historical identity verifies exactly as before, declared
    explicitly per Radu's own instruction, not silently reinterpreted.
  - `"v2"` (registry I1's own field set): a NEW 14-field recipe
    (`V2_RUN_ID_FIELDS` = the 8 legacy fields plus `security_ids`,
    `benchmark_security_id`, `data_as_of`, `horizons`, `calendar_id`,
    `run_id_scheme_version`), reconstructed by `recompute_v2_
    evaluation_run_id()` EXACTLY as `run_evaluation()` itself feeds
    `build_run_id()` -- including re-sorting `horizons`, which the
    registry retains in its original, possibly-unsorted input order
    (`EvaluationRunRegistry.horizons` vs. the sorted tuple actually
    hashed). A registry claiming `"v2"` with a required field
    (`security_ids`, `benchmark_security_id`, `data_as_of`) still at
    its pre-Stage-2 backward-compat default is refused BEFORE any hash
    comparison, with an explicit "required field" error -- `calendar_
    id=None` is deliberately NOT treated as missing, since a genuine
    v2 run legitimately carries it (EXPLORATORY mode without a
    resolved calendar).
  - anything else: refused outright, with NO fallback to the legacy
    recipe -- a v2 claim that fails its own check is never re-tried
    against the 8-field one (proven by a dedicated regression: a v2-
    scheme registry whose id happens to match the LEGACY recipe is
    still refused).
- `data_foundation/calendar/admission.py`'s `_compute_admission_id()`
  now serializes as canonical JSON (sorted keys, no whitespace)
  instead of `"\x1f".join()` -- a non-blocking follow-up GPT raised on
  commit `fd992db`: a field value containing the `\x1f` separator could
  shift the apparent field boundary, producing the SAME preimage for
  two DIFFERENT field splits (not an sha256 collision -- a
  serialization ambiguity; `AdmissionRegistry._record()`'s own equality
  check already refused to let this overwrite an existing entry, so it
  was never a live bypass). **Effect on existing identities, declared
  explicitly:** every `admission_id` value changes versus the prior
  scheme, for every input, not only the colliding ones -- the preimage
  format itself changed. `AdmissionRegistry` is in-memory, per-run
  only, never persisted anywhere, so nothing stored is invalidated.

**Acceptance criteria -- met.** A REAL `run_evaluation()` v2 output is
accepted by `#005`'s own identity check (`tests/spec003/test_46_v2_
run_id_accepted_by_005_identity_check.py`, rewritten from its prior
form, which by design asserted the opposite before this
authorization); every historical identity still verifies unchanged
(`tests/spec005/test_01_legacy_hash_recompute.py`, untouched, still
passing); the exact separator-collision case GPT reproduced now
produces distinct `admission_id`s (`tests/data_foundation/test_01`'s
own new regression).

**Verified: `tests/spec005/test_41_v2_evaluation_run_identity.py` (11
new tests: genuine v2 registry accepted; tamper detection on
`security_ids`/`calendar_id`; only-the-14-fields-affect-the-hash;
horizons-sorted-before-hashing, with a naive-unsorted-recompute proof
that the sort step is load-bearing; `calendar_id=None` accepted as
legitimate; missing `security_ids`/`data_as_of` each refused before
any hash check; an unknown `run_id_scheme_version` refused outright;
a v2-scheme registry whose id matches the legacy recipe still refused,
proving no silent fallback). `tests/spec003/test_46_...py` (rewritten,
1 test: a real `run_evaluation()` v2 output now accepted).
`tests/data_foundation/test_01_calendar_admission.py` (+1: the exact
separator-collision case, now resolved). Full project suite (`pytest
tests/`): 818 passed, 1 skipped (pre-existing, unrelated) -- zero
regression from the pre-delta baseline of 806. `tests/spec005/` now
430 passed (was 419 -- the +11 are this delta's own authorized
`#005`-side tests).

**Explicitly NOT done by this delta:** `#005`'s own adoption of
`CalendarRegistry` (B5, separate, still not authorized); Batch 3
(unaffected, not reopened); a real, genuinely-attested `OFFICIAL_
VERIFIED` calendar for actual formal runs (B3's real-source gap,
unchanged); the G2 out-of-sample confirmation protocol (unscoped,
unchanged); any stage beyond what is already authorized above.

---

## Stage 3 -- Config identity infrastructure (shared #003 + #004)

**IMPLEMENTED at commit `8650f17`; CORRECTED twice after GPT's own
CHANGES REQUIRED verdicts on exactly that commit (round 2, `955f482`)
and then on the round-2 delivery itself (round 3, this revision) --
delivered again for GPT's next review, NOT yet itself reviewed. Radu's
explicit authorization, 2026-10-07, scoped to exactly this stage per the
already-accepted plan below: applied to Discovery, Evaluation,
Hypothesis's preregistration gate, AND Research Queue -- does NOT
resume Batch 3, does NOT adopt `CalendarRegistry` into `#005`, does
NOT authorize Stage 4 or any other stage.**

**GPT's four findings on `8650f17`, and the correction applied to
each:**
1. Protection was opt-in (`if config_registry is None: return config`,
   a no-op passthrough) -- GPT reproduced, through a real `build_
   research_queue()` call, that a content-only tamper under the same
   `config_version` silently changed eligibility results whenever
   `config_registry` was omitted. **Fixed: mandatory by default.**
   Every consumer now creates a local, throwaway `ConfigRegistry()`
   when none is shared, and verifies against it unconditionally --
   `config_registry` is optional ONLY for sharing one verified baseline
   ACROSS multiple calls, never for opting into verification at all.
2. The first `register_or_verify()` call for a domain trusted whatever
   (version, content) pair the caller's object merely claimed -- even a
   brand-new registry would silently adopt an already-tampered config
   as truth on first use. **Fixed:** each domain's loader (`discovery/
   config/loader.py`, `evaluation/config/loader.py`, `hypothesis/
   config/loader.py`) now exposes `raw_texts: tuple[str, ...]` directly
   on its config dataclass, plus a pure `reparse_raw_texts()` function
   -- the EXACT parse+hash code `load_config()` itself uses, extracted,
   with no disk I/O. Every consumer reparses the CANDIDATE's own `raw_
   texts` independently and verifies the candidate's claimed label/
   content against THIS re-derived ground truth, BEFORE it is ever
   registered anywhere -- a tampered object is rejected by self-
   consistency, never trusted as a "first use" baseline.
3. `ConfigRegistry.register()` was public and unconditional -- a later
   call could silently overwrite an already-registered domain. **Fixed:**
   `register()` is no longer public; `register_or_verify()` is the ONLY
   write path (idempotent on identical re-registration, rejecting a
   different one, keeping the original). At the Hypothesis gate
   specifically, the tie between "the config pinned for this operation"
   and "verifying it is still active" now runs through this SAME
   `register_or_verify()` call unconditionally (a local-or-shared
   registry), not only when `config_registry` happened to be supplied.
4. `freeze()` fell through unchanged for an externally-supplied
   `MappingProxyType` (not a `dict` subclass, so `isinstance(value,
   dict)` missed it) -- a nested mutable list inside one stayed mutable
   after "freezing." **Fixed:** `freeze()` recurses into `dict` and
   `MappingProxyType` identically; any other unrecognized type (e.g. a
   bare `set`) is explicitly rejected with `ConfigIdentityError` rather
   than passed through.

New shared module `src/config_identity/registry.py`: `freeze()`/
`normalize_for_comparison()` (full recursive freeze -- `dict` ->
`MappingProxyType` of recursively-frozen values, `list`/`tuple` ->
`tuple` of recursively-frozen elements, never `MappingProxyType` alone,
which leaves a nested list mutable -- and the matching normalization
used to compare a frozen snapshot against an unfrozen candidate);
`RegisteredConfigVersion.verify()` (the two SEPARATE checks -- label,
structural-equality content -- exactly as designed, neither
substituting for the other); `ConfigRegistry.register_or_verify()`
(the first call for a domain registers it as the operation's own
pinned baseline; a later call sharing the same registry verifies its
candidate against THAT baseline, raising before any computation on a
mismatch). `config_version` itself is NEVER recomputed -- always the
unchanged loader's own output, including Discovery's own multi-source
`sha256("".join(raw_texts))[:12]` combination rule, preserved
byte-for-byte.

Wiring: each consumer takes a `config_registry` parameter, still
optional and defaulting to `None`, but its role is now "share one
verified baseline across calls," never "opt into verification at
all" -- omitting it makes the consumer build a local, throwaway
`ConfigRegistry()` and still verify against it, every call:
- **Discovery**: `compute_discovery_observations()`/`run_discovery()`
  reparse the candidate `config`'s own `raw_texts` independently,
  verify self-consistency, then register-or-verify the "discovery"
  domain against the (local-or-shared) registry, consuming exclusively
  the frozen `DiscoveryConfig` rebuilt from it.
- **Evaluation**: `run_evaluation()` does the same, for BOTH
  "discovery" and "evaluation" domains, once at the top;
  `_collect_observations()`'s own Discovery calls now receive the SAME
  registry, so they verify against the identical pinned baseline
  rather than a second, independent local one.
- **Hypothesis's preregistration gate**: `preregister_hypothesis()`
  still performs a MANDATORY (unconditional) live re-read of
  `hypothesis.yaml` on EVERY call, verifying the caller-supplied
  `hypothesis_config` against that fresh read before any of the
  existing checks run; `validate_for_preregistration()` then consumes
  exclusively this freshly-verified, frozen snapshot. The fresh read is
  now ALSO registered-or-verified against a local-or-shared registry
  unconditionally (round-2 fix for finding #3), not only when `config_
  registry` happened to be supplied. `hypothesis_config`'s own type
  stays `HypothesisConfig` (unchanged from the first delivery).
- **Research Queue**: `build_research_queue()` reparses the candidate
  `config`'s own `raw_texts`, verifies self-consistency, then
  registers-or-verifies the "hypothesis" domain against a local-or-
  shared registry -- unconditionally now, closing the exact bypass GPT
  reproduced here. TEST 50's own deliberately-different config scenario
  is unaffected ONLY because it is now genuinely loader-sourced (`tests/
  fixtures/config_overrides.py`), never because verification is
  skipped.

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

**Acceptance criteria, corrected this round (per GPT's own decision,
relayed by Radu): the mismatch case has exactly ONE outcome, not two.**
A config object whose label OR content is incompatible with the
registered snapshot MUST BE REJECTED before Research Queue construction
proceeds -- reporting the discrepancy and continuing the computation
does NOT satisfy this invariant; "rejects OR correctly reports" is not
an acceptable pair of alternatives. The correct-content-wrong-label case
rejected by the label check specifically; the correct-label-wrong-
content case rejected by structural equality specifically, both sides
normalized before comparing -- the two mismatches verified as TWO
SEPARATE regressions, not one combined "mismatch" case, mirroring the
preregistration gate's own discipline. Once verified, the operation
uses EXCLUSIVELY the frozen, registered snapshot -- never a second,
independently-loaded config object, for `build_research_queue()` any
more than for the preregistration gate.

**Acceptance criteria -- met, round 2.** Every regression required,
verified through REAL consumers, not only the shared helper: a
legitimate config (accepted); a correct-content-wrong-label object
(rejected by the label check specifically); a correct-label-wrong-
content object (rejected by the structural-equality check specifically,
both sides normalized before comparing); a directly-constructed,
inconsistent object (rejected, both checks firing); a nested
modification (recursive freeze proven two levels deep, and proven to
survive a source mutation after freezing); a config source changed
after registration (rejected, keeping the original, including through
the preregistration gate's own mandatory live re-read, simulated with a
monkeypatched, later-changed disk read against an earlier, explicit
registration). **New this round, closing GPT's four findings
specifically:** a tampered config rejected on the VERY FIRST call with
a BRAND-NEW `ConfigRegistry()` (finding #2, Discovery/Evaluation/
Research Queue); the SAME tamper rejected with NO `config_registry` at
all (finding #1 -- the exact bypass GPT reproduced, now closed; the
test that previously MANDATED this bypass has been REMOVED, not merely
modified, from `tests/spec002/test_25`, `tests/spec003/test_48`,
`tests/spec004/test_75`); a rejected attempt to replace an already-
registered reference, including with a totally unrelated replacement
(finding #3); `ConfigRegistry` confirmed to have no public `register()`
(finding #3); a `MappingProxyType` wrapping nested mutable lists,
mutated after "freezing," proven isolated (finding #4); an unsupported
mutable type (`set`) explicitly rejected by `freeze()` (finding #4).
Historical identities are preserved exactly as the already-accepted
contract requires -- `config_version` is never reinterpreted or
recomputed anywhere in this stage; it is now additionally RE-DERIVED
independently (never trusted from a claim) via each domain's own
`reparse_raw_texts()`.

**Legitimate alternative test configs, now genuinely loader-sourced.**
`tests/spec003/conftest.py`'s `reduced_discovery_config`/`fast_
evaluation_config`, plus 7 further pre-existing files that built a
deliberately-different config via `dataclasses.replace()` while keeping
the original label (`tests/spec002/test_15/16/23/24`, `tests/spec003/
test_33/43/45/47`, `tests/spec004/test_50`) -- exactly the shape
mandatory self-consistency now correctly rejects -- rewritten through a
new shared helper, `tests/fixtures/config_overrides.py`: re-serializes
the overridden section back to real YAML text and reparses via
`reparse_raw_texts()`, no disk I/O beyond the one real initial load.
Two honest, non-regression side effects, asserted explicitly rather
than hidden: `candidate_budget` (Discovery) and `horizons`/`support`
(Evaluation) are part of their file's own real content, so changing
them now genuinely changes `config_version`/`family_id` even though
they have zero effect on the statistical output -- `tests/spec002/
test_24` and `tests/spec003/test_33` updated to compare explicit-
ly excluding those identity-dependent fields, while separately asserting
the identity genuinely differs.

**Verified: 61 tests across the 5 touched/new Stage-3 files** (up from
31 at the first delivery -- net new this round: 3 removed [the bypass-
mandating tests], 9 added). `tests/config_identity/test_01_registered_
config_version.py` (17: the shared mechanism in isolation, plus
`MappingProxyType`-with-nested-lists, unsupported-mutable-type-
rejected, no-public-register, reject-unrelated-replacement). `tests/
spec002/test_25_config_identity_gate.py` (6: real `run_discovery()`/
`compute_discovery_observations()` consumers, including first-call-
tampered-with-fresh-registry and first-call-tampered-with-no-registry).
`tests/spec003/test_48_config_identity_gate.py` (6: real `run_
evaluation()` consumer, same two new cases). `tests/spec004/test_74_
config_identity_gate.py` (6: real `preregister_hypothesis()` consumer,
unchanged in count -- its existing no-config_registry negative tests
already exercised the corrected design). `tests/spec004/test_75_
research_queue_config_identity_gate.py` (6: real `build_research_
queue()` consumer, same two new cases, the one GPT used for its own
concrete reproduction). Verification discipline applied (this
engagement's established practice): the pre-round-2 bypass was
temporarily restored in `discovery/engine.py`, confirmed the new
no-registry regression test actually FAILS against it, then the fix
was restored. Full project suite (`pytest tests/`): **859 passed, 1
skipped** (pre-existing, unrelated) -- zero regression from the
round-1 baseline of 849.

**Round 3 (this revision) -- GPT's own CHANGES REQUIRED verdict on the
round-2 delivery (`955f482`): the four round-2 findings are confirmed
fixed; one further defect remained, reproduced through the real gate.**
A draft built under config A, preregistered while BOTH the caller-
supplied `hypothesis_config` AND the live file itself (simulated via
monkeypatch) had already moved to a genuinely different, self-
consistent config B, with NO `config_registry` shared to catch the
drift -- was wrongly ACCEPTED: checks (a) (candidate vs. fresh read)
and (b) (fresh read vs. an EXPLICITLY shared earlier registration)
each only prove a different kind of "honest now," neither ties the
gate back to the SPECIFIC snapshot the draft itself was built under.
**Fixed:** a third, unconditional check (c) -- `draft.strategy_config_
version` (recorded on the draft at construction time, travelling with
the object, no new parameter needed) must equal the active, verified
config's own version; a mismatch is refused before any of the existing
checks and before any registry write. Does NOT replace check (b), per
GPT's own instruction -- the two are complementary: (c) uses the
draft's own self-declared anchor and needs no sharing at all; (b)
catches drift across calls that explicitly share one registry.
Verification discipline applied: the new check was temporarily removed,
confirmed the two tests that depend on it exclusively (no shared
registry) FAIL -- including GPT's own exact reproduction -- while the
shared-registry variant still passes via mechanism (b) alone, then the
fix was restored. **4 new regressions** (`tests/spec004/test_74_
config_identity_gate.py`, whose `_gate()` helper gained a `draft_
config` parameter, separate from `hypothesis_config`, so a test can
build the draft under one config and call the gate with another): no
initial context -> rejected; initial context A shared -> rejected for
the active-config change; A unchanged with context A -> accepted
(sanity); a draft whose recorded version disagrees with the active
snapshot -> rejected before any write (`HypothesisRegistry.all_
hypotheses() == ()` confirmed). Full project suite (`pytest tests/`):
**863 passed, 1 skipped** (pre-existing, unrelated) -- zero regression
from the round-2 baseline of 859.

**Explicitly NOT done by this stage:** `#005`'s own adoption of
`CalendarRegistry` (B5, separate, still not authorized); Batch 3
(unaffected, not reopened); a real, genuinely-attested `OFFICIAL_
VERIFIED` calendar for actual formal runs (B3's real-source gap,
unchanged); the G2 out-of-sample confirmation protocol (unscoped,
unchanged); Stage 4 onward (not authorized).

---

## Stage 4 -- #003 statistics AND its #004 consumers, delivered as one bundle

**Depends on Stage 2 (same calendar-resolved session dates feed
bootstrap/bin assignment).** **A3 corrected this round, per GPT's own
decision, relayed by Radu: A3 is no longer a narrow `baseline_iqr`-only
fix layered beside an unchanged `stratified_baseline_point_estimate()`.
That function's own signature receives only `(date, value)` pairs, with
NO security identity -- it cannot implement per-security weighting at
all, for any statistic, regardless of what `stat` callable is passed
in. Keeping it unchanged does not defer F4+F5 for the reported baseline
mean/median, it fails to deliver F4+F5 for them.** A4 remains a SIBLING
of A3 (both consume the ONE pooled weighted distribution below; neither
depends on the other). A4's own `exchangeability_status` field (#003)
and its #004 consumers ship TOGETHER inside this same stage -- not
deferred to Stage 8.

- F2a/F2b (frozen signature-set content/id verification; duplicate
  `signature_id` rejection) and F6 (`family_test_count`) -- design-
  complete, section 9.
- **A2:** `session_mass` diagnostic (measurement only).
- **F4+F5's own per-security weighting formula, now actually wired
  into the baseline's own point estimate (the gap this round closes):**
  `stratified_baseline_point_estimate()`'s own signature changes to
  accept security identity (or pre-computed per-row weights), and its
  internal algorithm changes from "per-bin PLAIN stat, then bin-
  weighted-average" (today's Level 1) to building ONE pooled weighted
  distribution across every eligible row, each row carrying its own
  `W_b/(k_b*n_i,b)` weight.
- **A3:** that ONE pooled weighted distribution feeds `baseline_mean`
  (weighted mean), `baseline_median` (weighted Q(0.5)), AND `baseline_
  iqr` (Q(0.75)-Q(0.25)) TOGETHER -- midpoint convention with mandatory
  tie-aggregation (section 4.1/4.2) for both quantile-based statistics,
  replacing today's unweighted `robust_iqr()` call AND the Level-1
  mechanism in one change, not two separate ones. Does not touch the
  signature's own unweighted `DescriptiveStats`.
- **Bootstrap/CI and the permutation estimator (A4) now explicitly
  consume this SAME corrected baseline computation, per GPT's own
  instruction that they must correspond to the reported mean:** the
  per-replicate weighted estimator (recompute `k_rep`/`n_i_rep` from
  EACH replicate's own composition, applying the SAME weight formula
  with replicate-local values) stays the mechanism that consumes
  weights for bootstrap; interval construction from the `B` replicate
  statistic values is the UNWEIGHTED `2.5`th/`97.5`th percentile of
  those plain numbers. The permutation test's own "observed difference"
  draws from this SAME pooled weighted `baseline_mean`, never a
  separately-computed row-mean.
- **A1:** F3 common support, (a) UNAVAILABLE -- full comparison
  blackout on partial OR zero common support; signature's own full-
  population `DescriptiveStats` unaffected.
- **A4, #003 side:** weighted-permutation estimator mechanics; new
  `exchangeability_status` field on `BaselineComparison`, hard-coded
  `"UNVERIFIED"`, propagated to `DecayPoint` and `EvidencePacket.
  primary_exchangeability_status` (registry A4).
- **A4, #004 side, SAME bundle, corrected this round -- UNCONDITIONAL,
  not a status-conditioned branch (per GPT's own decision: a "no
  constructor argument" check does not prove authenticity, and is
  rejected):** `evidence/queue.py`'s `compute_review_priority()` sets
  `p_key = float("inf")` UNCONDITIONALLY for V1 -- it does not read or
  branch on `exchangeability_status` at all, so no value that field
  could ever hold (including an artificially-injected `"VERIFIED"`)
  changes the ranking. `tests/spec003/generate_report_artifacts.py` and
  `tests/spec004/generate_report_artifacts.py` updated to print the
  qualifier or label the figure as diagnostic-only wherever `adjusted_
  p`/`standardized_effect` appear.

**Acceptance criteria.** F2a/F2b/F6 regressions (section 9); the
WEIGHTED `session_mass` reproducing the 5%/95% split, regression-
locking the raw-`Counter` wrong answer; **the numeric regression
closing this round's gap, verified by direct computation (`python3`,
exact fractions) -- one bin, security A values `[0,2]`, security B
value `[4]`, weights `[1/4,1/4,1/2]`: today's row computation gives
mean `2.0`/median `2.0`; the corrected pooled weighted computation
gives mean `5/2 = 2.5`, median `8/3`, Q1 `1`, Q3 `4`, IQR `3` -- locked
as an exact-fraction test, with a SEPARATE assertion that `baseline_
median` and `baseline_iqr`'s own Q1/Q3 are read from the IDENTICAL
pooled set, not two independently-built distributions;** weight-
rescaling invariance (>= 3 scale factors) and the tie/weight-
permutation matrix applied to this one mechanism; A1's partial-support
regression (full blackout, descriptive stats intact) plus the zero-
support degenerate case; the exhaustive-enumeration permutation
regression (signature `[8]`, baseline `[0,2]`/`[4]`, weights
`[1/4,1/4,1/2]`, observed `5.5`, exact `p = 8/24 = 1/3`) kept distinct
from any Monte Carlo estimate; the equal-weight case verified byte-
identical to today's existing `stratified_permutation_p_value()` test;
the FULL integration regression (real `run_evaluation()` -> `build_
evidence_packet()` -> `compute_review_priority()`, never a hand-built
packet); **BEHAVIORAL tests, replacing the rejected structural-
signature check:** `exchangeability_status` absent/`None`, an unknown
string, and an artificially-injected `"VERIFIED"` (via `dataclasses.
replace()`) ALL leave `p_key = inf` and rank NO HIGHER than `adjusted_p
= None` would -- three cases, not one structural scan.

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

**Readiness note, per Radu's own closing instruction this round: stages
independent of Stage 4 stay technically prepared as stated -- the whole
package is not declared accepted ahead of this round's own Stage 4/
Stage 1/Stage 3 adjustments being checked.** Stages 2, 5, 6, 7 have no
dependency on Stage 4 and are unaffected by this round's corrections.
Stage 8 depends on Stage 4's `EvidencePacket` structure but not on its
own A3/A4 numeric corrections specifically (Finding 18/20 are
unaffected). Stage 4 itself and Stage 1/Stage 3 (both corrected this
round) should be read as freshly revised, not as previously-verified
and merely restated.

**Authorization.** Every stage above is a PROPOSAL for sequencing
already-decided design work. No stage may begin until Radu explicitly
authorizes implementation. Findings reconciliation remains CLOSED (both
specs, within each review's own declared scope); the calendar admission/
trust contract (revision 11, section 2) remains CLOSED and unmodified.
Baseline `3cdc532`, historical acceptances, and the Spec #005/Batch 3
pause are unchanged.
