# Joint Remediation Design -- Spec #003 + Spec #004 (2026-10-04, revision 9)

**Status: DESIGN ONLY. Implementation NOT AUTHORIZED.** Revision 9 is
a targeted correction of revision 8 (not a full rewrite -- revision 8's
config-verification fix, the S2 hash-preimage placement, and the
exhaustive-enumeration permutation regression are all confirmed closed
by Radu, with three further LOCAL alignments requested, not a
reopening). This round does three things: (1) three local corrections
to the config-verification mechanism's own wording (its justification
for choosing the mandatory live re-read was wrong about WHY design (a)
is less complete, not that it is unsafe; the content-equality check
needs both sides normalized to the SAME list/tuple representation
before comparing, or it is meaningless; the two distinct rejection
cases -- wrong label/right content vs. right label/wrong content --
were attributed to the wrong check in the regression text); (2) the
PRIORITY design work Radu explicitly asked for -- F1's calendar
source, verification, coverage, and provenance are now fully specified
by reusing Spec #005's own already-implemented, content-addressed
`TradingCalendar` contract (confirmed by reading `calendar.py` in
full), rather than inventing a parallel mechanism, moving F1 from
"still incomplete" into "design complete, awaiting approval," with
exactly one remaining, precisely-named contractual choice (the
strictness tier); (3) a new methodological-choices table (within
section 11's decision list), each with its own stated recommendation
and concrete consequence, kept explicitly separate from implementation
approval, per Radu's own explicit request -- common support, within-
bin weighting, the quantile convention, permutation exchangeability,
and the newly-added calendar strictness choice. This review concerns
remediation DESIGN only; it does not reopen findings reconciliation
(closed, both specs, within each review's own declared scope) and does
not authorize implementation.

**Checklist convention used throughout (Radu's own structure):** every
item is tracked on four separate axes, never collapsed into one
"status": **(a) design completeness** -- is a concrete, correct
mechanism specified; **(b) contractual decision** -- is there a
semantic/behavior choice only Radu can make; **(c) Radu's approval** --
not given by this document, tracked separately per item in section 11;
**(d) implementation + verification** -- a LATER, NOT-YET-AUTHORIZED
stage; "implement and run the regression matrix" is a goal FOR that
later stage, never a precondition for finishing (a).

---

## 1. F1 -- one target session for both classification and the return
calculation

### 1.1 The coherence requirement

Given calendar sessions (price-independent, see section 2),
`horizon_bars = N`, and an entry at session `T_entry`: compute
`T_target` = the session `N` steps forward from `T_entry` on the
calendar. **`T_target` is used for BOTH the OOS/not-yet-available/
data-gap classification below AND as the ONLY session whose bar may be
used for the return calculation.** The current implementation's own
`exit_idx = entry_idx + horizon_bars` (counting through the security's
OWN bar list, silently skipping any gap) is replaced entirely --
counting the security's own available bars, rather than looking up the
exact calendar-target session, is what let classification and the
return calculation disagree (see 1.2's corrected example). The SAME
discipline applies to the benchmark's own bar lookup for the relative-
return side -- both sides of one outcome agree on `T_target` by
construction, never independently drifting onto different dates.

### 1.2 Worked example, corrected (revision 3's was mis-indexed)

Calendar `E(0), S1(1), S2(2), S3(3)` (index in parentheses).
`horizon_bars = 2`. **Simple case, entry at `E`:** `T_target = S2`
(index `0+2=2`). If `development_end = S2`: `T_target <=
development_end`, not OOS. If the security's own bars are `{E, S3}`
(missing a bar exactly at `S2`): **missing-data status at `S2`,
never shifted to `S3`.** This is the corrected, simple form of the
example -- revision 3's own "entry at S1" variant incorrectly computed
`T_target` as `S2` when, by the same rule, entry at `S1` with `N=2`
gives `T_target = S3` (index `1+2=3`), not `S2` -- that mis-indexed
variant is withdrawn.

### 1.3 The four-way check, in order, with the price-reading boundary
stated explicitly

1. **Calendar insufficient to determine the target** -- `T_entry`
   itself is not found in the calendar's own `session_dates`, or
   `T_target`'s computed position falls beyond the calendar's declared
   coverage. **Distinct failure, checked FIRST:** this is a calendar-
   coverage problem, not a price/data problem -- no price has been
   read at this point, and none is read to perform this check (pure
   date-arithmetic against the calendar object only).
2. **`T_target` beyond `development_end`** -- `CROSSES_LOCKED_OOS`.
   Checked purely from the calendar's own dates against
   `development_end`; still no price read.
3. **`T_target <= development_end` but `T_target > effective_as_of`**
   (`effective_as_of = min(data_as_of, development_end)`) -- the
   caller's own vantage point has not yet reached that session;
   `INSUFFICIENT_FUTURE_DATA`. Still no price read past
   `effective_as_of` -- this is a pure date comparison between
   `T_target` and the already-known `effective_as_of` boundary.
4. **`T_target <= effective_as_of`** -- the bar SHOULD be fetchable.
   Only NOW is the bounded fetch (bounded to `effective_as_of`,
   point 1 of the original F1 fix, unchanged from earlier rounds)
   consulted for a bar at exactly `T_target`. **Corrected this round
   (GPT's review of revision 4, relayed by Radu): bar presence alone is
   NOT sufficient for `VALID` -- it only permits the EXISTING price
   check to run, confirmed this round by reading
   `outcomes/forward_returns.py` lines 77-94:**
   - **4a. No bar at exactly `T_target`:** the data-gap status (distinct
     from both `CROSSES_LOCKED_OOS` and `INSUFFICIENT_FUTURE_DATA` --
     Radu's own semantic naming call, unresolved, same as every prior
     round).
   - **4b. A bar exists at `T_target`, but its own price field
     (`split_adjusted_close`) is `None`:** a DISTINCT, already-existing
     case in the current code (line 91-92: this maps to
     `INSUFFICIENT_FUTURE_DATA` today, even though the bar's DATE is
     not in the future -- its PRICE is simply absent). Conceptually
     closer to a data-quality gap than a not-yet-arrived case; whether
     it should share 4a's status name, get its own third name, or keep
     today's `INSUFFICIENT_FUTURE_DATA` label is a further, NOT yet
     resolved naming question, alongside 4a's -- **Radu's own call,
     not decided by this document.**
   - **4c. A bar exists at `T_target` with a non-`None` price, AND the
     entry bar's own price is also non-`None` (the existing
     `entry_bar.split_adjusted_close is None` check, line 78-79, runs
     regardless of this section's changes):** only THEN is
     `outcome_status = VALID` and the return computed. **Note: these
     are `is None` checks in the current code, not a general
     `math.isfinite()` check -- stated precisely, not assumed broader
     than what was read this round.**

**No step above ever reads a price dated later than `effective_as_of`
-- the calendar-only checks (1-3) never touch price data at all, and
step 4 only reads a bar at a date already proven `<= effective_as_of`
by step 3.** This is the exact mechanism by which the OOS leak is
closed: price access and the OOS/not-yet/gap distinction are now
fully decoupled.

### 1.4 Scope boundaries, unchanged from revision 3

Sub-daily timeframes (`4H` etc.) are NOT addressed -- a daily calendar
says nothing about an intraday bar grid; named as an open gap.
**"TEST 27 confirmed still passing" remains retracted** -- nothing
has been implemented or run; TEST 27's own assertion is a regression
GOAL this mechanism is designed to satisfy (step 2 above still
produces `CROSSES_LOCKED_OOS` whenever appropriate), not a verified
result.

---

## 2. The calendar source -- sourcing requirements and the dependency
direction, unresolved design questions named precisely

`backtest.data.calendar.build_trading_calendar()` is a constructor
over caller-supplied `session_dates` -- it does not itself source or
verify anything external.

**Priority design work this round (per Radu's own explicit
instruction: "calendarul este încă în a doua categorie... Acestea
trebuie proiectate înainte de a declara F1 complet"):** a complete
#003 design needs four things this document previously only LISTED as
open. Confirmed this round, by reading `src/backtest/data/calendar.py`
and `src/backtest/models/entities.py` in full: Spec #005 ALREADY built
a complete, content-addressed, verified mechanism covering all four --
`TradingCalendar` (`calendar_id`/`calendar_hash` via `calendar_
fingerprint()`, `source`/`verified_by`/`verified_at`, `coverage_start`/
`coverage_end`), `verify_calendar_content_address()`, `verify_
calendar_structure()`, `require_verified_calendar_for_formal_run()`,
and `require_calendar_covers_window()`. **The design recommendation
this round is to REUSE this existing mechanism for #003, via the
section-2 relocation already recommended, rather than inventing a
parallel one:**
- **Source/version/integrity:** real session dates are built into a
  `TradingCalendar` via the EXISTING `build_trading_calendar()`
  constructor (relocated to Data Foundation), with `source =
  OFFICIAL_VERIFIED` and `verified_by`/`verified_at` populated by
  whichever Data-Foundation-level process establishes real market
  session dates independent of any specific security's price series
  (the ingestion process itself -- e.g. an official exchange calendar
  feed -- is Radu's own call, not resolved here; the CONTRACT it must
  populate already exists and is reused unchanged). `calendar_id`/
  `calendar_hash` already give it a content-addressed identity, the
  same discipline as every other id in this project.
- **Coverage requirement:** reuse `require_calendar_covers_window()`
  unchanged, called with the window `[development_start, max(
  development_end-or-now, the furthest `T_target` any horizon
  configured for this run could reach)]` -- section 1's own F1 fix
  needs the calendar to resolve `T_target` for EVERY horizon the run
  classifies, so the required window must cover all of them, not only
  `development_end`.
- **Entry/target-beyond-coverage behavior:** `require_calendar_covers_
  window()` already raises `CalendarCoverageIncompleteError` for this
  case -- reused directly as section 1.3's own check 1.
- **Provenance:** add the calendar's own `calendar_id`/`calendar_hash`/
  `calendar_version` to `EvaluationRunRegistry`'s own provenance
  fields, mirroring exactly how `require_verified_calendar_for_formal_
  run()` already re-verifies a calendar's content-address before
  trusting it -- the SAME re-verification-before-trust discipline,
  reused rather than re-invented.

**One genuine, NOT-yet-resolved contractual choice remains, named
precisely rather than assumed:** `require_verified_calendar_for_
formal_run()`'s OWN strictness (source MUST be `OFFICIAL_VERIFIED`,
never `SYNTHETIC_TEST_FIXTURE`) is explicitly scoped by SS11's own
text to FORMAL (#005) runs only -- `calendar.py`'s own module
docstring states `_resolve_session_dates()` (#003) "is untouched" and
that "#005's stricter calendar requirement is a #005-only concern,
never a #003 patch." **Whether #003's OWN new calendar-verification
step (reusing the same `TradingCalendar` contract) should require the
SAME `OFFICIAL_VERIFIED`-only strictness, or accept a looser tier for
#003's own (non-formal-backtest) purposes, is Radu's own call -- the
MECHANISM is fully specified and reused either way; only the
STRICTNESS THRESHOLD is open.**

**Dependency direction, still unresolved:** importing `TradingCalendar`
from `src/backtest/` into `src/evaluation/` reverses this project's own
verified one-way chain (Data Foundation -> Discovery -> Evaluation ->
Hypothesis -> Backtest). "Read-only" does not change this -- it is a
package-level import-graph fact, not a runtime-behavior one.
**Recommended, not decided:** relocate the calendar type (and whatever
minimal construction logic #003 needs) to a neutral location both
`evaluation` and `backtest` can import from -- most naturally Data
Foundation. **This remains Radu's own decision**, named here as a
recommendation, not resolved.

**Consequence and regression, stated concretely this round (per
Radu's own request -- a recommendation with consequences, not only
alternatives):** `build_trading_calendar()` is confirmed, by reading
`src/backtest/data/calendar.py` in full, to be a PURE constructor over
caller-supplied `session_dates` -- it sources and verifies nothing
itself. Relocating it is therefore a pure move (no logic change), with
ONE consequence: every current `backtest` import site switches to the
new location, and `evaluation`'s own import of it no longer reverses
the one-way chain. **Regression:** (1) every EXISTING test currently
exercising `build_trading_calendar()`/`require_verified_calendar_for_
formal_run()` from its current location re-run unchanged at the new
import path, asserting byte-identical behavior (a pure-relocation
claim is falsifiable this way, not merely asserted); (2) a NEW test,
in the same family as TEST 26/TEST 49/TEST 17-18 (section 8, section
9), asserting `src/evaluation/` never imports `src/backtest/` at all
(not just the calendar specifically) -- closing the SAME class of
architectural-direction gap this document already treats for
`hypothesis`, generalized to `backtest` as the forbidden namespace
from `evaluation`'s own side.

---

## 3. F4+F5 -- the per-security formula's own scope, stated precisely

`w = W_b / (k * n_i)` (per bin `b`, `k` = distinct securities, `n_i` =
security `i`'s own row count) **equalizes each security's TOTAL weight
within a bin -- it does not address cross-SESSION universe-size
variation within the same bin.** Radu's own example, confirmed: one
bin, security A present in 2 sessions (2 rows), 9 other securities
present only in the second of those sessions (1 row each, `k=10`
total). Per-security weight: A's rows get `W_b/20` each (total
`W_b/10`); each of the 9 others gets `W_b/10`. **Session 1's own total
weight = `W_b/20` = 5% of the bin; session 2's = `W_b/20 +
9*(W_b/10)` = 95%.** The formula is CORRECT for what it claims (every
security's total weight equal) and does NOT claim to equalize
session-level representation -- that is a separate, unaddressed
property, possibly also within SS74C's "large universe periods"
language.

**Impossibility claim RETRACTED this round (GPT's review, relayed by
Radu, verified by execution): equal per-security weight and equal
per-session weight are NOT mutually exclusive except in the degenerate
same-sessions case -- that was a false general claim.** Counterexample,
verified: `A` and `B` each present in sessions `S1` and `S2` (weights
`1/4` and `1/12` respectively), `C` present only in `S2` (weight
`1/3`). Security totals: `A=B=C=1/3` each (uniform). Session totals:
`S1=S2=1/2` each (ALSO uniform) -- despite `A`/`B` and `C` having
DIFFERENT presence patterns (2 sessions vs. 1). Both margins can be
uniform simultaneously under a non-trivial joint weighting; whether
that is ACHIEVABLE for this project's actual observed data (whose
presence structure is not chosen, unlike the counterexample) is a
separate, structure-dependent question, not a closed impossibility. A
naive normalization layered mechanically on top of the existing per-
security formula could still break its agreed property in practice --
that narrower, practical risk stands -- but "impossible in general" is
withdrawn.

**Diagnostic mechanism CORRECTED this round -- a raw row-count
`Counter` understates the real weighted skew, verified by execution:**
for Radu's own 1-security/2-sessions vs. 9-securities/1-session
example, a row-count `Counter` over session dates (mirroring
`compute_concentration()`'s own unweighted-row-counting shape
literally) gives `S1=1/11≈9.09%`, `S2=10/11≈90.91%` -- NOT the `5%`/
`95%` figure that actually motivated this concern, which comes from
the WEIGHTED per-security formula (`w=W_b/(k*n_i)`) applied to the
SAME example, verified: `S1`'s total weight (`A`'s one `S1` row at
`W_b/20`) is exactly `5%`, `S2`'s (`A`'s `S2` row plus the 9 others'
`W_b/10` each) is exactly `95%`. **A row-count diagnostic would
misreport the actual influence skew as roughly half its true size --
the diagnostic must sum ROW WEIGHTS per session, not count rows:**
`session_mass[t] = sum(w_row for every row dated t)` (using the SAME
per-security `w_row` already computed for the point estimate), then
normalize within the bin -- NOT a `Counter` of raw row occurrences.

**Concrete recommendation, corrected (per Radu's own request -- a
recommendation with consequences, not only alternatives):** add the
WEIGHTED `session_mass` diagnostic above (not a plain `Counter`),
surfaced as a new field or via `warnings` on `BaselineComparison`,
NEVER consumed by `stratified_baseline_point_estimate()` or any
weight/significance formula -- still a purely descriptive addition,
same category as `compute_concentration()`'s own established pattern,
just corrected to actually report WEIGHTED influence rather than raw
row counts. **Consequence:** zero change to the already-agreed per-
security weighting's own behavior; Radu's own example now becomes
visible as its TRUE `5%`/`95%` split, not a misleadingly milder
`9%`/`91%`. **This diagnostic, by itself, does NOT remedy the
within-bin session-level variation it reports -- it only makes it
visible.** Accepting the diagnostic as a SUFFICIENT response (rather
than requiring an actual further weighting mechanism) is its own
explicit contractual decision against SS74C's own text, not settled
by adding the diagnostic -- stated precisely this round, not implied.
**If the diagnostic, once implemented and run against real data, shows
severe session-level skew is common and materially distorts reported
results, THAT finding would be a candidate trigger for designing a
real second mechanism** (mirroring the "diagnostic-first" philosophy
section 5 below also uses for the permutation/block question) -- not
decided here either way. **Regression:** a test asserting the
corrected WEIGHTED diagnostic reproduces the true `5%`/`95%` split for
Radu's own example (not the `9%`/`91%` a row-count `Counter` would
give); a test asserting `stratified_baseline_point_estimate()`'s own
output is byte-identical before and after this diagnostic is added.
**Radu's own approval needed:** whether the weighted diagnostic is a
sufficient response to SS74C's own text, or whether a real second
weighting mechanism is required instead -- not assumed by this
document.

---

## 4. The weighted-quantile algorithm -- corrected for scale invariance

### 4.1 Why revision 3's rank-based algorithm was wrong for relative
weights (not merely imprecise)

Revision 3's `target_rank = 1 + p*(W-1)` formula is correct ONLY when
weights are literal integer multiplicities (repeat-counts of an actual
unit-sized sample) -- it is NOT invariant to rescaling weights by a
constant, which F4+F5's own `W_b/(k*n_i)` formula produces (a RELATIVE
quantity with no natural unit scale). **Verified by direct execution,
three scalings of the identical relative distribution** (values
`[0,10,20]`, each equally weighted):

| Weights | `target_rank` formula's own Q1 |
|---|---|
| `[1,1,1]` | `5.0` |
| `[2,2,2]` | `2.5` |
| `[1/3,1/3,1/3]` | `20.0` (degenerates: `W=1`, every `p` maps to the same rank) |

Three different answers for what must be the identical relative
distribution. **Revision 3's "verified by direct execution" claim was
real but insufficient in scope** -- it verified the formula reduces to
`statistics.quantiles(..., method="inclusive")` for literal unit
weights, which is a different (narrower) claim than "correct for
arbitrary relative weights." **Withdrawn for this use case.**

### 4.2 Corrected algorithm -- scale-invariant, verified by execution

**Midpoint (Hazen-type) weighted percentile**, a standard convention:
sort `(value, weight)` pairs ascending; `C_i` = cumulative weight
through point `i` (inclusive); `P_i = (C_i - 0.5*w_i) / W`. The
quantile for probability `p` is found by linear interpolation between
the two `P_i`'s bracketing `p` (clamped to the first/last point's
value outside `[P_1, P_n]`). **Verified scale-invariant by direct
execution** (identical `Q1` for weights `[1,1,1]`, `[2,2,2]`, and
`[1/3,1/3,1/3]`, all giving `Q1 = 2.5`, `median = 10`, `Q3 = 17.5` for
values `[0,10,20]`).

**This does NOT reproduce `method="inclusive"` at equal weights --
stated explicitly, not glossed over:** `statistics.quantiles([0,10,20],
n=4, method="inclusive")` gives `[5.0, 10.0, 15.0]`, different from
this convention's `[2.5, 10.0, 17.5]` at `Q1`/`Q3` (median
coincidentally agrees here).

**RETRACTED this round (GPT's review of revision 4, relayed by Radu):
the claim that "scale invariance and exact `inclusive`-reproduction at
equal weights cannot both hold in general" is FALSE -- the two
properties are not incompatible.** Constructive counterexample,
verified by execution: define `R_i = (P_i - P_1) / (P_n - P_1)` from
the already-scale-invariant midpoint positions `P_i` above (for
`n >= 2` points with positive weight), and interpolate the quantile
against `R_i` instead of `P_i` directly. `R_i` is itself scale-
invariant (it is built entirely from `P_i`, which is already scale-
invariant by construction -- rescaling all weights by a constant
leaves every `P_i`, and therefore every `R_i`, unchanged). **At equal
weights, `R_i` reduces exactly to `(i-1)/(n-1)` -- the standard
`inclusive` rank convention** -- verified: for values `[0,10,20]` at
weights `[1,1,1]`, `[2,2,2]`, and `[1/3,1/3,1/3]`, `R` is identically
`[0, 1/2, 1]` in every case, and interpolating against it gives
`Q1=5.0, median=10.0, Q3=15.0` in every case -- matching
`statistics.quantiles(..., method="inclusive")` exactly, AND scale-
invariant across all three weightings simultaneously. **This disproves
revision 4's impossibility claim; it does NOT by itself make `R_i` the
project's chosen convention.**

**Scope of the `R_i`/`inclusive` compatibility claim, NARROWED this
round (GPT's review of revision 5, relayed by Radu, verified by
execution): it holds only when the ORIGINAL observations already have
DISTINCT values with equal weights -- it does NOT hold once the
mandatory tie-aggregation rule (below) collapses any tied values,
even at equal weights.** Counterexample: observations `[0,0,10]`, all
weight `1`. `statistics.quantiles([0,0,10], n=4, method="inclusive")`
gives `[0.0, 0.0, 5.0]`. Computing `R_i` directly on the three
UN-aggregated rows (order does not matter here, since the tied rows
share the identical weight) reproduces this exactly: `[0, 0, 5]`.
**But once the mandatory tie-aggregation rule collapses the two
zero-weight-1 rows into one point of weight 2 (as this document
requires, to fix the order-dependence bug below), recomputing `R_i` on
the AGGREGATED two-point set `{(0, weight 2), (10, weight 1)}` gives
`[2.5, 5.0, 7.5]` -- a DIFFERENT answer**, because aggregation
necessarily changes the effective point count the rank convention
sees (two points, not three), and `inclusive`'s own rank formula is
defined over the ORIGINAL per-row count, ties counted separately for
ranking even though they share a value. **Corrected presentation: this
document does NOT offer "midpoint vs. a same-but-inclusive-guaranteed
variant" as the choice -- it offers midpoint (simple, never claims
`inclusive`-reproduction) vs. `R_i` (reproduces `inclusive` ONLY on
tie-free, equal-weight input; loses that property the moment
mandatory aggregation collapses any tie, which can happen even at
equal weights). Both remain live candidates for Radu's own choice; `R_i`
is a disproof of revision 4's impossibility claim, not an automatic
production recommendation.** **GPT's own stated recommendation,
relayed by Radu -- corrected attribution this round: this is GPT's
technical recommendation, not Radu's own personal preference, absent
his own explicit confirmation -- noted here without closing column
(c): midpoint with mandatory tie-aggregation, its properties declared
explicitly as above.**

**A second, independent defect found this round (GPT's review,
relayed by Radu): the midpoint convention (and `R_i`, since it is
built from the same `P_i`) is NOT well-defined under tied values with
different weights, without an explicit tie rule.** Verified by exact-
fraction execution: for `p=0.7`, pairs `[(0,1), (0,3), (10,1)]` (two
zero-valued points with weights 1 and 3, then a point at 10 with
weight 1) give `Q(0.7) = 5`, while the SAME multiset of pairs supplied
in a DIFFERENT order, `[(0,3), (0,1), (10,1)]`, gives `Q(0.7) = 0` --
the cumulative-weight position `C_i` (and therefore `P_i`) depends on
which tied-value row is processed first, so the result silently
depends on input ORDER, not merely on the weighted distribution the
rows represent. **Fix: aggregate the weights of all rows sharing an
identical value into ONE point BEFORE computing any cumulative
position** -- verified this removes the order-dependence entirely
(both orderings above, once aggregated to `{0: weight 4, 10: weight
1}`, give the identical `Q(0.7) = 6`). **This tie-aggregation step is
required for BOTH the midpoint and the rescaled convention** (both are
built from the same underlying `P_i`), and must be declared explicitly
as part of whichever convention Radu approves -- stated as a design
requirement, not an optional detail, since silently omitting it
reintroduces an undefined, input-order-dependent result.

**Contract completion, the remaining boundary cases, UNIFIED this
round (GPT's review of revision 5, relayed by Radu: revision 5's own
text said non-finite inputs are "excluded" while its own regression
matrix said "rejection" -- two different behaviors, never reconciled;
fixed here to ONE behavior, and the prior, mistaken justification by
analogy to `outcomes/forward_returns.py` is withdrawn, since that
module -- as this document itself correctly states elsewhere -- only
performs `is None` checks, never a general finiteness check, and so
cannot justify a finiteness-based exclusion policy here):**
- **Non-finite value or weight (`NaN`/`inf`) in the input the
  quantile function actually receives: a hard-fail input error
  (raise), never a silent exclusion inside the function.** Filtering
  out ineligible observations (e.g. a row whose value or weight is
  non-finite for an upstream reason) is the CALLER's own
  responsibility, done BEFORE invoking the quantile function, with the
  exclusion recorded explicitly (e.g. in `warnings`) -- the quantile
  function itself never silently drops a row it was handed.
- **Negative weight:** also a hard-fail input error, never silently
  clamped or dropped -- same treatment as non-finite, for the same
  reason (a quantile function that silently reinterprets malformed
  input masks an upstream bug).
- **Zero-weight rows:** excluded entirely before aggregation -- this
  one case IS a silent, intentional exclusion, not an error, mirroring
  the existing `if weight <= 0: continue` pattern already used
  elsewhere in this codebase (`bootstrap.py`'s
  `stratified_baseline_bootstrap_replicates()`,
  `comparison.py`'s `stratified_permutation_p_value()`) -- a
  zero-weight row contributes nothing to any weighted statistic by
  definition, unlike a negative or non-finite one, which signals
  malformed input.
- **Empty input** (no positive-weight rows survive): returns `None`
  for every requested quantile (mirrors the existing `if not pools:
  return None` pattern in `comparison.py`).
- **Single distinct value** with all remaining positive weight:
  returns that value for every `p`, trivially, under either
  convention.

**Recommended regression matrix, not yet implemented:** unit-weight
reproduction of `statistics.quantiles(..., method="inclusive")` on
TIE-FREE input by `R_i` specifically -- **corrected this round (GPT's
review, relayed by Radu): midpoint does NOT reproduce `inclusive` even
on tie-free, equal-weight input** (verified in 4.2: `[0,10,20]` gives
midpoint `[2.5,10,17.5]` vs. `inclusive`'s `[5,10,15]` -- a prior draft
of this matrix wrongly said "both conventions agree here"; only `R_i`
does); the `[0,0,10]`
tie-at-equal-weight case above, confirming midpoint and `R_i` now
DISAGREE post-aggregation (not a bug to fix, a property to regression-
lock); weight-rescaling invariance across at least three distinct
scale factors (as verified in 4.2); input-order permutation of
tied-value rows with DIFFERING weights (as verified in the tie-order
fix above, both pre- and post-aggregation); splitting one row's weight
into several rows at the identical value vs. one merged row (must
agree, by construction, once aggregation is applied); zero-weight
exclusion; negative-weight hard-fail; non-finite hard-fail; empty-input
`None`; single-distinct-value input. **Radu's own approval needed
for: which convention (midpoint vs. rescaled) to adopt -- his own
stated leaning is midpoint with mandatory aggregation, noted above,
not yet formally closed in column (c).**

### 4.3 The worked example, recomputed with the corrected algorithm --
exact fractions, verified by execution, independently reconfirmed by
Radu's own execution this round

Same bins as every prior round (`early`, weight `0.7`: security A 3
rows `[0.8,1.0,1.2]`, security B 1 row `[2.0]`; `late`, weight `0.3`:
A 1 row `[1.5]`, B 1 row `[2.5]`; per-security weights `W_b/(k*n_i)`,
`k=2` throughout):

- **Reweight (every row):** `Q1 = 79/70 ≈ 1.1286`, `median = 33/20 =
  1.65`, `Q3 = 43/20 = 2.15`, **`IQR = 143/140 ≈ 1.0214`**.
- **Collapse (representative = own mean):** `Q1 = 23/20 = 1.15`,
  `median = 33/20 = 1.65`, `Q3 = 43/20 = 2.15`, **`IQR = 1` exactly**.

**Both means remain `1.65`** (unaffected -- this was never in
question). **The IQR comparison, now correctly computed a third time:**
reweight's IQR (`≈1.0214`) is slightly WIDER than collapse's (`1.0`)
here -- a THIRD different directional answer across three attempts at
this same example (rev 2 claimed collapse narrower; rev 3's wrong
algorithm claimed reweight narrower; this corrected algorithm says
reweight is in fact very slightly wider). **The only claim retained
going forward: (i) and (ii) generally diverge on IQR even when their
means agree -- the specific magnitude and direction are fixture-
dependent and must be recomputed whenever the convention or the
fixture changes, never asserted from a prior round's arithmetic.**

---

## 5. The permutation-test extension -- exchangeability, not merely
distributional equality

**Revision 3's error, stated precisely:** claiming the shuffle-values-
across-fixed-weighted-slots procedure "tests exactly" a stated null
hypothesis overstates what was shown. Equality of the marginal VALUE
distributions, conditional on the security-representation structure,
does not by itself establish that individual observations are
EXCHANGEABLE under that procedure -- exchangeability is a joint
condition (the entire joint distribution is invariant under
permutation), stronger than marginal equality, and can fail under
within-security serial correlation or shared time effects (exactly
the kind of dependence this codebase's own TIME_BLOCK bootstrap design
already takes seriously elsewhere, per `bootstrap.py`'s own same-day-
grouping rationale). **Corrected framing:** conditional mutual independence of the
individual values (given which security/session produced each one)
plus a common distribution across the pooled group is ONE SUFFICIENT
condition for exchangeability -- stated this round precisely as
sufficient, not necessary, correcting an overclaim in this document's
own prior wording that risked reading as "exchangeability holds if and
only if this independence condition holds." Exchangeability could in
principle be satisfied through some other route even where that
specific independence fails; the point that matters operationally is
that NEITHER this document nor the codebase has shown exchangeability
holds for this procedure -- it is stated as the REQUIRED assumption,
not claimed as automatically satisfied, and not claimed to be the only
way it could hold. **Block/cluster permutation (shuffling each
security's entire row-set as one unit) has NOT been given its own
precise definition in any round so far** -- naming it as "an
alternative" without defining it is not a comparison, just a
placeholder.

**A second overclaim, retracted this round: the value-level procedure
is NOT "the weaker, more standard assumption, already used throughout
the rest of this codebase's own permutation/bootstrap machinery."**
Re-read this round: `statistics/bootstrap.py`'s
`time_block_bootstrap_replicates()` groups ALL values sharing a date
together first, then resamples CONTIGUOUS BLOCKS of calendar sessions
(not individual rows, not individual dates) with replacement -- the
file's own docstring states this explicitly as the reason block
bootstrap exists at all (preserving a common market/regime shock that
hits many securities' episodes in the same week). The existing
bootstrap machinery therefore does NOT treat row-level values as
mutually independent or as the unit of resampling -- it assumes the
OPPOSITE, that nearby-in-time rows are dependent and must be resampled
together. The value-level permutation procedure's independence
assumption is consequently NOT already validated elsewhere in this
codebase; it is a DIFFERENT, so far unjustified assumption, in tension
with the dependence structure the bootstrap design takes seriously.
**Both the value-level procedure and block permutation remain open,
with no comparison possible until block permutation is itself given a
full specification** (how pooled candidate groups are formed when the
raw-row target count `n_sig` doesn't align with whole-security block
boundaries) -- neither is presented as the default or the "standard"
choice going forward.

**Corrected this round (GPT's review, relayed by Radu): "ship as-is,
docs-only" is WRONG once F4+F5's per-security weighting is adopted for
the baseline's own point estimate.** `stratified_permutation_p_value()`
is confirmed, by re-reading `comparison.py` in full, to compute PLAIN,
unweighted within-bin means (`sum(base_vals)/len(base_vals)`) on both
the observed statistic and every permuted replicate. If the baseline's
REPORTED point estimate becomes per-security-weighted (section 3) while
this function stays plain-mean, the permutation test would be testing
significance of a DIFFERENT quantity than the one actually reported --
reintroducing an F3-style "reported effect and tested significance
describe different populations" mismatch, one level over. **Two
genuinely separate items follow, never collapsed into one:**

1. **The estimator mismatch -- needs design, code, and regression (not
   docs-only); DESIGNED in full this round, verified by execution:**
   extend each bin's baseline side to carry `(security_id, value)` per
   row (not a plain value list). Precompute each row's own FIXED
   per-security weight ONCE from the TRUE baseline composition (section
   3's existing `w = W_b/(k*n_i)` formula, scoped to this bin). Build
   the pooled array exactly as today (`signature values ++ baseline
   values`), but ALSO build a PARALLEL, FIXED weight array aligned to
   the SAME positions (`None` for every signature-side position, the
   precomputed weight for every baseline-side position) -- the weight
   stays bound to its POSITION in the pool, never to whichever value a
   shuffle later places there. For both `observed` and every permuted
   replicate: shuffle the VALUES only; the signature-side statistic is
   the plain mean of whichever values land in the (fixed-count,
   fixed-position) signature slots; the baseline-side statistic is the
   WEIGHTED mean of whichever values land in the baseline slots, using
   each slot's OWN fixed weight (never recomputed from whatever
   security the shuffled value happened to originally belong to).
   **Verified by execution this round:** at equal per-security weights
   (the degenerate case), this reduces BYTE-IDENTICAL to today's plain
   test (same observed value, same p-value, same RNG-driven sequence,
   confirmed on a toy fixture) -- a natural, automatic backward-
   compatibility regression. At skewed weights (a 2-row vs. 1-row toy
   fixture mirroring section 3's own asymmetry), the weighted observed
   statistic correctly reflects the heavier security's own dominance,
   verified against a hand-computed expected value. **Consequence:**
   the function's signature changes (baseline side needs security
   identity, not just values) -- a real code change, at implementation
   time, not optional. **Regression:** the equal-weight-reduces-to-
   today's-test property above, locked as its own test; every EXISTING
   test currently covering `stratified_permutation_p_value()` re-run
   and confirmed to still pass under equal weights specifically
   (proving non-regression for every case that doesn't exercise the
   new weighting). **For UNEQUAL weights, corrected this round (GPT's
   review, relayed by Radu): verifying only the observed statistic's
   value, as a prior draft did, does NOT verify the enumeration/
   p-value mechanics themselves -- a real gap.** **NEW -- a full
   EXHAUSTIVE-enumeration regression, independently verified this
   round by execution:** signature `[8]`; baseline `A=[0,2]` (2 rows),
   `B=[4]` (1 row), `k=2`; fixed per-row weights `[1/4, 1/4, 1/2]`;
   observed `8 - 2.5 = 5.5`; all `4! = 24` orderings of the four pooled
   values across the four fixed positions; two-sided, ties-included,
   gives EXACTLY `8/24 = 1/3`. **This must be kept DISTINCT from a
   Monte Carlo estimate using the existing add-one continuity
   correction** (`(extreme+1)/(iterations+1)`) -- the exhaustive count
   verifies the weighted enumeration's own MECHANICS; it validates
   nothing about the exchangeability assumption itself, which remains
   the separate, open question in item 2 below.
2. **The exchangeability-acceptance question -- stays exactly what it
   was, genuinely docs-only, and does NOT change with the estimator
   fix above:** whether to accept the value-level procedure's own
   required assumption (full exchangeability, not merely marginal
   equality) as a documented, temporary limitation for V1, or to
   require block permutation first. This remains the project's OWN
   already-stated position otherwise, confirmed by reading
   `comparison.py`'s own module docstring (lines 24-29): "a full
   two-way clustered permutation is a natural v2 refinement if the
   concentration/stability diagnostics ever show it's needed, not
   built speculatively now (Spec #003 SS47)." **This document's
   correction to that existing position is still only to its CAVEAT's
   precision** (state "full exchangeability," not the vaguer "finer-
   grained dependence") **-- but this acceptance decision is now
   explicitly scoped to apply to the WEIGHTED estimator above, once
   implemented, not to the plain-mean version it replaces.** Diagnostics
   alone (concentration/stability/the new session-mass diagnostic) do
   not by themselves certify that the weighted test's own p-values are
   correctly calibrated -- they are a trigger for building block
   permutation if they show a problem, never a substitute for defining
   it. **The trigger for actually building block permutation stays
   exactly what the existing docstring already names.**

**The `[5,7]` vs. `[3,4]` example, scoped correctly (not previously
scoped):** exhaustive enumeration over `C(4,2)=6` splits, two-sided
test on `|mean(group1) - mean(group2)|` with ties counted as "at least
as extreme," gives exact `p = 2/6 = 1/3`. **This checks only that the
exhaustive-enumeration arithmetic for EQUAL weights (the simplest case)
is implemented correctly -- it validates nothing about unequal weights
or about the exchangeability assumption itself**, which is the open
question above, not something a single small example can settle.

---

## 6. CI/bootstrap -- the estimator and the interval construction,
kept separate

**Revision 3 blurred two distinct steps; separated here:**

1. **Per-replicate estimator (uses F4+F5's weights):** `time_block_
   bootstrap_replicates()` currently tracks no security identity
   (`dated_values: list[tuple[str, float]]`). Extended to `list[tuple[
   str, str, float]]` (security_id, date, value), threaded from
   wherever the baseline pool is first assembled. Within EACH drawn
   replicate, recompute `k_rep`/`n_i_rep` from THAT replicate's own
   composition (which can differ from the original sample, since
   blocks are drawn with replacement) and apply section 3's weight
   formula using those replicate-local values -- never the original
   sample's fixed weights. **Bins with no eligible security/row
   combination in a given replicate are excluded from that replicate's
   combination step** (mirroring the existing `total_weight > 0`
   guard), with the remaining included bins' weights implicitly
   renormalized by the same `weighted_sum/total_weight` division
   pattern already in use.
2. **Interval construction from the replicate distribution (does NOT
   need weights again):** once step 1 produces `B` replicate statistic
   VALUES (one weighted number per replicate), the percentile CI is
   the UNWEIGHTED `2.5`th/`97.5`th percentile of those `B` plain
   numbers -- weighting was already fully consumed inside step 1;
   applying it again here would double-count it. Revision 3 did not
   distinguish these two steps.

**F3 common-support, the remaining pieces, enumerated exhaustively:**
weight renormalization is already the existing `weighted_sum/
total_weight` pattern (not a new mechanism); the SIGNATURE's own
`signature_mean_relative` must be restricted to the SAME bin subset as
`baseline_mean` (missed in every prior round -- restricting only the
baseline side reintroduces the original F3 population mismatch one
level down); when common support is empty for a given bin/replicate,
exclude it from BOTH the signature and baseline sides consistently,
for that bin/replicate; the all-bins-excluded boundary case produces
`None`, identical to option (a)'s own behavior in that same degenerate
case.

**Which fields this restricts, stated explicitly this round (per
`spec003_remediation_proposal_2026-10-04.md`'s own F3 section, option
(b)): restricted to the common-support bin subset (becomes `None`
outside it, or when no bin qualifies) --** `mean_difference`,
`median_difference`, `raw_p`, `mean_difference_ci`,
`standardized_effect` (since its own formula consumes `median_
difference` and `baseline_iqr` directly, section 4.1). **NOT
restricted -- stay full-population, unaffected by this fix:** the
signature's own plain descriptive statistics over its FULL set of
episodes (`relative_outcome`/`absolute_outcome`, the ordinary
`DescriptiveStats`, never the baseline comparison) -- nothing about
common-support requires narrowing what the signature's own raw
outcomes report, only what is compared against a baseline and tested
for significance.

---

## 7. Config immutability -- full recursive freezing, not `MappingProxyType`
alone

**`MappingProxyType` wraps dict-style access only -- a LIST nested
inside the wrapped dict is still a plain, mutable list, reachable and
mutable through the proxy.** Corrected requirement: a full recursive
freeze -- `dict` -> `MappingProxyType` of recursively-frozen values;
`list`/`tuple` -> `tuple` of recursively-frozen elements; every other
value (`str`/`int`/`float`/`bool`/`None`) returned as-is (already
immutable). The resulting snapshot must hold **no external mutable
reference** -- it is built from a fresh, fully independent traversal
of the loaded config (never aliasing the original `dict`/`list`
objects anywhere in the frozen structure). The three-way check (actual
content / the object's own claimed version / the version registered
for the operation) ties to THIS fully-frozen snapshot specifically --
unresolved wiring from revision 2/3 (how this snapshot's identity
reaches `hypothesis_config_version`/the versioning-epoch marker)
remains open, named here rather than silently assumed solved.

**Concrete recommendation this round (per Radu's own request),
grounded by reading all three config loaders in full -- CORRECTED
this round (GPT's review, relayed by Radu) on two points: it had
conflated two genuinely different "versions," and its own
verification mechanism had regressed below what
`spec004_remediation_proposal_2026-10-04.md`'s OWN "Required
regression coverage" section already specified for this exact
finding.**

**Point 1 -- config-content identity and run-id SCHEME identity are
two different axes, never one marker:** `hypothesis_config_version`,
`evaluation_config_version`, and `discovery_config_version` ARE
already content-addressed (confirmed this round: all three loaders
compute `sha256(raw_file_text)[:12]` fresh at every `load_config()`
call) -- this hash is the right identity for "has the YAML content
changed," and nothing further needs inventing for THAT question.
**But S2 (`build_run_id()`'s fingerprint gaining `security_ids`/
`benchmark_security_id`/`data_as_of`/`horizons`) is a CODE/ALGORITHM
change -- which FIELDS the fingerprint hashes -- that can happen with
ZERO change to any YAML file's content. The config hash would stay
byte-identical across that change, so it CANNOT serve as S2's own
"scheme changed" marker** -- revision 6 wrongly proposed reusing it
for both purposes. **Corrected: keep the existing config-content
hashes for config identity, unchanged; introduce a SEPARATE, literal
`run_id_scheme_version` constant (e.g. `"v2"`, bumped by hand whenever
`build_run_id()`'s own field set changes) -- the same discipline
already used elsewhere in this codebase for `OUTCOME_ENGINE_VERSION`/
`HYPOTHESIS_ENGINE_VERSION`, not a hash of anything, since there is no
file whose content tracks an algorithm's own field choices. **Placement
corrected this round (GPT's review, relayed by Radu): this constant
must be included IN `build_run_id()`'s own FINGERPRINT INPUT itself --
part of what gets hashed into `evaluation_run_id` -- not merely a
sibling field recorded alongside the id in `EvaluationRunRegistry`'s
provenance.** A provenance-only field would let two runs under
DIFFERENT schemes still collide on `evaluation_run_id` if every
hashed field happened to match; putting the scheme marker INSIDE the
hash preimage makes that structurally impossible, the same guarantee
every other fingerprint in this project already relies on. Historical
`evaluation_run_id`s computed under the OLD scheme are NEVER
reinterpreted** -- exactly `spec003_remediation_proposal_2026-10-04.
md`'s own S2 section already says, confirmed by reading it again this
round.

**Point 2 -- the verification mechanism compared two INCOMPATIBLE
hashes; corrected this round (GPT's review, relayed by Radu, verified
by execution on the actual `hypothesis.yaml` in this repo):** step 2
of revision 7's own mechanism recomputed a hash from a CANONICAL
RE-SERIALIZATION of the parsed content and compared it against the
EXISTING loader's raw-file-text hash -- these are NOT the same
digest, by construction, and would reject every legitimate config.
**Verified this round:** `sha256(raw hypothesis.yaml text)[:12]` =
`e5e262fa1378`; `sha256(canonical JSON of the PARSED dict)[:12]` =
a DIFFERENT value; `sha256(re-serialized YAML of the same dict)[:12]`
= a THIRD, also different value -- none of the three re-derived
digests matches the original loader's own hash, confirming the
mismatch is real, not edge-case-only.

**Corrected mechanism, per GPT's own recipe, relayed by Radu --
historical identity preserved, content verified SEPARATELY via
structural equality, never via a second incompatible hash:**
1. `RegisteredConfigVersion` retains the EXACT raw text(s) the loader
   actually used, AND the version computed by the EXISTING, unchanged
   loader algorithm over that exact text (`sha256(raw_text)[:12]` for
   `hypothesis`/`evaluation`; `sha256("".join(raw_texts))[:12]` for
   `discovery` -- preserving `discovery/config/loader.py`'s own exact
   multi-source-combination rule, never a different combination rule).
   No hash is RE-DERIVED from anything else; the registered version IS
   the loader's own output, carried forward unchanged.
2. The section-7 fully-frozen recursive structure is built by PARSING
   those SAME retained raw texts -- used for immutability (preventing
   downstream mutation of the loaded structure), never for re-deriving
   a hash.
3. For an OBJECT received from outside (a caller-supplied
   `HypothesisConfig`, or any config object not sourced from this
   exact registered snapshot): verify BOTH, as two SEPARATE checks,
   each catching a different failure mode --
   - **(a) label check:** its claimed version label equals the
     registered snapshot's own version string -- this is what catches
     a CORRECT-content-WRONG-label object (content is actually fine,
     but the label lies about which version it is).
   - **(b) structural-equality check:** its actual parsed CONTENT is
     STRUCTURALLY EQUAL to the registered snapshot's own parsed
     content -- this is what catches a CORRECT-label-WRONG-content
     object (the label is honest, but the underlying data was hand-
     built or mutated-before-freeze).
   **Representation corrected this round (GPT's review, relayed by
   Radu): the two sides being compared in (b) must be put into the
   SAME representation first, or the comparison is meaningless.** The
   registered snapshot's own content has already been through
   section 7's recursive freeze (lists -> tuples, dicts ->
   `MappingProxyType`); a freshly-parsed external dict has NOT (its
   lists are still plain lists) -- `{"a": [1, 2]} == {"a": (1, 2)}` is
   `False` in Python even though the two mean the same thing. **Fix:
   apply the SAME recursive normalization (the identical list->tuple,
   dict->plain-dict-for-comparison-purposes traversal) to BOTH sides
   before comparing** -- never compare an unfrozen dict directly
   against the frozen structure. Neither check substitutes for the
   other: passing (a) while failing (b), or passing (b) while failing
   (a), are both rejections, for different, clearly distinguishable
   reasons. **A separate, additional "semantic canonical digest" MAY
   exist for other purposes, but must NEVER be compared directly
   against the original raw-text-based version** -- the two serve
   different purposes and are not interchangeable.
4. The operation then uses EXCLUSIVELY this verified, registered
   snapshot -- never a second, independently-loaded object trusted
   without the same two-part check.

**File-mutation-after-registration policy -- EXPLICITLY CHOSEN, with
its justification CORRECTED this round (GPT's review, relayed by
Radu):** this document chooses design (b) -- a FRESH `load_config()`
re-read at `preregister_hypothesis()` gate time is MANDATORY, not
optional, and its version is compared against the approval-time
pinned snapshot's own version; a mismatch is a hard gate failure.
**Corrected justification: design (a) does NOT use a config the
approving human never saw -- that framing was wrong.** Design (a)
(proceed using exclusively the approved, pinned snapshot, with no
live re-check at all) uses PRECISELY the config the human approved,
regardless of what the live file says afterward -- it is not unsafe
with respect to the human's own decision. **The actual reason to
choose (b) over (a) is a separate, additional CONTRACTUAL
requirement this document adds: that the approved config must ALSO
still be the CURRENTLY ACTIVE one at registration time** -- a
freshness/currency requirement, not a correctness-of-content
argument. Both (a) and (b) are internally coherent designs; (b) is
recommended because it matches the stronger guarantee this document
has stated as its goal since revision 6 (no silent drift between
approval-time and registration-time configs), not because (a) is
unsafe. **Radu's own approval needed** for this choice between (a)
and (b) -- recommendation restated, not a correctness claim about (a).

**Consequence, unchanged in spirit, now correctly mechanized without
incompatible hashes:** today, nothing checks that a human's approval-
time config snapshot still matches what's live at registration time;
this design makes a mismatch a hard gate failure, via the retained
loader-native version and a mandatory live re-read, never via a
re-derived, incompatible digest. **Regression (collected in section
12), with each case now attributed to the SPECIFIC check that catches
it:** the correct-content-WRONG-LABEL case, rejected by the LABEL
check (3a) specifically; the correct-label-WRONG-CONTENT case,
rejected by the STRUCTURAL-EQUALITY check (3b) specifically, with both
sides normalized to the SAME representation before comparing; the
config-mutated-between-approval-and-registration case, caught by the
now-mandatory live re-read; a passing check operating on the pinned
snapshot afterward, not a second independent re-read; Discovery's own
multi-source combination rule preserved byte-for-byte in the
registered snapshot; PLUS, for S2 specifically, a regression asserting
two runs differing ONLY in `run_id_scheme_version` (identical config,
identical every other hashed field) produce DIFFERENT `evaluation_
run_id`s -- proving the scheme marker is inside the hash preimage, not
just alongside it -- distinguished from a SEPARATE regression
asserting two runs differing only in `horizons` (same scheme) also
produce different ids, showing the two axes (config/fields vs. scheme)
are each independently captured. **Radu's own approval needed for:**
adopting the config-identity wiring, the separate `run_id_scheme_
version` marker inside the hash preimage, and the mandatory-live-
re-read policy choice (on its corrected, freshness-based justification)
-- not assumed by this document.

---

## 8. The AST guard -- project-namespace resolution and a genuine
negative case

**Corrected this round (GPT's review of revision 4, relayed by Radu):
revision 4's filesystem-existence mitigation was backwards -- it would
produce a false NEGATIVE on a real violation, exactly where the guard
matters most.** A guard against reversing the project's one-way
dependency chain must catch an import of the forbidden namespace even
when the SPECIFIC submodule named does not exist YET -- e.g. a future
`from hypothesis.not_yet_written_module import X` inside
`src/evaluation/` is exactly the kind of violation this test exists to
catch, and gating on `src/hypothesis/not_yet_written_module.py`
actually existing on disk would silently let it pass BECAUSE the
violation targets something not yet written. Filesystem existence is
not a precondition for a dotted path to "belong to" a package in
Python's own import resolution -- it is a RUNTIME fact (would this
import actually succeed), orthogonal to the STATIC architectural
question this guard asks (does this import statement's top-level
component name the forbidden namespace).

**Corrected algorithm, namespace-membership first, filesystem as
auxiliary information only, never as a gate:**
1. **Recognize this project's own import-resolution environment
   explicitly:** confirmed this round, `src/` is the root importable
   directory -- every current import in this codebase is bare
   (`from hypothesis.models.entities import X`, `from evaluation.
   models.entities import Y`, never `from src.hypothesis... import
   X`); a leading `src.` prefix is a defensive secondary form to
   recognize (raised in an earlier round as a case to catch), not a
   form this project's code currently uses -- confirmed again this
   round, zero `src.`-prefixed imports exist anywhere in `src/` or
   `tests/` (`grep -rn "^from src\.\|^import src\."` -> no matches).
2. **Build CANDIDATE dotted paths per import statement, then check
   each candidate's first component -- corrected this round (GPT's
   review of revision 5, relayed by Radu): a prior draft of this rule
   treated each `alias.name` in `ast.ImportFrom.names` as an
   independent absolute namespace on its own, which is wrong -- the
   base (`node.module`, or the resolved relative base below) must be
   prepended first, and the base itself must ALSO be checked on its
   own:**
   - **`ast.Import`:** for each `alias.name`, one candidate =
     `alias.name.split(".")`.
   - **`ast.ImportFrom`, `node.level == 0` (absolute):** `base =
     node.module.split(".") if node.module else []`; candidates =
     `[base]` (checks the base alone -- catches `from hypothesis.x
     import y`) **plus** `[base + [alias.name] for alias in
     node.names]` (catches `from src import hypothesis`, where
     `base=["src"]` alone is not a hit, but `base + ["hypothesis"]`
     is, once `"src"` is stripped below).
   - **Strip a leading `"src"` component if the CANDIDATE's own first
     element is `"src"`** (the defensive secondary form from rule 1),
     then the import is a FORBIDDEN hit iff the candidate's (possibly
     stripped) first remaining component equals the forbidden
     namespace's top-level name exactly (`"hypothesis"` for TEST 49) --
     matching the first component only, correcting revision 3/4's own
     `"hypothesis" in m.split(".")` substring-anywhere matcher (which
     would wrongly flag an unrelated `vendor.hypothesis`, first
     component `vendor`). **Verified this round: `from vendor import
     hypothesis` produces candidates `[["vendor"], ["vendor",
     "hypothesis"]]` -- neither's first component is `"hypothesis"`
     after the (inapplicable) strip step, correctly NOT flagged;
     `from src import hypothesis` produces `[["src"], ["src",
     "hypothesis"]]` -- the second candidate strips to `["hypothesis"]`,
     correctly FLAGGED.**
3. **For a RELATIVE import** (`ast.ImportFrom` with `node.level > 0`):
   **corrected this round -- the climb amount was off by one.**
   Compute the ANALYZED FILE's own package-component tuple from its
   path under `src/` (e.g. `src/evaluation/baseline/universe.py` has
   package tuple `("evaluation", "baseline")`). The base is this
   tuple with its LAST `node.level - 1` components dropped (never
   `node.level` -- level 1 means "this same package," not "climb one
   level up"), then `node.module`'s own components (if any) appended;
   from there, candidates are built exactly as in rule 2's `ImportFrom`
   case (base alone, and base + each `alias.name`). **Boundary
   condition CORRECTED again this round (GPT's review, relayed by
   Radu, verified against real Python's own `importlib.util.
   resolve_name()` this round): the unresolvable "beyond top-level
   package" case triggers when `node.level - 1 >= len(package tuple)`
   -- NOT only when it strictly EXCEEDS the length, as a prior draft
   of this rule said.** Verified by execution: `importlib.util.
   resolve_name("...x", "evaluation.baseline")` (package tuple length
   2, `level=3`, so `level-1=2`) raises Python's own `ImportError:
   attempted relative import beyond top-level package` -- the
   unresolvable case already triggers AT `level=3` from this 2-deep
   package, not only at `level=4` as a prior draft claimed. **Flagged
   separately as its own diagnostic**
   (`"relative import climbs above its package root, cannot verify
   architectural direction"`), never silently passed, never silently
   assumed forbidden. **Verified by execution against package
   `("evaluation", "baseline")`, including the corrected boundary:**
   `.hypothesis` (`level=1, module="hypothesis"`) resolves to
   `["evaluation", "baseline", "hypothesis"]` -- first component
   `evaluation`, correctly NOT flagged (it is `evaluation`'s own
   sibling module, confusingly named but internal); `..hypothesis`
   (`level=2, module="hypothesis"`) resolves to `["evaluation",
   "hypothesis"]` -- first component `evaluation`, also correctly NOT
   flagged, one level further up; `...hypothesis` (`level=3`) hits the
   beyond-root case NOW, confirmed by `importlib.util.resolve_name()`
   itself raising at this exact level, not at `level=4`. **Confirmed
   this round: zero relative imports exist anywhere in `src/` today**
   (`grep -rn "^from \.\|^from \.\."` -> no matches) -- this closes a
   gap in the CONTRACT (a future relative import could otherwise slip
   past an absolute-only matcher, or be mis-resolved by the off-by-one
   formula this round corrects) without fixing any currently-active
   false negative, since none exists today.
4. **Filesystem existence is demoted to a non-gating, informational
   signal only** -- it MAY be used to enrich an error message (e.g.
   "no such module exists yet at this path") but must NEVER decide
   whether an import is flagged; the architectural ban is about
   NAMESPACE membership, independent of whether any particular
   submodule has already been written.

**Positive/negative case matrix, consolidated this round (TEST 26 and
TEST 49 share this identical matrix):** FLAGGED -- `import hypothesis`;
`from hypothesis.registry import hypotheses`; `from src.hypothesis
import X` (absolute, `src.`-prefixed); `from src import hypothesis`
(the base+alias construction above); a relative import that climbs
all the way to the `src/` root and then into `hypothesis`. NOT
FLAGGED -- `from vendor import hypothesis` (unrelated namespace
sharing the literal name one level down); `from .hypothesis import X`
and `from ..hypothesis import X` from within `evaluation.baseline`
(both resolve to an `evaluation`-internal sibling module, verified
above); a relative import exceeding its package root (its own
separate, named diagnostic, neither flagged nor silently passed).

**This same algorithm applies uniformly to every guard of this
structural shape in the codebase** -- Spec #002's TEST 17/18, Spec
#003's TEST 26 (discovery cannot import evaluation, see new section 9
below), and Spec #004's TEST 49 (worked through above) all share the
identical collector/matcher defect pattern and the identical fix;
TEST 26 does not carry the name-collision concern below (no known
third-party package named `evaluation` is in use or anticipated here).
**Status this round, corrected (GPT's review of revision 5, relayed by
Radu): TEST 26's own row is NOT "Yes" until this shared algorithm
itself is corrected -- it was marked complete in revision 5 while
still carrying the two resolution bugs this round fixes; both TEST 26
and TEST 49 move together, since they share one algorithm (section
10's checklist updated accordingly).**

**The bare top-level name-collision case is a SEPARATE, narrower
problem from the algorithm above, and is NOT a precondition for
shipping this guard now:** `hypothesis` is the name of a well-known
third-party PROPERTY-BASED TESTING library on PyPI -- confirmed NOT
currently installed in this project (`pip show hypothesis` -> not
found) and not referenced in any requirements file (checked this
round and re-confirmed), but a plausible FUTURE addition. If it were
ever added, a bare `import hypothesis`/`from hypothesis import given`
intending the THIRD-PARTY library would be syntactically IDENTICAL, at
the AST level, to this project's own unqualified `import hypothesis`
style -- static analysis alone cannot disambiguate the two for a bare
top-level form, in either algorithm. **This does not block shipping
the corrected algorithm above:** within THIS test's own enforcement
scope, the project can simply DECLARE, by convention, that the bare
name `hypothesis` is reserved for the internal package for purposes of
this guard, now -- a declaration, not a resolution, and one that would
need re-examination only if and when the third-party library is
actually added as a dependency (not resolved preemptively by changing
the guard's logic today, and not a reason to withhold the corrected
algorithm in the meantime).

---

## 9. #003 straightforward mechanisms -- reintegrated in full, not
only "Yes" in a checklist cell (new section this round; GPT's review
of revision 4, relayed by Radu, found these marked complete in the
checklist with no mechanism text anywhere in the document's own body)

**F2a -- frozen signature set accepted without content verification
(Top Finding 12a):** `run_evaluation()` never recomputes
`freeze_signature_set()` on the incoming `SignatureSet` to check its
own `signature_set_id` actually matches its own `signatures`. Fix: at
the top of `run_evaluation()`, recompute `freeze_signature_set(list(
signature_set.signatures)).signature_set_id` and raise if it doesn't
equal `signature_set.signature_set_id` -- a cheap, deterministic
check, no behavior change for any legitimately-constructed
`SignatureSet`. Test needed: a `SignatureSet` built via
`dataclasses.replace()` with mismatched content/id, asserting
`run_evaluation()` now raises.

**F2b -- duplicate `signature_id` collides in BH correction (Top
Finding 12b):** nothing rejects two `EvaluationSignatureDefinition`s
sharing one `signature_id` within a `SignatureSet`; `record_key()`
then collapses their BH entries into one. The check must sit at
`run_evaluation()`'s own entry gate, not only inside
`freeze_signature_set()` -- F2a's own reproduction already shows a
`SignatureSet` reaching `run_evaluation()` without ever passing
through `freeze_signature_set()` (built directly via `dataclasses.
replace()`), so a uniqueness check placed only there would be bypassed
the same way. Fix: at the top of `run_evaluation()`, alongside F2a's
check, validate `len({s.signature_id for s in
signature_set.signatures}) == len(signature_set.signatures)`, raising
on a duplicate; `freeze_signature_set()` may gain the same check too,
as defense-in-depth, but never as a substitute for the engine-entry
gate. Test needed: a `SignatureSet` with two definitions sharing one
`signature_id`, built via `dataclasses.replace()` (bypassing
`freeze_signature_set()`), asserting `run_evaluation()` still rejects
it.

**F6 -- `family_test_count` missing (Top Finding 7):** SS44 names
`family_test_count` in `BaselineComparison`'s required field list; the
field exists nowhere in `src/` or `tests/`. Fix: add
`family_test_count: Optional[int]` to `BaselineComparison`, defined as
the number of `PValueRecord`s actually included in that record's own
BH family (`len(fam_records)` for the family `benjamini_hochberg()`
grouped this profile into) -- never a count of every signature x
horizon combination in the run. **`family_test_count` is non-`None`
if and only if `mode == "FORMAL_DEVELOPMENT"` AND this profile's
`raw_p is not None`** -- exactly mirroring the existing `adjusted_p`/
`family_id` population rule, independent of `support_status`
(`stratified_permutation_p_value()` and the support-sufficiency check
are two independent mechanisms; a profile tagged
`INSUFFICIENT_SUPPORT` can still have a non-`None` `raw_p`, and vice
versa). Tests needed: `family_test_count` equals the real family size
in a multi-signature `FORMAL_DEVELOPMENT` run; `family_test_count is
None` for every profile in an `EXPLORATORY` run, including one with
non-`None` `raw_p`; `family_test_count` populated for an
`INSUFFICIENT_SUPPORT`-tagged profile with non-`None` `raw_p` in a
`FORMAL_DEVELOPMENT` run (demonstrating the two mechanisms are
independent).

**#003 G1 -- TEST 26 AST guard blind to the parent-import form (Top
Finding 18), same defect family as section 8 above, now fully
specified and NO LONGER open, this round, since section 8's shared
algorithm had its two resolution bugs fixed:** `_imported_modules()`
never inspects `ast.ImportFrom`'s `names` (the imported symbols), only
`.module` -- so `from src import evaluation as ev` inside
`src/discovery/` is invisible to the guard. Fix: apply section 8's
now-corrected algorithm in full (base+alias candidate construction,
the `level - 1` relative-import climb, filesystem demoted to
non-gating) with `"evaluation"` as the forbidden top-level name; no
`evaluation`-name third-party collision is known or anticipated, so
TEST 26 needs none of section 8's bare-name-collision caveat, and --
unlike TEST 49 -- has no remaining open item of any kind once the
shared algorithm itself is correct. Test needed: a regression using
the exact scratch-file probe already used to demonstrate this
(`from src import evaluation as ev`), asserting the guard now fails
as expected, PLUS section 8's own consolidated positive/negative case
matrix (with `"hypothesis"` swapped for `"evaluation"`).

**#003 G2 -- TEST 34's assertions do not test what they claim (Top
Finding 19), not an AST guard, a plain test-correctness fix:**
`test_34_holding_decay_curve.py` line 41 ends in `or True`, making the
assertion unconditionally pass; line 43's `hasattr(curve, "winner")`
check is trivially true for any plain list, not a guard specific to
this function. Fix: remove the `or True`; assert on `curve`'s actual
values directly (the real filter logic lives in `engine.py`'s
`decay_curve()`, filtering by `signature_id`) rather than re-deriving
a filtered list from `profiles` only to compare it to itself; for the
"no winner" check, assert on `EvidenceProfile` itself having no such
field (via `dataclasses.fields()`), which could meaningfully carry a
"winner" concept if one were ever added, rather than on a plain list.
This IS the test fix -- no separate regression beyond correcting
`test_34` itself.

---

## 10. #004 mechanisms -- reintegrated in full (not only as deltas)

**Finding 14 (GPT-G1), status downgraded to PARTIAL this round (GPT's
review of revision 4, relayed by Radu): the mapping was incomplete in
a way confirmed this round by reading the actual gate code
(`registry/preregistration.py`, `validation/rules.py`,
`proposals/validator.py`, `models/entities.py` in full).**

**The gap, stated precisely:** `preregister_hypothesis()` and
`validate_for_preregistration()` NEVER cross-check the `draft`'s
trading-content fields against the originating `proposal`'s
corresponding fields at all -- confirmed by reading both functions in
full. The only link from `draft` back to `proposal` today is
`draft.hypothesis_provenance.proposal_id == proposal.proposal_id`, a
STRING-identity check -- and `proposal_id` is NOT content-addressed
(`normalize_proposal()` reads it verbatim from the caller's raw dict,
confirmed this round). `validate_for_preregistration()`'s own
`hypothesis_id`/`definition_hash` check only proves SELF-consistency
(the hash matches the draft's OWN current fields) -- it proves nothing
about whether those fields are what the human/consensus process
actually reviewed. As things stand, a `draft` carrying a `proposal_id`
that matches some previously-APPROVED proposal's id, but with
completely different `direction`/`entry_definition`/
`horizon_candidate_set`/`evidence_provenance` content, would pass
every existing check, because nothing anywhere compares `draft`'s
content against `proposal`'s content, or against what the human
actually approved.

**Corrected design, three parts:**
1. **`verify_draft_matches_proposal(draft, proposal, variants) ->
   (bool, errors)`, a new explicit check inside `preregister_
   hypothesis()`'s existing step 0 block:** field-by-field equality --
   `draft.direction == proposal.direction`; `draft.entry_definition ==
   proposal.entry_definition`; `draft.entry_execution_policy ==
   proposal.entry_execution_policy`; `draft.horizon_candidate_set ==
   proposal.horizon_candidates`; `draft.evidence_provenance ==
   proposal.source_evidence`. Exits checked by replay, not by
   equality, since `materialize_variants()`'s TIME_EXIT expansion is a
   one-to-many derivation: for each of `proposal.exit_hypotheses`,
   confirm a variant with the matching `variant_fingerprint()` is
   present among `variants`, AND that `variants` contains no OTHER
   content the proposal didn't ask for.
2. **Tying the human's approval to this exact content:** add
   `content_fingerprint: str` to `HumanDecision`, populated by
   whatever process constructs it (the human review step) from the
   SAME canonical fingerprint -- `direction`/`entry_definition`/
   `entry_execution_policy`/`horizon_candidates`/`source_evidence` via
   the existing `_entry_fp()`/`_horizon_fp()`/`_evidence_fp()`
   component functions, PLUS the exit content via `_exit_fp()` --
   computed from the `proposal` the human was actually shown. At the
   gate, recompute this same fingerprint from the LIVE `proposal`
   argument and require it to equal `consensus.human_decision.
   content_fingerprint` -- this is what ties "a human approved" to "a
   human approved THIS content," which nothing today establishes.
3. **Tying the cached structural-validation result to the same
   content and the same config. Corrected this round (GPT's review of
   revision 5, relayed by Radu, confirmed by reading `validate_
   proposal()` in full): option (ii) below, as previously described,
   is NOT sufficient on its own -- (i) is now this document's actual
   RECOMMENDATION, not merely "the simpler fit."**
   - **(i), RECOMMENDED:** have `preregister_hypothesis()` RE-RUN
     `validate_proposal()` itself, on the live `proposal` argument,
     against whatever `HypothesisConfig`/`DiscoveryConfig` versions
     are currently registered for this operation (tied to Finding
     19/11's `RegisteredConfigVersion` mechanism, section 7) --
     removing the cached `proposal_validation.valid` flag from the
     trust boundary entirely, since there is then nothing cached to
     go stale, and the LIVE `validate_proposal()` call necessarily
     sees every field it has always read, including the narrative
     ones below -- this gap cannot arise for option (i) by
     construction, the same reasoning as the recomputed `hypothesis_
     id`/`definition_hash` pattern elsewhere in this codebase.
   - **(ii), the cache-preserving alternative, corrected this round --
     NOT yet sufficient as revision 5 described it:** `validate_
     proposal()` is confirmed, by reading it in full, to ALSO require
     `proposal.facts_from_evidence` non-empty and `proposal.
     interpretation` non-empty/non-whitespace (lines 272-275) --
     BOTH narrative/evidentiary fields, deliberately EXCLUDED from the
     trading-content fingerprint in part 2 above (same exclusion
     discipline as `direction_basis`/`selection_basis` elsewhere in
     this project). **A cached `ProposalValidationResult` tied only to
     that narrower content fingerprint could stay apparently valid
     after `facts_from_evidence`/`interpretation` are emptied out,
     since emptying them does not change the trading-content
     fingerprint at all** -- confirmed, this is a real gap in
     revision 5's own option (ii), not merely a theoretical one.
     **For option (ii) to be sound at all, it needs a SECOND, WIDER
     fingerprint -- a "validation-input fingerprint," distinct from
     and never confused with the narrower economic-identity
     fingerprint -- covering every field `validate_proposal()` itself
     reads: `direction`, `entry_execution_policy`, `entry_definition`,
     `horizon_candidates`, `exit_hypotheses` (already in the narrower
     fingerprint too) PLUS `facts_from_evidence` and `interpretation`
     (narrative, present ONLY in this wider fingerprint, never in the
     economic one) -- populated inside `validate_proposal()` from its
     own `proposal` argument, together with the
     `hypothesis_config_version`/`discovery_config_version` actually
     used; the gate then verifies this wider fingerprint AND that the
     recorded config versions still match what's currently registered,
     re-validating only on a mismatch.**
   Option (i) is simpler, closes the config-staleness question by
   construction, and has no analogous completeness gap, since it
   re-reads the live proposal in full every time. Option (ii), even
   once corrected with the wider validation-input fingerprint above,
   still carries more fields and a staleness check for the sake of
   avoiding one redundant validation pass. **GPT's own explicit
   recommendation, relayed by Radu, this round: option (i) --
   corrected attribution (GPT's technical recommendation, not Radu's
   personal decision absent his own confirmation).** Neither is
   implemented; formally, Radu's own choice, not assumed by this
   document alone -- but (i) is no longer presented as one of two
   equally-weighted alternatives.

**Methodological metadata -- the "existing separate mechanism" named
precisely this round (GPT's review of revision 5, relayed by Radu:
revision 5 named this exclusion but did not say what verifies the
FIRST write is itself truthful):** `variant_tag`/baseline-designation
is deliberately excluded from `variant_fingerprint()` -- it is
evaluation methodology, not economic content. Confirmed by reading
`materialize_variants()` in full: `baseline_time_exit_bars` is a
PLAIN, UNTRACED caller-supplied argument -- nothing records WHERE a
caller's claim that a given horizon "has EXPLICITLY been pre-
designated... before backtesting" (the function's own docstring)
actually comes from, or verifies it against any prior declaration.
`register_variant()`'s full-content immutability (Finding 16's own
mechanism, PATCH #004-B finding #3) only prevents CHANGING
`variant_tag` AFTER its first write -- it proves nothing about
whether that FIRST value was truthful, i.e. that it actually matches
whatever was decided before any evidence/backtest existed, as opposed
to being picked after the fact and simply never touched again.

**Corrected source, verification, and TIMING this round (GPT's review,
relayed by Radu, catching two further gaps in the above):**

**Timing, corrected:** "at proposal time, before any evidence exists"
is WRONG -- Spec #004 proposals already, necessarily, consume Spec
#003 Evaluation evidence (that is exactly what `EvidenceProvenance`
is); evidence legitimately PRECEDES and motivates a proposal. The
actual bias risk this designation guards against is hindsight
temptation created by BACKTEST RESULTS (Spec #005) -- a horizon
retroactively declared "the baseline" after seeing which one performed
best in a backtest. **Corrected statement: the designation must be
frozen before any Spec #005 backtest/exit-engine run ever executes
using these materialized variants** -- not before evidence, which is
both normal and required.

**Linkage, corrected -- confirmed this round, a real gap in the design
above:** `designated_baseline_bars` is (correctly) EXCLUDED from
`_horizon_fp()`/`hypothesis_fingerprint()`, since it is methodology,
not economic content -- but Finding 14's own approval-time
`HumanDecision.content_fingerprint` (above) is built from exactly
those SAME excluding component functions. **If `proposal` and `draft`
are mutated TOGETHER after approval (the SAME scenario `spec004_
remediation_proposal_2026-10-04.md`'s own "Required regression
coverage" section already names for Finding 14 generally), a change to
`designated_baseline_bars` made in lockstep with everything else would
be invisible to BOTH the draft-vs-current-proposal comparison (since
both sides moved together) AND the economic content fingerprint
(since this field isn't part of what it hashes) -- it would simply
never be checked by anything.** **Fix: add a SEPARATE field,
`HumanDecision.approved_designated_baseline_bars: Optional[int]`,
recorded independently at approval time (not derived from or folded
into `content_fingerprint`), verified at the gate to equal the LIVE
`proposal.horizon_candidates.designated_baseline_bars` -- its own
explicit check, specifically because this field is, by design, outside
the economic fingerprint's own coverage.** `preregister_hypothesis()`
then reads `baseline_time_exit_bars` for its call to `materialize_
variants()` FROM `proposal.horizon_candidates.designated_baseline_
bars` exclusively, AFTER this separate check passes -- never as a free
argument supplied independently at the call site. **Consequence:**
closes the gap without touching the economic hash at all (the new
field remains proposal/draft-level methodology, structurally parallel
to `variant_tag`, never part of any content-addressed identity) --
AND without relying on the economic fingerprint to catch a change it
was never designed to catch. **Regression:** a test asserting
`preregister_hypothesis()` rejects a call whose `materialize_
variants()` invocation would tag a DIFFERENT horizon
`BASELINE_VARIANT` than `proposal.horizon_candidates.designated_
baseline_bars` declares; a SEPARATE test asserting rejection when
`proposal`/`draft` are mutated TOGETHER after approval, changing
`designated_baseline_bars` while leaving every economically-hashed
field unchanged (the specific lockstep-mutation gap this round found).

**Finding 15 (GPT-G2), complete contract:** (i) exactly one TIME_EXIT
variant per `horizon_candidate_set.values` entry, no fewer and no
more; (ii) any number of SIGNAL_INVALIDATION/STOP_MANAGED_INVALIDATION
variants, each unique by its FULL content fingerprint (the same
`variant_fingerprint()` definition Finding 14 above reuses, not a
hand-picked field subset -- corrected after the original `(exit_family,
invalidation_conditions)` key was shown to collapse variants differing
only in `max_holding_bars`/`stop_loss`/`partial_profit`); (iii) every
variant's family-specific fields validated per the existing rules
already in `spec004_remediation_proposal...md` section 2.

**Finding 16 (GPT-G3), mechanism and exact guarantee scope, corrected
this round (GPT's review of revision 4, relayed by Radu -- confirmed
by reading `_force_register()`/`register_variant()` in full):**
extract their own preconditions into two named predicate functions
used by BOTH a pre-write dry run and the actual write call (one shared
implementation, so the two cannot independently drift).

**Corrected this round: checking each new item's predicate only
against the INITIAL (pre-batch) registry state is not enough to
guarantee all-or-nothing atomicity for a BATCH.** `preregister_
hypothesis()` writes one hypothesis (`_force_register()`) THEN N
variants (`register_variant()` in a loop) in that same call. If the
dry run checked each of the N variants separately against only the
registry's state BEFORE the batch started, a conflict BETWEEN two
items of the SAME batch (e.g. two variants in `variants` that would
collide with each other, not with anything already stored) would be
invisible to either item's dry-run check -- neither sees the other,
since neither is in the initial state. The dry run would then pass for
every item, the real writes would proceed, and the real write call for
the LATER conflicting item would fail only after the EARLIER one had
already been committed -- a partial write, exactly the atomicity
violation this mechanism exists to prevent.

**Fix: the dry run must simulate the SAME sequential insertion order
the real writes will use, maintaining a virtual registry state that
starts from the actual initial state and is updated (virtually, never
committed) as each item is dry-run-checked** -- hypothesis first
(checked against the initial state), then variant 1 (checked against
initial + the virtually-inserted hypothesis), then variant 2 (checked
against initial + hypothesis + virtual variant 1), and so on through
variant N. Only once every item in this simulated sequence passes does
the function proceed to perform the real writes, in the identical
order -- which are then guaranteed to all succeed, having already been
proven consistent against the exact sequence they will be written in.

**Explicit precondition, stated this round, not previously named:**
this guarantee holds only under SYNCHRONOUS execution with no write
from any OTHER caller interleaved between the dry run and the real
writes on the SAME registry instance -- no locking or concurrency
control is being added here; this is a single-call-sequence
correctness guarantee, not a general concurrency-safe atomicity
mechanism, and must not be described as one.

Guarantees no raise from `ImmutableHypothesisError`'s three documented
conditions (content mismatch; PREREGISTERED-content mismatch; variant
content mismatch) PROVIDED the synchronous-execution precondition
holds. **Does not and cannot guarantee anything outside those three
named conditions** (e.g. a storage-layer failure if the registry is
ever backed by something other than a plain in-memory dict) -- stated
as the guarantee's exact boundary, not implied to be unconditional.

**Findings 17, 18, 20 (GPT-G4, G5, P004C):** unchanged, complete, no
open design question -- widen `register()`'s guard to any-status-to-
PREREGISTERED (17); add `primary_stability_summary` per primary-horizon
bin, justified against SS39's own distinct "stability bins" vs. SS57's
"stability availability" language (18); add `StopLossRule`/
`PartialProfitRule` to `_TYPE_REGISTRY` (20).

**Findings 19/11 (GPT-G6 + Finding 11):** the `RegisteredConfigVersion`
mechanism (one `load_config()` call per operation, immutable per
section 7's full recursive freeze, three-way concordance check) --
wiring to the versioning-epoch marker remains open, shared with S2's
own epoch question (checklist, section 11, row 15).

**Finding 1 (evaluation_mode marking) -- admission policy, concrete
recommendation added this round (per Radu's own request -- a
recommendation with consequences, not only alternatives):** add
`evaluation_mode` to `EvidenceProvenance` and its own fingerprint
input (marking, unchanged from the prior round) -- AND, for the
admission policy itself, **recommend `preregister_hypothesis()` hard-
rejects any proposal whose `source_evidence.evaluation_mode !=
"FORMAL_DEVELOPMENT"`, symmetric with Finding 2's own already-
recommended treatment of `research_mode != PREREGISTERED_STRATEGY`** --
the same reasoning applies on both sides of one evidentiary chain:
Finding 2 already treats a non-confirmed RESEARCH status as
disqualifying outright, not merely flaggable; EXPLORATORY evidence
(found via a less-constrained search, carrying a materially higher
false-discovery risk than a FORMAL_DEVELOPMENT run) warrants the
identical PROCEDURAL treatment on the EVALUATION side, for
consistency, not a weaker marking-only response.

**Overclaim RETRACTED this round (GPT's review, relayed by Radu):
re-running the SAME signature under FORMAL_DEVELOPMENT does NOT, by
itself, "produce fresh, confirmatory evidence" -- that claim is
withdrawn.** Confirmed by reading `engine.py` again this round:
FORMAL_DEVELOPMENT's own actual guarantees are PROCEDURAL --every
signature must already be PRE_REGISTERED (frozen before this
particular evaluation run, with matching timeframe/discovery-version
provenance) and the BH multiple-testing correction is applied across
the family. **Neither guarantee makes the underlying HISTORICAL DATA
new.** Re-running the identical signature over the identical historical
window under a different mode label does not remove whatever
selection bias was introduced when the signature was originally
surfaced by a less-constrained EXPLORATORY search -- it is the same
data, re-labeled, not a new confirmatory test. **Corrected statement:
the hard-reject rule enforces the PROCEDURAL discipline FORMAL_
DEVELOPMENT already provides (pre-registration, BH correction) -- it
does NOT, by itself, resolve the deeper methodological question of
whether the same pattern was already peeked at during the exploratory
phase. Defining a genuine confirmation protocol (e.g. a requirement
that the FORMAL_DEVELOPMENT run cover a held-out/out-of-sample period
the exploratory search never touched) is a separate, substantive,
NOT-resolved-here question -- Radu's own call on whether and how to
define it, not implied by adopting this admission rule.**

**A further gap, closed this round:** the admission check must verify
`evaluation_mode` against the REAL `EvaluationRunRegistry` the
evidence actually traces to, not only trust the caller-declared field
inside `source_evidence` -- mirroring `check_provenance_matches_run()`'s
own existing pattern (confirmed by reading it in full: it currently
checks `evaluation_run_id`/engine and config versions/`signature_set_
id`/`timeframe`, but NOT mode at all). Once `evaluation_mode` is added
to `EvidenceProvenance` (marking, above), `check_provenance_matches_
run()` must ALSO verify `evidence_provenance.evaluation_mode ==
run_registry.mode` (note the field-name asymmetry: `EvaluationRunRegistry`
calls its own field `mode`, not `evaluation_mode`) -- otherwise a
caller could simply DECLARE `"FORMAL_DEVELOPMENT"` in `source_evidence`
for evidence that actually came from a real `EXPLORATORY` run, and
nothing would catch the lie.

**Consequence:** a hypothesis whose evidence traces to an EXPLORATORY
run can no longer reach PREREGISTERED at all, enforced against the
REAL run record, not a self-reported field -- the SAME signature would
need a genuine FORMAL_DEVELOPMENT run (ideally over data the
exploratory phase never saw, per the open confirmation-protocol
question above) before it can be proposed; this is a real process
consequence, not just a bookkeeping field, and its actual statistical
benefit is bounded by whatever confirmation protocol is (separately)
defined. **Regression:** a test asserting `preregister_hypothesis()`
rejects a proposal whose `source_evidence.evaluation_mode ==
"EXPLORATORY"`, mirroring the existing/recommended test pattern for
Finding 2's `research_mode` rejection; a SEPARATE test asserting
rejection when `source_evidence.evaluation_mode` FALSELY claims
`"FORMAL_DEVELOPMENT"` for evidence whose real `EvaluationRunRegistry`
record shows `mode == "EXPLORATORY"` (the mode-vs-registry cross-check
this round added). **Radu's own approval needed:** whether to adopt
the hard-reject policy (with its now-honestly-stated, bounded
benefit), or a weaker marking-only response; and separately, whether
and how to define a genuine out-of-sample confirmation protocol --
neither assumed by this document.

**Finding 2 (research_mode), Finding 10 (exit-family count):**
unchanged from the prior round -- reject `research_mode !=
PREREGISTERED_STRATEGY` outright; count distinct exit-family TYPES
(including the mandatory TIME_EXIT) rather than raw entries, pending
Radu's own call on whether today's stricter behavior was actually
intended.

---

## 11. Checklist -- four axes per item, not one status column

**Rows 9, 11, 12, 14, 15, 18, 20 corrected this round; see
section-by-section corrections above for the reasoning behind each
change. A consolidated regression list follows in section 12.**

**Short decision list, per Radu's own explicit request this round --
NOT a new summary invented fresh, a separation of what the table below
already shows into two buckets, since the table's own column (a) does
exactly this per-row but a short list makes the overall picture
legible at a glance:**

**(A) DESIGN COMPLETE, awaiting Radu's own approval (rows below) --
nothing further needs inventing for these, only his decision:** F2a+
F2b, F6, G2/TEST 34, G1/TEST 26 AST guard (rows 1, 2, 5, 20); Findings
17, 18, 20, 2, 10-direction (rows 3, 4, 6, 13); Finding 16/GPT-G3's
batch-safe dry run (row 8); Finding 15/GPT-G2's full-content variant
key (row 10); Finding 1's marking AND admission-policy recommendation
(row 12); Finding 14/GPT-G1's draft-vs-proposal/human-approval/
baseline-designation binding (row 9); the config-identity mechanism
and S2's separate `run_id_scheme_version` marker, BOTH corrected a
third time this round (rows 14-15); the quantile tie-aggregation
requirement, the WEIGHTED session-mass diagnostic, and the weighted-
permutation-estimator mechanism with its exhaustive-enumeration
regression (all three now fully specified within row 18); TEST 49's
AST algorithm (row 11, EXCEPT the bare-name collision, which is its
own separate, acknowledged-unresolvable item). **MOVED into this
bucket this round: F1's calendar (row 17)** -- source, verification,
coverage, and provenance are now ALL specified by reusing Spec #005's
existing, already-implemented `TradingCalendar` contract (confirmed by
reading `calendar.py` in full this round), with exactly ONE open item
(the strictness-tier choice, named below, not a missing mechanism).

**(B) STILL INCOMPLETE -- no full mechanism exists yet; Radu's
approval would not yet mean anything concrete for these:**
- **#003 S1 (row 16):** a scope/responsibility question (code vs.
  documented trust boundary), not a mechanism gap -- no design exists
  because none has been attempted, this is Radu's own call on scope.
- **Within-bin SESSION-level weighting, as a REAL mechanism** (beyond
  the diagnostic in (A) above): only pursued if Radu judges the
  diagnostic an insufficient response to SS74C -- not designed, since
  not yet known to be needed.
- **Block permutation:** explicitly named, in every round since
  revision 4, as NOT YET DEFINED -- no design exists, deliberately,
  per this project's own existing "v2 if diagnostics show it's needed"
  position (section 5).
- **An out-of-sample confirmation protocol** for the EXPLORATORY-
  evidence admission policy (section 10, Finding 1): named this round
  as the deeper question the admission rule alone does not resolve --
  not designed, Radu's own call on whether and how to define it.

**Attribution, reaffirmed this round per Radu's own explicit
instruction: the midpoint-with-aggregation convention and the gate-
time-revalidation recommendation (Finding 14, option (i)) are GPT's
own technical recommendations, relayed by Radu -- NOT decisions Radu
has made or approved. Nothing in bucket (A) above is an approval;
"design complete" means ready FOR his approval, not already given.**

**Methodological choices, kept SEPARATE from implementation approval
this round, per Radu's own explicit request -- each with a stated
recommendation and its concrete consequence, never a bare list of
alternatives; "design complete" in bucket (A) never implies any of
these has already been decided:**

| Choice | Recommendation (GPT's, relayed by Radu, except where noted) | Concrete consequence if adopted |
|---|---|---|
| F3 common support (option (a) UNAVAILABLE vs. (b) RESTRICTED comparison) | **No recommendation given in any prior round -- stated for the first time this round, grounded in this project's own established fail-closed pattern** (SS11's `CALENDAR_UNVERIFIED`, the PREREGISTERED-only gate): lean toward (a), UNAVAILABLE -- never publish a comparison that doesn't cover the signature's own full population, consistent with "fail closed, don't offer a number for a population the test didn't cover." | (a): some signature/horizon profiles report no `mean_difference`/`raw_p`/CI at all when coverage is incomplete -- fewer numbers, none of them population-mismatched. (b): every profile still gets a number, restricted to common support, with an explicit exclusion count -- more coverage, but requires a reader to notice and interpret the exclusion count correctly every time. |
| F4+F5 within-bin weighting (per-security formula, uncontested) + session-level variation (diagnostic vs. a real second mechanism) | Per-security formula: adopt as designed (uncontested). Session-level: adopt the WEIGHTED `session_mass` diagnostic only (section 3), not a new weighting layer. | Diagnostic-only: Radu's own 5%/95% example becomes visible in the output; the per-security formula's own equal-weight property is preserved untouched; session-level dominance is NOT corrected, only reported -- a further mechanism stays possible later if the diagnostic shows a real problem. |
| Weighted-quantile convention (midpoint vs. `R_i`) | Midpoint with mandatory tie-aggregation (GPT's recommendation, relayed by Radu -- Radu's own personal preference not yet confirmed, per the attribution note above). | Midpoint: simpler, scale-invariant, but never reproduces `statistics.quantiles(..., method="inclusive")`, even at equal weights with no ties. `R_i`: reproduces `inclusive` for DISTINCT, equal-weight input, but loses that property the moment any tie is aggregated (section 4.2's own `[0,0,10]` counterexample) -- neither is a strict superset of the other's guarantees. |
| Permutation exchangeability (accept the value-level procedure's own assumption for V1 vs. require block permutation first) | Accept for V1, as this project's own existing `comparison.py` docstring (SS47) already states; revisit only if concentration/stability diagnostics show a real problem. | Accepting: ships now, with a documented, named limitation (full exchangeability, not merely marginal equality) -- a real but currently unquantified risk under within-security serial correlation. Requiring block first: delays indefinitely, since block permutation has never been given a precise definition in any round. |
| Calendar strictness for #003 (full #005 `OFFICIAL_VERIFIED`-only vs. a looser tier) | **New this round, named precisely rather than assumed:** no recommendation given yet -- genuinely Radu's own call, since it trades off #003's own operational flexibility against the strength of the "verified, not inferred" guarantee section 2 is designed to provide. | Full strictness: #003 runs fail closed whenever no `OFFICIAL_VERIFIED` calendar is available, the same cost #005 already accepts for formal runs. Looser tier: #003 can proceed more often, but its own calendar-based classification (section 1) rests on a weaker verification guarantee than #005's. |

| # | Item | (a) Design complete | (b) Contractual decision needed | (c) Radu's approval | (d) Implementation + verification |
|---|---|---|---|---|---|
| 1 | #003 F2a+F2b | Yes (section 9) | No | Pending | Later stage |
| 2 | #003 F6 | Yes (section 9) | No | Pending | Later stage |
| 3 | #004 Finding 17 | Yes | No | Pending | Later stage |
| 4 | #004 Finding 20 | Yes | No | Pending | Later stage |
| 5 | #003 G2 (TEST 34) | Yes (section 9) | No | Pending | Later stage |
| 6 | #004 Finding 2 | Yes | No | Pending | Later stage |
| 7 | #004 Finding 18 | Yes | No | Pending | Later stage |
| 8 | #004 Finding 16 (GPT-G3) | Yes -- batch-internal simulated-sequential dry run specified (fixes a partial-write gap found this round); explicit synchronous-execution precondition stated; exact 3-condition guarantee scope stated (section 10) | Whether that guarantee scope is sufficient, or a wider one is required | Pending | Later stage |
| 9 | #004 Finding 14 (GPT-G1) | Partial -- `verify_draft_matches_proposal()`, `HumanDecision.content_fingerprint`, and the baseline-designation source/verification (`designated_baseline_bars`, now with its OWN separate `approved_designated_baseline_bars` approval-time check, closing a lockstep-mutation gap found this round) all specified; the designation's own timing corrected to "before any Spec #005 backtest," not "before evidence" (#004 already consumes #003 evidence); option (i) (gate-time revalidation) GPT's own recommendation, relayed by Radu, option (ii) corrected to require a second, WIDER validation-input fingerprint (covering `facts_from_evidence`/`interpretation`) if kept at all (section 10) | Yes -- (i) vs. corrected (ii); not a free choice between equals any more, (i) is GPT's own recommendation | Pending | Later stage |
| 10 | #004 Finding 15 | Yes, full-content key | No remaining design gap identified this round | Pending | Later stage |
| 11 | #004 TEST 49 (AST guard, evaluation->hypothesis) | Partial -- **shared algorithm's two resolution bugs fixed this round** (base+alias candidate construction for `ImportFrom`, corrected `level - 1` relative-import climb, verified by execution against Radu's own `.hypothesis`/`..hypothesis` examples; consolidated positive/negative case matrix added, section 8) -- the ONLY remaining open item is the bare top-level `hypothesis` collision, named as a separate, non-blocking, inherently-unresolvable-by-AST-alone case | Yes -- whether to accept the collision risk via a documented project-convention declaration, or rename the package | Pending | Later stage |
| 12 | #004 Finding 1 | Yes -- marking AND a concrete admission-policy recommendation (hard-reject `evaluation_mode == "EXPLORATORY"`, symmetric with Finding 2's own `research_mode` treatment, verified against the REAL `EvaluationRunRegistry`, not a self-reported field, section 10); the overclaim that re-running under FORMAL_DEVELOPMENT "produces fresh confirmatory evidence" RETRACTED this round -- the rule enforces procedural discipline only, the deeper selection-bias question stays open | Yes -- whether to adopt the hard-reject recommendation or a weaker marking-only response; separately, whether/how to define a genuine out-of-sample confirmation protocol | Pending | Later stage |
| 13 | #004 Finding 10 | Yes (direction) | Yes -- intended-behavior question | Pending | Later stage |
| 14 | #004 Finding 19 / Finding 11 | Yes -- **corrected a THIRD time this round (GPT's review, relayed by Radu): the prior draft compared two INCOMPATIBLE hashes -- fixed by retaining the loader's own raw-text-based version unchanged, and by TWO separate external-object checks (label equality catches wrong-label/right-content; structural equality, both sides normalized to the same representation, catches right-label/wrong-content) rather than one conflated check; the mandatory-live-re-read policy's own justification corrected (design (a) was wrongly described as unsafe -- it isn't, (b) is chosen for an added freshness requirement, not for correctness)** (section 7) | Yes -- whether to adopt this corrected wiring and the mandatory-live-re-read choice, on its corrected justification | Pending | Later stage |
| 15 | #003 S2 | Yes -- but CORRECTED this round: S2 needs its OWN separate `run_id_scheme_version` literal marker, NOT row 14's config-content hash (a `build_run_id()` field-set change is a code change, invisible to any YAML hash) -- two distinct mechanisms now, not one shared wiring as previously drafted (section 7) | Yes -- whether to adopt the separate `run_id_scheme_version` marker | Pending | Later stage |
| 16 | #003 S1 | N/A -- scope question, not a mechanism gap | Yes -- responsibility (code vs. documented trust boundary) | Pending | Later stage |
| 17 | #003 F1 (complete behavior) | **Yes, substantially advanced this round (per Radu's own explicit priority): source/verification/coverage/provenance all now specified by REUSING Spec #005's existing, already-implemented `TradingCalendar` contract** (`calendar_id`/`calendar_hash`, `verify_calendar_content_address()`, `require_calendar_covers_window()`, confirmed by reading `calendar.py` in full) **rather than inventing a parallel mechanism; same-target-session mechanism and 4-way check complete, distinguishing bar-missing from bar-present-with-null-price (section 1)**; sub-daily timeframes out of scope | Yes -- the data-gap status name(s); the calendar relocation decision; **the ONE remaining open item: whether #003's own calendar check needs #005's FULL `OFFICIAL_VERIFIED`-only strictness, or a looser tier for #003's own non-formal purposes (section 2, named precisely, not a mechanism gap)** | Pending | Later stage |
| 18 | #003 F3+F4+F5 | Partial -- per-security formula correct and scoped; session-weighting "impossibility" claim RETRACTED this round (a counterexample shows uniform security AND session margins can coexist), diagnostic mechanism corrected from a raw `Counter` (understates the real skew, verified) to a WEIGHTED `session_mass` sum (section 3); quantile section -- the `R_i`/`inclusive` compatibility claim NARROWED further this round to tie-free, equal-weight ORIGINAL input only, verified by a `[0,0,10]` counterexample that it does not survive mandatory tie-aggregation even at equal weights; non-finite-input contract unified to a hard-fail (section 4); CI/bootstrap estimator-vs-interval separation and F3's field list specified (section 6); permutation section CORRECTED this round -- "ship as-is, docs-only" was wrong once F4+F5's weighting is adopted (would test a different quantity than reported); a full weighted-estimator mechanism is now designed and verified (equal-weight case reduces byte-identical to today's test), the exchangeability-ACCEPTANCE question kept separately open (section 5) | Yes -- F3's (a)/(b) choice; the choice between midpoint and `R_i`; whether the WEIGHTED session-diagnostic recommendation is a sufficient response to SS74C, or a real second mechanism is required (section 3); whether the weighted-permutation-estimator design is adopted, and separately whether to accept the exchangeability limitation for V1 (section 5) | Pending | Later stage |
| 19 | Config immutability (cross-cutting) | Yes -- full recursive freeze specified (section 7) | No | Pending | Later stage |
| 20 | #003 G1 (TEST 26 AST guard, discovery->evaluation) | **Yes -- no longer merely "same algorithm family," the shared algorithm's own bugs are now fixed (row 11), so TEST 26 has no remaining open item of any kind (section 9)** | No | Pending | Later stage |

**No row in this checklist is blocked on "implement and run the
regression matrix" -- that is column (d), explicitly a later,
not-yet-authorized stage, never a condition for this document's own
design-completeness claims in column (a).**

---

## 12. Consolidated regression checklist -- every test named across
this document, in one place (new this round, per Radu's own explicit
request: "un checklist consolidat al regresiilor sau trimiteri exacte
către cele existente")

Defining these tests belongs to the DESIGN stage; running them belongs
to column (d), the later, not-yet-authorized implementation stage --
listed here, none executed.

**Section 1 (F1):** TEST 27's own assertion, restated as a regression
GOAL (CROSSES_LOCKED_OOS fires correctly), not yet a verified result;
NEW -- a case EXERCISING both the bar-missing sub-case (4a) and the
bar-present-with-null-price sub-case (4b), asserting whichever status-
naming policy Radu approves (one shared name, or two distinct names)
is applied CONSISTENTLY -- corrected wording this round (GPT's review,
relayed by Radu): the status-naming choice itself is still open per
section 1's own text (same name permitted as one option), so this
regression must not presuppose the two sub-cases get DIFFERENT
statuses, only that whichever policy is approved is applied the same
way every time.

**Section 2 (calendar):** every EXISTING test currently exercising
`build_trading_calendar()`/`require_verified_calendar_for_formal_run()`
re-run unchanged at its relocated import path; NEW -- a guard test in
the TEST 26/TEST 49 family asserting `src/evaluation/` never imports
`src/backtest/` at all.

**Section 3 (session weighting):** NEW -- the WEIGHTED `session_mass`
diagnostic (summing per-security row weights per session, NOT a raw
`Counter`) reproduces Radu's own 1-security/2-sessions vs.
9-securities/1-session TRUE `5%`/`95%` split (a raw `Counter` would
wrongly give `~9%`/`~91%`, regression-locked as the WRONG answer this
diagnostic must not reproduce); NEW --
`stratified_baseline_point_estimate()`'s output is byte-identical
before/after the diagnostic is added.

**Section 4 (quantiles), the full matrix stated in section 4 itself,
collected here by reference:** unit-weight reproduction of
`statistics.quantiles(..., method="inclusive")` on tie-free input BY
`R_i` SPECIFICALLY (midpoint does not reproduce it even tie-free,
corrected this round); the `[0,0,10]` tied-equal-weight case,
regression-locking that midpoint and `R_i` now DISAGREE post-
aggregation; weight-rescaling invariance across >= 3 scale factors;
input-order permutation of tied rows with DIFFERING weights (the
`[(0,1),(0,3),(10,1)]` vs. `[(0,3),(0,1),(10,1)]` case); mass split vs.
merge at an identical value; zero-weight exclusion; negative-weight
hard-fail; non-finite hard-fail; empty-input `None`;
single-distinct-value input.

**Section 5 (permutation estimator, NEW this round -- design/code/
regression, not docs-only):** the equal-per-security-weight case
reduces BYTE-IDENTICAL to today's existing plain-mean
`stratified_permutation_p_value()` (same observed value, same p-value,
verified this round on a toy fixture -- the natural backward-
compatibility lock); every EXISTING test currently covering
`stratified_permutation_p_value()` re-run and confirmed to still pass
under equal weights. **For UNEQUAL weights, corrected this round
(GPT's review, relayed by Radu): the prior draft verified only the
observed statistic, never the actual p-value mechanics under unequal
weights -- a real gap, since the observed statistic matching alone
does not prove the PERMUTATION/enumeration logic itself is correct.**
**NEW -- full exhaustive-enumeration regression, independently
verified this round:** signature `[8]`; baseline rows `A=[0,2]`
(2 rows), `B=[4]` (1 row), `k=2`; fixed per-row baseline weights
`[1/4, 1/4, 1/2]`; observed difference `8 - 2.5 = 5.5` (verified by
exact-fraction execution); all `4! = 24` orderings of the four pooled
values across the four FIXED positions (1 signature slot, 3 weighted
baseline slots); two-sided test with ties counted as "at least as
extreme" gives EXACTLY `8/24 = 1/3` (verified by exhaustive execution,
not sampled). **This exact enumeration regression must be kept
DISTINCT from, and never conflated with, a Monte Carlo estimate using
the existing add-one continuity correction** (`(extreme+1)/
(iterations+1)`, as `permutation_p_value()`/`stratified_permutation_p_
value()` already use for the iteration-sampled case) -- the exhaustive
count verifies the MECHANICS of the weighted enumeration itself; it
does not and cannot validate the exchangeability assumption, which
remains the separate, open question above.

**Section 6 (bootstrap/F3):** NEW -- `time_block_bootstrap_
replicates()`'s extended `list[tuple[str, str, float]]` signature
(security_id, date, value) recomputes `k_rep`/`n_i_rep` per replicate
from that replicate's OWN composition, not the original sample's fixed
weights; NEW -- the percentile CI step consumes the `B` already-
weighted replicate values UNWEIGHTED (no second weighting pass); NEW --
F3 option (b)'s `signature_mean_relative` restricted to the SAME bin
subset as `baseline_mean` (not just the baseline side).

**Sections 8/9/20 (AST guards, TEST 26 and TEST 49, one shared
matrix):** the exact scratch-file probe already used
(`from src import evaluation as ev` / the TEST 49 equivalent for
`hypothesis`), asserting the guard now fails; PLUS section 8's full
positive/negative case matrix for BOTH guards (substituting the
forbidden name): `import <name>`; `from <name>.x import y`; `from
src.<name> import X`; `from src import <name>` (FLAGGED, all four);
`from vendor import <name>` (NOT flagged); `from .<name> import X` and
`from ..<name> import X` from a 2-deep package (NOT flagged, resolves
to a sibling module, per the corrected `level - 1` climb); `from
...<name> import X` from the same 2-deep package (the corrected
beyond-root boundary, own diagnostic, neither flagged nor silently
passed -- verified this round to trigger at `level=3`, not `level=4`).

**Section 7 (config identity) + S2 (run-id scheme), corrected AGAIN
this round -- the verification mechanism itself was fixed, so these
regressions are restated against the CORRECTED design, not the
incompatible-hash version; which check catches which case is now
stated precisely, corrected from a prior mis-attribution:** config
identity -- a CORRECT-content-WRONG-label case (claimed version string
doesn't match its actual content, though the content itself is fine)
is REJECTED by the LABEL check specifically (never by a second,
independently-recomputed hash, which this round's own execution
confirmed would not even match for LEGITIMATE configs); a SEPARATE
CORRECT-label-WRONG-content case (a hand-built or mutated-before-
freeze object whose label is honest but whose data isn't) is REJECTED
by the STRUCTURAL-CONTENT-EQUALITY check specifically, with both sides
normalized to the same list/tuple representation before comparing
(section 7's own fix this round); a config mutated between approval
and registration is rejected by the now-MANDATORY live re-read against
the pinned, content-verified snapshot; a check that passes operates on
the pinned snapshot afterward, not the original mutable object re-read
again; Discovery's own exact multi-source combination rule
(`"".join(raw_texts)` before hashing) preserved byte-for-byte in the
registered snapshot, never replaced by a different combination rule --
all specified in `spec004_remediation_proposal_2026-10-04.md`'s own
"Required regression coverage" for Finding 19/GPT-G6, collected here
by reference. S2 -- SEPARATELY, and corrected this round: a regression
asserting two runs with IDENTICAL config and every other hashed field
but DIFFERENT `run_id_scheme_version` produce DIFFERENT `evaluation_
run_id`s -- proving the scheme marker is inside `build_run_id()`'s own
fingerprint INPUT, not merely a sibling provenance field (a provenance-
only field would not force this); a SEPARATE regression asserting two
runs differing only in `horizons` (same scheme) also produce different
ids, showing the two axes (config/fields vs. scheme) are each
independently captured by the fingerprint.

**Section 9 (#003 F2a/F2b/F6/G2, already specified there in full,
collected here by reference):** F2a -- a `SignatureSet` built via
`dataclasses.replace()` with mismatched content/id, asserting
`run_evaluation()` now raises; F2b -- a `SignatureSet` with two
definitions sharing one `signature_id`, built the same way, asserting
rejection; F6 -- three tests (family size in a multi-signature
`FORMAL_DEVELOPMENT` run; `family_test_count is None` for every
`EXPLORATORY` profile; `family_test_count` populated for an
`INSUFFICIENT_SUPPORT`-tagged profile with non-`None` `raw_p`); G2 --
the `test_34` fix IS the test, no separate regression.

**Section 10 (#004 mechanisms), NOW including Findings 15/17/18/19/20,
collected by reference from `spec004_remediation_proposal_2026-10-04.
md`'s own "Required regression coverage" section (missing from this
checklist until this round):**
- **Finding 1:** a proposal whose `source_evidence.evaluation_mode ==
  "EXPLORATORY"` is rejected at `preregister_hypothesis()`; SEPARATELY
  -- a proposal whose `source_evidence.evaluation_mode` FALSELY claims
  `"FORMAL_DEVELOPMENT"` while the real `EvaluationRunRegistry` record
  shows `mode == "EXPLORATORY"` is ALSO rejected (the mode-vs-registry
  cross-check added this round).
- **Finding 14:** `verify_draft_matches_proposal()` rejects a draft
  whose content differs from its originating proposal, field by
  field, AND rejects a human-decision/validation-result fingerprint
  mismatch, AND rejects content changed under the SAME approved id
  when `proposal` and `draft` are mutated TOGETHER (not just a draft
  diverging from an unmodified proposal).
- **Finding 14 (baseline designation):** a call whose `materialize_
  variants()` invocation would tag a DIFFERENT horizon
  `BASELINE_VARIANT` than `proposal.horizon_candidates.designated_
  baseline_bars` declares is rejected; SEPARATELY -- rejection when
  `proposal`/`draft` are mutated TOGETHER after approval, changing
  `designated_baseline_bars` while every economically-hashed field
  stays unchanged (the lockstep-mutation gap found this round).
- **Finding 15 (GPT-G2):** both directions of incompleteness (missing
  AND extra TIME_EXIT variants relative to `horizon_candidate_set.
  values`) and at least one invalid exit-semantics case per field
  (`time_exit_bars` sign, `horizon_reference_point`,
  `exit_execution_policy`).
- **Finding 16 (GPT-G3):** the batch-internal simulated-sequential dry
  run catches a conflict BETWEEN two items of the SAME batch (not only
  against the pre-batch registry state) AFTER an earlier item has
  already been inserted into the dry run's own VIRTUAL state --
  **wording corrected this round (GPT's review, relayed by Radu): NOT
  "after it has been written" -- this mechanism never performs a real
  write until the ENTIRE simulated sequence has passed conflict-free,
  so no rollback of a real write is ever needed or offered; demanding
  a test for a conflict found after a REAL write would wrongly imply
  a rollback capability this design does not provide** -- AND a
  conflict where the hypothesis id pre-existed as a DRAFT before the
  call; both must leave the registry in the exact pre-call state (no
  real write having occurred in either case).
- **Finding 17 (GPT-G4):** every public-API transition path into
  PREREGISTERED is rejected, AND the legitimate existing use of
  `register()` (idempotent re-registration of an ALREADY-PREREGISTERED
  record with identical content, e.g. audit-log replay) continues to
  succeed unchanged.
- **Finding 18 (GPT-G5):** stability-bin values placed into the
  `EvidencePacket` are asserted to actually reach it with CORRECT
  values, not merely that a presence flag is set.
- **Finding 20 (P004C):** both nested types round-trip (`StopLossRule`
  AND `PartialProfitRule`), AND a full `STOP_MANAGED_INVALIDATION`
  hypothesis+variant family survives a complete persist-then-reload
  cycle through `JsonlAuditLog.append()`/`replay()`.

---

**No code or test was changed to produce this revision. No new
mathematical counterexample needed executing this round** (the three
local config corrections are wording/attribution fixes to an already-
verified mechanism from revision 8, not new claims needing their own
execution). **This round's source grounding was reading, in full:**
`src/backtest/data/calendar.py` and the relevant sections of
`src/backtest/models/entities.py` (`TradingCalendar`, `CalendarSource`,
`calendar_fingerprint()`, `verify_calendar_content_address()`,
`verify_calendar_structure()`, `require_verified_calendar_for_
formal_run()`, `require_calendar_covers_window()`) -- grounding F1's
calendar design in an EXISTING, already-implemented mechanism rather
than inventing one, per Radu's own explicit priority this round; and
`src/evaluation/engine.py`'s `_resolve_session_dates()`/`run_
evaluation()` again, confirming the CURRENT, unverified session-date
resolution this design replaces -- no project test suite was run.
Baseline `3cdc532`, historical acceptances, and the Spec #005/Batch 3
pause are unchanged. Findings reconciliation remains closed (both
specs, within each review's own declared scope);
remediation design remains open; implementation remains not
authorized.**
