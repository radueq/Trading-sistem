# Joint Remediation Design -- Spec #003 + Spec #004 (2026-10-04, revision 5)

**Status: DESIGN ONLY. Implementation NOT AUTHORIZED.** Revision 5 is a
targeted correction of revision 4, per Radu's own explicit instruction
("corectează punctual aceste mecanisme... fără o nouă rescriere
integrală") -- NOT a full rewrite; sections not listed below as changed
are unchanged from revision 4. GPT's follow-up review of revision 4
(relayed by Radu, independently re-verified this round by direct
execution and by re-reading the actual source) found: a FALSE claim in
section 4 (scale invariance and reproducing `inclusive` at equal
weights do NOT conflict in general -- revision 4's claimed
impossibility is retracted); a real tie-order dependence bug in the
midpoint quantile convention (new, section 4); two overclaims in
section 5's permutation framing, one of them contradicted by the
bootstrap code itself; an AST-guard design (section 8) that would have
produced false NEGATIVES on a real architectural violation targeting a
not-yet-written submodule; an incomplete Finding 14 (#004) design that
never actually ties human approval to specific proposal content; and
several mechanisms the checklist marked "Yes" without their text
present in this document's own body (#003's F2a/F2b/F6/G1/G2 -- added
as new section 9 below, pushing the former sections 9/10 to 10/11).
This review concerns remediation DESIGN only; it does not reopen
findings reconciliation (closed, both specs, within each review's own
declared scope) and does not authorize implementation.

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
verify anything external. A complete #003 design needs, and this
document does not yet provide:
- **Source/version/integrity:** where real session dates come from,
  independent of any price series, with its own version tracked and
  verified before use.
- **Coverage requirement:** the calendar must cover at least through
  `T_target` (section 1.3's check 1) for every session the run touches.
- **Entry/target-beyond-coverage behavior:** named explicitly above
  (section 1.3, check 1) as its own failure mode.
- **Provenance:** which calendar (identity + version) a run used,
  recorded alongside the run's other provenance fields
  (`EvaluationRunRegistry`).

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
language. **Open question, not resolved by this document:** whether a
further, separate within-bin SESSION-level normalization is also
needed, layered on top of (not instead of) the per-security formula.

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
project's chosen convention** -- it only establishes that the choice
between the midpoint convention (`P_i`, simpler, does not reproduce
`inclusive` at equal weights) and the rescaled convention (`R_i`,
reproduces `inclusive` at equal weights, requires `n>=2` support
points and a well-defined `P_n - P_1 != 0`, i.e. more than one
distinct value with positive weight) is a genuine, open design choice
-- **both remain live candidates; Radu's own choice between them is
needed, not assumed by either revision 4's withdrawn claim or this
correction.**

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

**Contract completion, the remaining boundary cases (none verified by
execution this round beyond the two above -- stated as design
requirements for Radu's review, consistent with patterns already
established elsewhere in this codebase):** zero-weight rows are
excluded entirely before aggregation (mirrors the existing `if weight
<= 0: continue` pattern in `bootstrap.py`'s
`stratified_baseline_bootstrap_replicates()` and
`comparison.py`'s `stratified_permutation_p_value()`); a negative
weight is a hard-fail input error, never silently clamped or dropped;
a non-finite value or weight (`NaN`/`inf`) is excluded (mirrors the
existing `is None`/finiteness-style exclusion pattern in
`outcomes/forward_returns.py`); an empty input (no positive-weight
rows survive) returns `None` for every requested quantile (mirrors the
existing `if not pools: return None` pattern in
`comparison.py`); a single distinct value with all remaining positive
weight returns that value for every `p`, trivially, under either
convention. **Recommended regression matrix, not yet implemented:**
unit-weight reproduction of `statistics.quantiles(..., method=
"inclusive")` (both conventions, for `R_i`; midpoint only needs its
own stated non-reproduction verified, not asserted equal); weight-
rescaling invariance across at least three distinct scale factors (as
verified above); input-order permutation of tied-value rows (as
verified above, both pre- and post-aggregation-fix); splitting one
row's weight into several rows at the identical value vs. one merged
row (must agree, by construction, once aggregation is applied); zero-
weight exclusion; negative-weight rejection; non-finite rejection;
empty-input `None`; single-distinct-value input. **Radu's own approval
needed for: which convention (midpoint vs. rescaled) to adopt, and
confirmation of the tie-aggregation requirement -- neither assumed by
this document.**

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
2. **For an ABSOLUTE import** (`ast.Import`'s `alias.name`, or
   `ast.ImportFrom` with `node.level == 0`'s `node.module` AND every
   `alias.name` in `node.names`, per the collector fix already
   established in revision 3): strip a leading `"src."` if present;
   the import is a FORBIDDEN hit if and only if the FIRST remaining
   dotted component equals the forbidden namespace's own top-level
   package name exactly (`"hypothesis"` for TEST 49's own direction) --
   **matching the first component only, correcting revision 3/4's
   own `"hypothesis" in m.split(".")` substring-anywhere-in-the-path
   matcher**, which would also flag an UNRELATED namespace that merely
   happens to have a submodule sharing that literal name (e.g. a
   hypothetical `vendor.hypothesis` package, first component `vendor`,
   is not this project's `hypothesis` package and must not be flagged;
   `"hypothesis" in "vendor.hypothesis".split(".")` would wrongly flag
   it under the prior matcher).
3. **For a RELATIVE import** (`ast.ImportFrom` with `node.level > 0`):
   resolve it to its EFFECTIVE absolute dotted path starting from the
   ANALYZED FILE's own package (derived from the file's path under
   `src/` -- e.g. `src/evaluation/baseline/universe.py` has package
   `evaluation.baseline`), climbing up `node.level` components from
   that package and then appending `node.module` (if any); apply rule
   2's first-component check to the resolved path. **Confirmed this
   round: zero relative imports exist anywhere in `src/` today**
   (`grep -rn "^from \.\|^from \.\."` -> no matches) -- this closes a
   gap in the CONTRACT (a future relative import could otherwise slip
   past an absolute-only matcher) without fixing any currently-active
   false negative, since none exists today.
4. **Filesystem existence is demoted to a non-gating, informational
   signal only** -- it MAY be used to enrich an error message (e.g.
   "no such module exists yet at this path") but must NEVER decide
   whether an import is flagged; the architectural ban is about
   NAMESPACE membership, independent of whether any particular
   submodule has already been written.

**This same algorithm applies uniformly to every guard of this
structural shape in the codebase** -- Spec #002's TEST 17/18, Spec
#003's TEST 26 (discovery cannot import evaluation, see new section 9
below), and Spec #004's TEST 49 (worked through above) all share the
identical collector/matcher defect pattern and the identical fix;
TEST 26 does not carry the name-collision concern below (no known
third-party package named `evaluation` is in use or anticipated here),
so its own fix is simpler and fully specified, with no open
contractual question (section 9).

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
Finding 18), same defect family as section 8 above, simpler and fully
specified, no open contractual question:** `_imported_modules()` never
inspects `ast.ImportFrom`'s `names` (the imported symbols), only
`.module` -- so `from src import evaluation as ev` inside
`src/discovery/` is invisible to the guard. Fix: collect `alias.name`
for each name in `node.names` when the node is an `ast.ImportFrom`,
exactly as section 8's corrected collector already requires for TEST
49; apply section 8's same first-component matching rule (no
`evaluation`-name third-party collision is known or anticipated, so
TEST 26 needs none of section 8's collision caveat). Test needed: a
regression using the exact scratch-file probe already used to
demonstrate this (`from src import evaluation as ev`), asserting the
guard now fails as expected.

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
   content and the same config -- two options, Radu's own choice
   between them, not decided here:**
   - **(i), recommended as the simpler fit with this codebase's own
     established pattern** of never trusting a cached derived value
     (the same philosophy behind recomputing `hypothesis_id`/
     `definition_hash` at the gate instead of trusting a caller's
     claim): have `preregister_hypothesis()` RE-RUN `validate_
     proposal()` itself, on the live `proposal` argument, against
     whatever `HypothesisConfig`/`DiscoveryConfig` versions are
     currently registered for this operation (tied to Finding 19/11's
     `RegisteredConfigVersion` mechanism, section 7) -- removing the
     cached `proposal_validation.valid` flag from the trust boundary
     entirely, since there is then nothing cached to go stale.
   - **(ii), the alternative GPT itself named:** keep the cached
     `ProposalValidationResult`, but add `content_fingerprint: str`
     (the same canonical fingerprint as above) AND the
     `hypothesis_config_version`/`discovery_config_version` actually
     used, populated inside `validate_proposal()` from its own
     `proposal` argument; the gate then verifies both the content
     fingerprint and that the recorded config versions still match
     what's currently registered, re-validating only on a mismatch.
   Option (i) is simpler and closes the config-staleness question by
   construction; option (ii) avoids one redundant validation pass at
   the cost of carrying two more fields and a staleness check. Neither
   is implemented; **Radu's own choice, not assumed.**

**Methodological metadata, explicitly carved OUT of this binding:**
`variant_tag`/baseline-designation (added by PATCH #004-A finding #5)
is deliberately excluded from `variant_fingerprint()` -- it is
evaluation methodology, not economic content (Finding 16/`register_
variant()`'s own docstring already states this exclusion). This
section's content-fingerprint binding covers ONLY trading-meaning
fields; baseline designation continues to be tracked by its own
existing, separate mechanism and must never be folded into, or
confused with, the content fingerprint above.

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

**Finding 1 (evaluation_mode marking), Finding 2 (research_mode),
Finding 10 (exit-family count):** unchanged from the prior round --
add `evaluation_mode` to `EvidenceProvenance` and its own fingerprint
input; reject `research_mode != PREREGISTERED_STRATEGY` outright;
count distinct exit-family TYPES (including the mandatory TIME_EXIT)
rather than raw entries, pending Radu's own call on whether today's
stricter behavior was actually intended.

---

## 11. Checklist -- four axes per item, not one status column

**Row 9 and row 8 downgraded/corrected, row 11 relabeled, row 20
added, row 18/19 reworded this round -- see section-by-section
corrections above for the reasoning behind each change.**

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
| 9 | #004 Finding 14 (GPT-G1) | **PARTIAL this round (downgraded from "Yes" -- GPT's review of revision 4, relayed by Radu, found the gate never cross-checks draft content against the originating proposal at all, confirmed by reading the gate code in full):** `verify_draft_matches_proposal()` specified; `HumanDecision.content_fingerprint` binding specified; methodological-metadata carve-out stated (section 10) | Yes -- choice between gate-time proposal revalidation (recommended) and a content-fingerprint-plus-config-version field on the cached `ProposalValidationResult` (section 10) | Pending | Later stage |
| 10 | #004 Finding 15 | Yes, full-content key | No remaining design gap identified this round | Pending | Later stage |
| 11 | #004 TEST 49 (AST guard, evaluation->hypothesis) -- **relabeled this round; was mislabeled "#003 G1" in revision 4** | Partial -- namespace-first-component matcher + relative-import resolution specified, filesystem demoted to non-gating (section 8, corrected this round after the prior filesystem-gating design was found to produce false negatives); bare top-level `hypothesis` collision named as a separate, non-blocking, inherently-unresolvable-by-AST-alone case | Yes -- whether to accept the collision risk via a documented project-convention declaration, or rename the package | Pending | Later stage |
| 12 | #004 Finding 1 | Yes (marking); policy question separate | Yes -- admission policy, jointly with #003's own OOS-discipline framing | Pending | Later stage |
| 13 | #004 Finding 10 | Yes (direction) | Yes -- intended-behavior question | Pending | Later stage |
| 14 | #004 Finding 19 / Finding 11 | Partial -- mechanism named; epoch-marker wiring open | Yes -- versioning-epoch marker, jointly with #003 S2 | Pending | Later stage |
| 15 | #003 S2 | Partial -- fingerprint extension uncontested; epoch-marker open | Yes -- versioning-epoch marker | Pending | Later stage |
| 16 | #003 S1 | N/A -- scope question, not a mechanism gap | Yes -- responsibility (code vs. documented trust boundary) | Pending | Later stage |
| 17 | #003 F1 (complete behavior) | Partial -- same-target-session mechanism and 4-way check complete, now distinguishing bar-missing from bar-present-with-null-price as separate sub-cases (section 1, corrected this round); calendar sourcing and dependency direction open (section 2); sub-daily timeframes out of scope | Yes -- the data-gap status name(s), now covering both the bar-missing and the bar-present-null-price sub-cases; the calendar sourcing/relocation decision | Pending | Later stage |
| 18 | #003 F3+F4+F5 | Partial -- per-security formula correct and scoped (section 3); **TWO candidate scale-invariant quantile conventions specified and verified this round (midpoint, and a rescaled variant that also reproduces `inclusive` at equal weights), plus a required tie-aggregation rule (verified fix for an order-dependence bug found this round) -- NEITHER convention chosen yet (section 4, corrected this round after an incorrect "impossibility" claim was retracted)**; CI/bootstrap estimator-vs-interval separation specified, F3's exact restricted-vs-unrestricted field list now enumerated (section 6); permutation section corrected this round to remove two overclaims, still fully open (section 5) | Yes -- F3's (a)/(b) choice; **the choice BETWEEN the two scale-invariant quantile conventions (section 4.2), not a single tradeoff as framed in revision 4**; whether within-bin session-level variation needs its own fix (section 3); the permutation null-model choice (section 5) | Pending | Later stage |
| 19 | Config immutability (cross-cutting) | Yes -- full recursive freeze specified (section 7) | No | Pending | Later stage |
| 20 | #003 G1 (TEST 26 AST guard, discovery->evaluation) -- **new row this round; previously absent from the checklist entirely** | Yes -- same algorithm family as row 11, fully specified, no collision caveat applies (section 9) | No | Pending | Later stage |

**No row in this checklist is blocked on "implement and run the
regression matrix" -- that is column (d), explicitly a later,
not-yet-authorized stage, never a condition for this document's own
design-completeness claims in column (a).**

**No code or test was changed to produce this revision. This round's
verification was, again, isolated Python execution only -- never the
project's own test suite:** the `R_i` rescaled-quantile counterexample
(section 4.2, disproving revision 4's impossibility claim); the tie-
order-dependence counterexample and its aggregation fix (section 4,
new this round); re-confirmation of Radu's own exact-fraction worked
example (section 4.3); the `grep` checks confirming zero `src.`-
prefixed and zero relative imports in `src/` (section 8, re-confirmed
this round). This round's source grounding also included reading, in
full, `registry/preregistration.py`, `validation/rules.py`,
`proposals/validator.py`, the relevant sections of `models/entities.py`
and `registry/hypotheses.py` (Finding 14/16's corrections), `outcomes/
forward_returns.py` (F1's correction), `statistics/bootstrap.py`
(the permutation section's correction), `tests/spec004/
test_49_evaluation_cannot_import_hypothesis.py`, and
`spec003_remediation_proposal_2026-10-04.md`'s F2a/F2b/F6/G1/G2
sections (new section 9) -- no project test suite was run. Baseline
`3cdc532`, historical acceptances, and the Spec #005/Batch 3 pause are
unchanged. Findings reconciliation remains closed (both specs, within
each review's own declared scope); remediation design remains open;
implementation remains not authorized.**
