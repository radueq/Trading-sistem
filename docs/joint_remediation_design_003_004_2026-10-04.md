# Joint Remediation Design -- Spec #003 + Spec #004 (2026-10-04, revision 4)

**Status: DESIGN ONLY. Implementation NOT AUTHORIZED.** Revision 4,
written as a self-contained design document per Radu's own explicit
instruction, not a diff against revision 3. Revision 3 corrected
several revision-2 errors but left a scale-invariance bug in its own
quantile algorithm (caught by GPT's follow-up review, relayed by Radu,
and independently re-verified by direct execution this round -- see
section 4.2) plus five further gaps. This review concerns remediation
DESIGN only; it does not reopen findings reconciliation (closed, both
specs, within each review's own declared scope) and does not authorize
implementation.

**Checklist convention used throughout (Radu's own structure):** every
item is tracked on four separate axes, never collapsed into one
"status": **(a) design completeness** -- is a concrete, correct
mechanism specified; **(b) contractual decision** -- is there a
semantic/behavior choice only Radu can make; **(c) Radu's approval** --
not given by this document, tracked separately per item in section 10;
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
   consulted for a bar at exactly `T_target`. If present: `VALID`
   (return computed from it). If absent: the data-gap status
   (distinct from both `CROSSES_LOCKED_OOS` and `INSUFFICIENT_FUTURE_
   DATA` -- Radu's own semantic naming call, unresolved, same as every
   prior round).

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
coincidentally agrees here). **This is the declared tradeoff Radu's
own message asks for: scale invariance and exact `inclusive`-
reproduction at equal weights cannot both hold in general** (`inclusive`
is inherently a finite-count convention; relative weights have no
count to be finite about). **Recommended: adopt the scale-invariant
midpoint convention for every relative-weight use in this project**
(F4+F5's baseline statistics; nowhere else in this codebase currently
computes a weighted quantile), accepting the stated deviation from
`inclusive` at equal weights as the necessary consequence -- **Radu's
own approval needed for this specific tradeoff, not assumed.**

### 4.3 The worked example, recomputed with the corrected algorithm --
exact fractions, verified by execution

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
grouping rationale). **Corrected framing:** the procedure is VALID
under the assumption that, conditional on which security/session
produced each observation, the recorded values are mutually
independent draws from a common distribution (full exchangeability,
not just equal marginals) -- stated as the REQUIRED assumption, not
claimed as automatically satisfied. **Block/cluster permutation
(shuffling each security's entire row-set as one unit) has NOT been
given its own precise definition in any round so far** -- naming it as
"an alternative" without defining it is not a comparison, just a
placeholder. **Both remain open,** with the value-level procedure
representing the weaker, more standard assumption (used throughout the
rest of this codebase's own permutation/bootstrap machinery, which
already treats row-level values as the unit of resampling) and
block-permutation representing a more conservative, NOT YET DEFINED
alternative that would need its own full specification (how pooled
candidate groups are formed when the raw-row target count `n_sig`
doesn't align with whole-security block boundaries) before any
validity comparison is possible.

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

**The matcher fix (`"hypothesis" in m.split(".")`) is necessary but
not sufficient -- it can also flag an UNRELATED namespace.** Concrete,
verified-real negative case (not a hypothetical): `hypothesis` is the
name of a well-known, commonly-used third-party PROPERTY-BASED TESTING
library on PyPI -- confirmed NOT currently installed in this project
(`pip show hypothesis` -> not found) and not referenced in any
requirements file (checked this round), but a plausible FUTURE
addition for property-based tests. **If it were ever added, `import
hypothesis` or `from hypothesis import given` (its own real API) would
be syntactically IDENTICAL, at the AST level, to this project's own
`import hypothesis`/`from hypothesis import X` style** -- both use the
same bare top-level name, because this project's own package is
imported unqualified (`from hypothesis.models.entities import X`, not
`from trading_sistem.hypothesis.models.entities import X`). **Static
AST analysis cannot disambiguate these two cases for a bare top-level
`import hypothesis` or `from hypothesis import <name>`** -- this is an
inherent limitation of the project's own current unqualified-import
style, not something the guard's matcher logic can fix by itself.

**Partial, real mitigation:** for a DOTTED path (e.g. `hypothesis.
registry.hypotheses`, or `from hypothesis.registry import hypotheses`),
resolve the path against the actual filesystem -- flag it only if
`src/hypothesis/<rest-of-path>.py` (or `__init__.py`) actually exists
on disk. This correctly avoids flagging a coincidentally-similar but
nonexistent dotted path, and correctly still catches every real
internal-package form, including the prefixed `src.hypothesis.X` case
from the previous round. **It does NOT resolve the bare top-level
`import hypothesis` ambiguity** -- both the real internal package and
the hypothetical third-party library would resolve to "yes, `src/
hypothesis/__init__.py` exists," without telling us which one a given
import statement actually intends. **Recommended, not decided:**
document this collision as a standing project constraint (the
third-party `hypothesis` library must never be added as a dependency
while the internal package keeps this unqualified name), rather than
attempt to resolve it at the AST-guard level, where it cannot be
resolved. **Relative imports:** confirmed zero usage in `src/` today
(`grep -rn "^from \.\|^from \.\."`, re-confirmed this round); `node.
level`/`node.module is None` handling remains a named, unaddressed
residual limitation given that confirmed absence.

---

## 9. #004 mechanisms -- reintegrated in full (not only as deltas)

**Finding 14 (GPT-G1), complete mapping:** the approved-content
fingerprint covers `direction`, `entry_definition`, `entry_execution_
policy`, `horizon_candidate_set` (values + `parameter_source`/
`selection_basis`), AND the proposal's own `exit_hypotheses`
(canonical content, via the existing `_exit_fp()`/`variant_
fingerprint()` definition -- corrected in the prior round after the
fingerprint was found to omit exits entirely). Recorded once, on the
human-decision record, at approval time -- never recomputed from
whatever a later caller supplies. At the gate: recompute the identical
fingerprint from the draft's own corresponding fields plus the exit
content actually used to materialize variants, compare against the
frozen approved value, THEN (only after that comparison passes) replay
`materialize_variants()` to verify the registered variants match.
`horizon_candidate_set.values` -> `materialize_variants()`'s own
TIME_EXIT expansion is the one and only allowed "derivation" step
(verified by replay-equality, not by hashing, since it is a
one-to-many expansion); every other field requires exact identity.

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

**Finding 16 (GPT-G3), mechanism and exact guarantee scope:** extract
`_force_register()`'s and `register_variant()`'s own preconditions
into two named predicate functions used by BOTH a pre-write dry run
and the actual write call (one shared implementation, so the two
cannot independently drift). Guarantees no raise from
`ImmutableHypothesisError`'s three documented conditions (content
mismatch; PREREGISTERED-content mismatch; variant content mismatch).
**Does not and cannot guarantee anything outside those three named
conditions** (e.g. a storage-layer failure if the registry is ever
backed by something other than a plain in-memory dict) -- stated as
the guarantee's exact boundary, not implied to be unconditional.

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
own epoch question (section 11).

**Finding 1 (evaluation_mode marking), Finding 2 (research_mode),
Finding 10 (exit-family count):** unchanged from the prior round --
add `evaluation_mode` to `EvidenceProvenance` and its own fingerprint
input; reject `research_mode != PREREGISTERED_STRATEGY` outright;
count distinct exit-family TYPES (including the mandatory TIME_EXIT)
rather than raw entries, pending Radu's own call on whether today's
stricter behavior was actually intended.

---

## 10. Checklist -- four axes per item, not one status column

| # | Item | (a) Design complete | (b) Contractual decision needed | (c) Radu's approval | (d) Implementation + verification |
|---|---|---|---|---|---|
| 1 | #003 F2a+F2b | Yes | No | Pending | Later stage |
| 2 | #003 F6 | Yes | No | Pending | Later stage |
| 3 | #004 Finding 17 | Yes | No | Pending | Later stage |
| 4 | #004 Finding 20 | Yes | No | Pending | Later stage |
| 5 | #003 G2 (TEST 34) | Yes | No | Pending | Later stage |
| 6 | #004 Finding 2 | Yes | No | Pending | Later stage |
| 7 | #004 Finding 18 | Yes | No | Pending | Later stage |
| 8 | #004 Finding 16 | Yes, with exact 3-condition guarantee scope stated | Whether that scope is sufficient, or a wider guarantee is required | Pending | Later stage |
| 9 | #004 Finding 14 | Yes, exit content now included | No remaining design gap identified this round | Pending | Later stage |
| 10 | #004 Finding 15 | Yes, full-content key | No remaining design gap identified this round | Pending | Later stage |
| 11 | #003 G1 (AST guard) | Partial -- matcher + filesystem-resolution specified; bare top-level `hypothesis` collision named as inherently unresolvable by AST alone | Yes -- whether to accept the collision risk, document it as a standing constraint, or rename the package | Pending | Later stage |
| 12 | #004 Finding 1 | Yes (marking); policy question separate | Yes -- admission policy, jointly with #003's own OOS-discipline framing | Pending | Later stage |
| 13 | #004 Finding 10 | Yes (direction) | Yes -- intended-behavior question | Pending | Later stage |
| 14 | #004 Finding 19 / Finding 11 | Partial -- mechanism named; epoch-marker wiring open | Yes -- versioning-epoch marker, jointly with #003 S2 | Pending | Later stage |
| 15 | #003 S2 | Partial -- fingerprint extension uncontested; epoch-marker open | Yes -- versioning-epoch marker | Pending | Later stage |
| 16 | #003 S1 | N/A -- scope question, not a mechanism gap | Yes -- responsibility (code vs. documented trust boundary) | Pending | Later stage |
| 17 | #003 F1 (complete behavior) | Partial -- same-target-session mechanism and 4-way check complete (sections 1); calendar sourcing and dependency direction open (section 2); sub-daily timeframes out of scope | Yes -- the data-gap status name; the calendar sourcing/relocation decision | Pending | Later stage |
| 18 | #003 F3+F4+F5 | Partial -- per-security formula correct and scoped (section 3); quantile algorithm now scale-invariant and verified (section 4); CI/bootstrap estimator-vs-interval separation specified (section 6); permutation exchangeability assumption stated but validity still open (section 5) | Yes -- F3's (a)/(b) choice; the scale-invariant-vs-inclusive quantile tradeoff (section 4.2); whether within-bin session-level variation needs its own fix (section 3); the permutation null-model choice (section 5) | Pending | Later stage |
| 19 | Config immutability + AST (cross-cutting) | Partial -- full recursive freeze specified (section 7); AST filesystem-resolution specified, bare-name collision named unresolvable (section 8) | Yes -- the `hypothesis`-name collision policy | Pending | Later stage |

**No row in this checklist is blocked on "implement and run the
regression matrix" -- that is column (d), explicitly a later,
not-yet-authorized stage, never a condition for this document's own
design-completeness claims in column (a).**

**No code or test was changed to produce this revision. Only the
isolated mathematical checks described above (quantile scale-
invariance, the corrected worked example, the `hypothesis` package
collision check) were executed this round -- no project test suite was
run. Baseline `3cdc532`, historical acceptances, and the Spec
#005/Batch 3 pause are unchanged. Findings reconciliation remains
closed (both specs, within each review's own declared scope);
remediation design remains open; implementation remains not
authorized.**
