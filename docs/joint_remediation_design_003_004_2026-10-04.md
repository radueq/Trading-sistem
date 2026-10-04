# Joint Remediation Design -- Spec #003 + Spec #004 (2026-10-04, revision 3)

**Status: DESIGN ONLY. Implementation NOT AUTHORIZED.** Revision 3,
correcting eight substantive problems GPT's own follow-up review
(relayed by Radu) found in revision 2 -- several by catching a genuine
arithmetic error in this document's own worked example, verified
independently this round (see section 3.2). **This revision downgrades
several rows revision 2 marked "Complete" back to "design advanced, not
complete"** -- see the revised checklist (section 8). Nothing in this
document authorizes implementation or claims a test result that was
not actually produced.

---

## 1. F1 -- classification and the return calculation must resolve to
the SAME exit, not two independently-computed ones

**The coherence bug revision 2 missed, Radu's own example:** calendar
sessions `E, S1, S2, S3`; `N = 2`; `development_end = S2`; the
security's own bars exist at `E, S2, S3` (missing `S1` -- a genuine
data gap for this one security). Revision 2's calendar-based
classification: 2 sessions forward from `E` on the calendar is `S2`,
which is `<= development_end` -- NOT classified `CROSSES_LOCKED_OOS`.
But the CURRENT implementation's own return calculation counts `N`
bars forward THROUGH THE SECURITY'S OWN BAR LIST, which skips the
missing `S1` silently: the security's own bar at position `entry_idx +
2` is `S3` (position 0=`E`, position 1=`S2`, position 2=`S3`, since
`S1` simply isn't in this security's own list) -- `S3` is PAST
`development_end`. So classification says "not OOS, exits at S2" while
the actual return-computation mechanism would have picked `S3` --
**two different, uncoordinated answers to "what is this hypothesis's
exit," one of them genuinely OOS.** Revision 2 did not define this
case at all.

### 1.1 Recommended fix -- one target session, used for both purposes

**For the `1D` timeframe:** compute `expected_exit_date` from the
calendar exactly as revision 2 did (session `N` steps forward from the
entry session). This SAME date is now used for BOTH classification AND
locating the exit bar -- never "the Nth bar the security happens to
have, skipping gaps." Concretely:
- If `expected_exit_date > development_end`: `CROSSES_LOCKED_OOS` (as
  before, section 2.3 of revision 2, unchanged).
- Else: look up the security's bar AT EXACTLY `expected_exit_date`.
  **If that exact bar does not exist, the outcome is a missing-data
  status -- the exit is never shifted to the security's next
  available bar.** This replaces the current implementation's own
  `exit_idx = entry_idx + horizon_bars` positional counting, which
  silently treats "skip past a gap" as equivalent to "N bars forward"
  -- it is not. **Re-applying Radu's own example under this fix:**
  target `S2`, security has a bar exactly at `S2` -> uses that bar,
  `VALID`, no incoherence. A variant of the example (entry at `S1`
  instead, if the security were missing `S2` instead of `S1`) would
  correctly produce the missing-data status at `S2`, never a return
  computed from `S3` pretending to be "the 2-bars-forward exit."
- **Benchmark alignment:** the same exact-target-session discipline
  must apply to the benchmark's own bar lookup for the relative-return
  side of the outcome, not only the security's side -- both sides of
  one forward-return computation need to agree on which calendar
  session is "the exit," or the two could independently drift onto
  different actual dates under their own gap patterns.

**This is a genuine, visible behavior change from what exists today**
(today's gap-skipping is implicit and untested as its own behavior) --
presented here explicitly for Radu's own approval, not as a
transparent refactor.

### 1.2 Sub-daily timeframes -- explicitly NOT resolved by this design

This section's mechanism is specified for `1D` only. A daily session
calendar (`E, S1, S2, S3, ...`) says nothing about how many bars exist
WITHIN a single session for a sub-daily timeframe (e.g. `4H`) -- that
needs a separate, timeframe-specific intraday bar grid (how many `4H`
bars per session, and their own boundary alignment to session
open/close), which this document does not design. **Named as an open
gap, not silently assumed solved by reusing the daily calendar.**

### 1.3 "TEST 27 ... confirmed still passing" -- retracted

Revision 2 asserted TEST 27 would keep passing under the new
mechanism. **That claim is withdrawn -- nothing was implemented or run
to support it.** The correct framing: TEST 27's own assertion
(`any(crosses_locked_oos > 0 ...)`) is a REGRESSION GOAL this
mechanism is designed to satisfy (since `CROSSES_LOCKED_OOS` still
fires via the calendar lookup, independent of what's fetched) -- not a
verified result. Confirming it requires an actual implementation and
test run, neither of which has happened.

---

## 2. The calendar source -- a constructor, not a verified provider;
the dependency direction it creates

**Error in revision 2:** `build_trading_calendar()`
(`backtest/data/calendar.py`) takes `session_dates` as a caller-
supplied PARAMETER -- it sorts/dedups and content-addresses whatever
it's handed; it does not itself fetch or verify anything from an
external source. Calling this "a separately-sourced, price-independent
list" was true of the TYPE's shape, not of any claim that a populated,
verified INSTANCE is actually available to #003. Whether Spec #005
itself already has a populated, verified `TradingCalendar` instance
anywhere (vs. only the constructor/validation machinery) was not
checked this round and is not assumed here.

### 2.1 What #003's own design must specify (not yet specified)

- **Source, version, integrity verification:** where the actual
  session dates come from (an external market-calendar source, not
  derived from any price series), how that source's own version is
  tracked, and how its integrity is checked before use -- mirroring
  the same discipline SS11 already requires of #005's own calendar
  input, not assumed inherited by reusing the TYPE.
- **Coverage requirement:** the calendar's own declared coverage must
  extend at least to the target session computed in section 1 -- if it
  doesn't, that is itself a distinct failure mode (calendar coverage
  incomplete), not silently treated as "insufficient future data" or
  "data gap."
- **Entry session missing from the calendar, or target beyond
  coverage:** both need an explicit, named behavior -- not left as an
  implicit crash or silent fallback.
- **Provenance:** which calendar (identity + version) was used for a
  given run needs to be recorded in that run's own provenance, the
  same way every other input to Evaluation's output is already
  tracked (`EvaluationRunRegistry`'s own fields).

None of the four points above is designed in this document; they are
named as what a complete design needs, replacing revision 2's implicit
assumption that "reuse the type" settles sourcing.

### 2.2 The dependency-direction problem

**"Read-only" does not eliminate a new package-level import
dependency.** If `src/evaluation/` imports anything from
`src/backtest/` (even only `TradingCalendar`/`build_trading_calendar`,
never the SS11 gate functions), that is a NEW edge in the dependency
graph running Backtest -> Evaluation -- the OPPOSITE direction from
the one-way chain this project has repeatedly verified (Data
Foundation -> Discovery -> Evaluation -> Hypothesis -> Backtest) across
every prior audit round. Revision 2's "read-only use is fine" claim is
wrong on this point. **Recommended correction:** do not import from
`backtest` at all. Either (a) relocate the calendar TYPE (and whatever
minimal construction/validation logic #003 actually needs) to a
neutral location both `evaluation` and `backtest` can import from
without creating a cross-edge -- most naturally Data Foundation, since
calendar data is a data-sourcing concern, not an Evaluation- or
Backtest-specific one -- or (b) have `evaluation` define and source its
OWN calendar object independently, accepting duplication over a
reversed dependency. **This is itself a decision needing Radu's own
sign-off, not assumed resolved by "read-only."**

---

## 3. F3 + F4 + F5 -- corrected mathematics

### 3.1 The per-security weight formula resolves ROW-COUNT dominance
within a security, not SESSION-level universe-size variation within a
bin -- these are different properties

**Radu's own example, verified:** one bin; security A has rows in 2
sessions; 9 other securities each have a row in only the SECOND of
those 2 sessions (10 distinct securities total in the bin: A + 9
others). Under `w = W_b / (k * n_i)` with `k=10`: A's 2 rows each get
`W_b/20`; each of the 9 others' single row gets `W_b/10`. **Session 1's
total weight = A's one row there = `W_b/20` = 5% of the bin. Session
2's total weight = A's other row (`W_b/20`) + 9 others (`9*W_b/10`) =
95% of the bin.** The per-security formula correctly equalizes A's
TOTAL weight against every other security's total weight (`W_b/10`
each) -- but it does nothing to prevent one SESSION within the bin from
carrying 19x the weight of another, purely because more securities
happened to be observable that session. **This document's prior claim
that the formula resolves F4+F5 is corrected: it resolves the
per-security row-count dominance F5's own reproduction demonstrated; it
does NOT address within-bin, cross-session universe-size variation,
which SS74C's own "periods with very large universe" language may
also be read to cover.** Whether that second property needs its own,
separate correction (and what it would look like -- e.g. an additional
per-session normalization layered on top of the per-security one) is
now flagged as a FURTHER open design question, not resolved by this
section.

### 3.2 Corrected weighted-quantile algorithm (revision 2's was wrong)

**Revision 2's description ("find where cumulative weight crosses `p`,
interpolate between bracketing points") does not reproduce the
`method="inclusive"` convention already used elsewhere in this
codebase** (confirmed: for `[0,10,20,30]`, revision 2's description
produces `Q1=0, median=10, Q3=20`; Python's own
`statistics.quantiles([0,10,20,30], n=4, method="inclusive")` returns
`[7.5, 15.0, 22.5]` -- verified by direct execution this round).

**Corrected algorithm, verified by direct execution against the
equal-weight case (reproducing `[7.5, 15.0, 22.5]` exactly):**

```
sort (value, weight) pairs ascending by value
W = sum of all weights
target_rank = 1 + p * (W - 1)          # 1-indexed virtual rank
# each point i occupies virtual ranks (C_i, C_i + w_i], where
# C_i = sum of weights of all points strictly before it
locate(rank) = the point i whose (C_i, C_i + w_i] contains `rank`
v_floor = locate(floor(target_rank))
v_ceil  = locate(ceil(target_rank))
if v_floor == v_ceil's point: return that point's value
else: interpolate: frac = target_rank - floor(target_rank)
      return v_floor + frac * (v_ceil - v_floor)
```

This treats each point's weight as "that value repeated `w_i` times"
in a virtual expanded sample, then applies the SAME `(rank-1)/(N-1)`
positioning `method="inclusive"` already uses -- confirmed reducing to
`statistics.quantiles(..., method="inclusive")` exactly when all
weights are equal (not merely asserted -- executed and checked this
round).

### 3.3 The worked example, recomputed correctly -- the ORIGINAL
directional claim was also wrong, not just imprecise

Re-running section 3.1's own early/late bin example
(`[(0.8,7),(1.0,7),(1.2,7),(1.5,9),(2.0,21),(2.5,9)]` for reweight,
weights as exact integers out of 60; `[(1.0,21),(1.5,9),(2.0,21),
(2.5,9)]` for collapse) through the CORRECTED algorithm (3.2),
executed directly:

- **Reweight (every row):** `Q1 = 1.2`, `Q3 = 2.0`, **`IQR = 0.8`**,
  mean `= 1.65`.
- **Collapse (per-security representative = mean):** `Q1 = 1.0`,
  `Q3 = 2.0`, **`IQR = 1.0`**, mean `= 1.65` (confirming the
  already-established mean-equivalence, unaffected by this
  correction).

**Revision 2 claimed collapse has the visibly NARROWER IQR. The
corrected, executed computation shows the OPPOSITE: reweight's IQR
(`0.8`) is narrower than collapse's (`1.0`) in this example.** Both the
earlier NUMBERS (computed with an undefined/wrong algorithm) and the
earlier DIRECTION of the claim are withdrawn. The qualitative point
that (i) and (ii) generally diverge on IQR even when their means agree
still holds -- this example now demonstrates it correctly, in the
opposite direction from what was claimed.

### 3.4 F3's common-support option (b) -- the missing pieces, specified

- **Weight renormalization:** already implicit in the existing
  `weighted_sum / total_weight` pattern (`stratified_baseline_point_
  estimate`'s own structure) -- `total_weight` is already the sum of
  only the INCLUDED bins' weights, so restricting to a common-support
  subset and dividing by that subset's own total weight is the same
  operation already in use, not a new mechanism. Stated explicitly
  here since revision 2 left it implicit.
- **The signature's own statistics must be restricted to the SAME
  bin subset, not left at the full population.** This was missed in
  revision 2: `mean_difference = signature_mean_relative -
  baseline_mean`; if `baseline_mean` is now computed only over
  common-support bins while `signature_mean_relative` stays computed
  over the FULL population, `mean_difference` is again comparing two
  different populations -- the ORIGINAL F3 bug, reintroduced one level
  down. Both sides of the subtraction must be restricted to the
  identical bin subset.
- **Zero-eligible-bin boundary case:** if no bin has common support,
  `total_weight = 0` and `mean_difference`/`raw_p` become `None` --
  this is exactly option (a)'s behavior, confirming (a) and (b)
  coincide exactly in the degenerate all-excluded case.

### 3.5 The CI/bootstrap redesign -- not previously specified at all

**`time_block_bootstrap_replicates()` (`statistics/bootstrap.py`)
tracks NO security identity today** -- confirmed by reading its own
signature: `dated_values: list[tuple[str, float]]` is (date, value)
only. Extending this to use 3.1's per-security weighting requires
threading `security_id` through: `dated_values` becomes `list[tuple[
str, str, float]]` (security_id, date, value), carried from wherever
the baseline pool is first assembled through to this function. **Within
EACH bootstrap replicate** (which draws time-blocks with replacement,
so a replicate's own security/row composition can differ from the
original sample), recompute `k_rep` (distinct securities drawn) and
each security's own `n_i_rep` (its row count IN THAT REPLICATE), apply
3.1's weight formula using THOSE replicate-specific values, and pass a
WEIGHTED statistic function (the weighted mean, or 3.2's algorithm for
a percentile-bootstrap CI) instead of today's plain unweighted
`_mean`. **This is a real structural change to the bootstrap's own
call signature and every call site, not a parameter tweak** -- named
here as the correct design, with its implementation cost stated
honestly rather than hidden.

### 3.6 The permutation-test extension -- the null hypothesis stated,
block permutation named as an alternative, "no block permutation
needed" withdrawn as premature

**Revision 2's error:** concluding "no need for block/cluster
permutation" and treating "reduces to today's exact code when weights
are equal" as validity evidence. The equal-weight reduction is an
ALGORITHMIC sanity check (the new code doesn't break the old case) --
it says nothing about whether the UNEQUAL-weight case is statistically
valid.

**The null hypothesis, stated explicitly (not stated at all in
revision 2):** `H0: conditional on the observed security-
representation structure in this bin (which securities appear, and how
many rows each contributes), the numeric VALUES recorded for signature
episodes and for baseline rows are drawn from the same distribution.`
Revision 2's "shuffle values across fixed weighted slots" mechanism
tests exactly this H0 -- it treats the representational structure
(which row belongs to which security, and therefore each row's own
weight) as a FIXED, given nuisance structure, and randomizes only the
VALUES. This is A defensible choice, not THE only one, and it was
presented as settled without saying so.

**Named alternative, not previously considered: block/cluster
permutation**, where each security's ENTIRE row-set (with its own
internal values intact) is reassigned as one unit between the
fake-signature and fake-baseline groups, rather than permuting
individual row values independently of security membership. This tests
a DIFFERENT null hypothesis -- that whole SECURITIES (not individual
observations) are exchangeable between groups -- which is more
conservative about within-security correlation but does not fit neatly
against a fixed `n_sig` raw-row target (securities carry different row
counts, so splitting by a raw count target is awkward, as noted in
earlier analysis this round). **Choosing between these two null models
is a further, unresolved statistical design decision -- not settled by
this document, and not defaulted to either option.**

**A small, calculable example, in place of "equal weights reduce to
current code" as the only check:** bin with `n_sig=2` signature values
`[5, 7]` and 2 baseline rows from DIFFERENT securities with equal
weight `[3, 4]` under section 3.1's formula (trivial case, `k=2`,
`n_i=1` each, weights equal) -- `observed = mean([5,7]) - weighted_mean([3,4], equal) = 6 - 3.5 = 2.5`.
With only `C(4,2)=6` possible ways to split 4 pooled values `{5,7,3,4}`
into 2+2 groups, the full permutation distribution is enumerable by
hand, giving an EXACT (not simulated) p-value to check any
implementation against -- offered as the kind of concrete, checkable
test case section 7's own regression list should include, in place of
only an "equal weights -> identical to today" check.

---

## 4. #004 Top Finding 14 (GPT-G1) -- the fingerprint omitted exit
content entirely

**Error in revision 2:** the proposed `approved_proposal_fingerprint`
hashed only direction/entry/execution-policy/horizon fields, then
"verified" exits by replaying `materialize_variants()` against
whatever `exit_hypotheses` the CALLER currently supplies at gate time
-- which is not tied back to approval at all. A caller could submit a
DIFFERENT `exit_hypotheses` list at the gate than what was actually
reviewed and approved, and this mechanism would not catch it.

**Corrected:** the approved-content fingerprint must ALSO include the
proposal's own `exit_hypotheses` (their canonical content, via the
SAME content-hashing discipline `_exit_fp()`/`variant_fingerprint()`
already use elsewhere in this codebase, not a hand-picked field
subset). At the gate, recompute this fingerprint from the `exit_
hypotheses` actually being used to materialize variants, compare
against the frozen approved value, and only THEN replay `materialize_
variants()` against that now-verified-approved content. Verifying the
materializer's own OUTPUT without first verifying its INPUT was tied to
approval is not a substitute for binding the exits themselves.

## 5. #004 Top Finding 15 (GPT-G2) -- the uniqueness key was too coarse

**Error in revision 2:** `(exit_family, invalidation_conditions)` as
the dedup key can collapse genuinely different variants that differ
only in `max_holding_bars`, `stop_loss`, or `partial_profit` --
administrative-looking fields that are actually part of the exit's own
trading-meaning content. **Corrected:** use the EXISTING
`variant_fingerprint()`/`_exit_fp()` content hash (already defined,
already excludes only genuinely administrative fields like
`variant_tag`) as the uniqueness key, not a hand-picked tuple of
fields. Two variants are "the same" exactly when their existing
content-fingerprint matches -- reusing the definition this codebase
already trusts for content-addressing, rather than inventing a second,
narrower one for this specific check.

---

## 6. Config immutability and the AST guard -- two still-incomplete
mechanisms, corrected

### 6.1 `deepcopy` inside a frozen dataclass does not achieve immutability

**Error in revision 2's `RegisteredConfigVersion` design:** presenting
"a frozen dataclass wrapping a `copy.deepcopy`'d dict" as equivalent to
"recursive `MappingProxyType`." **It is not** -- `deepcopy` produces a
plain, still-mutable `dict`; wrapping it in a frozen dataclass only
prevents reassigning the dataclass's OWN attribute (`obj.data = ...`),
never mutating `obj.data["key"] = ...` on the dict it still holds.
**Withdrawn as an alternative.** The only mechanism that actually
achieves immutability here is recursive `MappingProxyType` (or an
equivalent genuinely-immutable mapping), applied to every nested level
of `data`, not a dataclass wrapper around a plain copy. **Still
unspecified, now flagged explicitly rather than glossed over:** exactly
how `RegisteredConfigVersion`'s own identity ties into the
`hypothesis_config_version` field already stored in `Hypothesis
ComplexitySnapshot` and into whatever versioning-epoch marker S2/Finding
19 jointly decide (section 7 of this document) -- this is a wiring
question the next design pass must answer, not resolved here.

### 6.2 The AST import-resolution algorithm -- the matcher, not just the
collector, was wrong

**Confirmed by reading the actual test** (`tests/spec004/test_49_
evaluation_cannot_import_hypothesis.py`): the existing matcher checks
`m == "hypothesis" or m.startswith("hypothesis.")` against each
collected string. Revision 2's fix (collect `alias.name` for
`ImportFrom` too) does NOT fix `from src.hypothesis import registry`:
`node.module = "src.hypothesis"` is already collected today (via the
existing code), but `"src.hypothesis".startswith("hypothesis.")` is
`False` -- the PREFIXED form was, and remains, invisible under
revision 2's fix, because the fix only addressed the COLLECTOR, not
the MATCHER.

**Corrected:** the matcher itself must check COMPONENT MEMBERSHIP, not
prefix/equality against the whole string: `"hypothesis" in
m.split(".")`. Verified by hand against every case: `"hypothesis"` ->
`True`; `"hypothesis.registry.hypotheses"` -> `True`;
`"src.hypothesis"` -> `True` (the previously-missed prefixed form,
now caught); `"src"` alone -> `False` (still needs the collector fix
below to catch the parent-import-with-alias case); `"discovery"` ->
`False` (negative case unaffected). Combined with the collector fix
(adding `alias.name` for `ImportFrom`), `from src import hypothesis as
h` now adds bare `"hypothesis"` to the set, which the corrected matcher
catches directly.

**Relative imports (`node.level`), checked rather than assumed:**
confirmed by direct search (`grep -rn "^from \.\|^from \.\."`) that
`src/` contains **zero** relative imports today -- this is a latent
gap for future code, not a currently-missed violation. The collector
must still process `ast.ImportFrom` nodes even when `node.module is
None` (today's code skips the whole branch via `and node.module`,
which would also skip collecting `alias.name` for `from . import
hypothesis` if that form is ever introduced) -- full `node.level`
resolution to an absolute module path is not designed here, named as a
residual limitation given zero current usage.

**Revision 2's "covering every import form" claim is withdrawn** until
the matcher fix above is actually implemented and the full 8-row test
matrix (unchanged from revision 2, still valid) is run against it.

---

## 7. Corrected compatibility-matrix entries

**F1 (corrected):** revision 2's matrix did not include F1's own row
at all for #004 impact, implicitly treating it as "no value #004
reads is touched." **Wrong:** F1's classification mechanism changes
WHICH episodes get `VALID` vs. `CROSSES_LOCKED_OOS` vs. a data-gap
status for a given run, which changes the SET and COUNT of valid
outcomes feeding `support.valid_episode_n`, `opportunity_density`, and
ultimately `EvidencePacket.primary_valid_episode_n`/`primary_
episodes_per_20_sessions` -- fields #004 does read. F1 is added to the
matrix with this consequence named.

**F4+F5 (corrected):** revision 2 implied every `standardized_effect`
value changes once F4+F5 ships. **Narrowed:** values change except in
the degenerate case where old and new weighting already coincide (e.g.
a bin containing exactly one security, where per-security and
per-row weighting are identical by construction) -- stated as a
qualified claim, not an unconditional one.

---

## 8. Revised sign-off checklist -- "Complete" downgraded wherever this
round found a gap

| # | Item | Status after this round | What's still needed |
|---|---|---|---|
| 1 | #003 F2a + F2b | Complete | -- |
| 2 | #003 F6 | Complete | -- |
| 3 | #004 Finding 17 (GPT-G4) | Complete | -- |
| 4 | #004 Finding 20 (P004C) | Complete | -- |
| 5 | #003 G2 (TEST 34) | Complete | -- |
| 6 | #004 Finding 2 (research_mode) | Complete | -- |
| 7 | #003 G1 (AST guard) | **Downgraded -- matcher fix, relative-import handling, full matrix unimplemented** | implement + run the 8-row matrix against the corrected matcher |
| 8 | #004 Finding 15 (GPT-G2) | **Downgraded -- key corrected, not yet verified end to end** | confirm the content-hash key against the full variant test matrix |
| 9 | #004 Finding 16 (GPT-G3) | Complete (shared-predicate mechanism; exception scope already stated explicitly) | -- |
| 10 | #004 Finding 10 (exit-family count) | Direction complete; intent question open | Radu: fix, or confirm working-as-designed |
| 11 | #003 F3 + F4 + F5 | **Downgraded -- per-security formula correct but partial (3.1); quantile algorithm now correct and verified (3.2-3.3); CI/bootstrap redesign newly specified but not implemented (3.5); permutation validity an open statistical question (3.6)** | Radu/GPT: decide whether within-bin session-level variation needs its own correction; decide the permutation null-hypothesis model (value-exchangeable vs. block) |
| 12 | #003 F1 (complete behavior) | **Downgraded -- same-exit coherence now fixed (section 1); calendar sourcing and dependency-direction unresolved (section 2); sub-daily timeframes out of scope; TEST 27 claim retracted** | Radu: approve the same-target-session semantics change; resolve calendar sourcing and the #003->#005 import-direction question |
| 13 | #003 S1 | Unchanged | Radu: choose responsibility |
| 14 | #003 S2 | Unchanged | Radu: choose epoch marker |
| 15 | #004 Finding 19 (GPT-G6) + Finding 11 | **Downgraded -- `RegisteredConfigVersion` mechanism named but its immutability approach was wrong (section 6.1); fingerprint-schema wiring unspecified** | specify the actual immutable-mapping mechanism and its wiring into `hypothesis_config_version` |
| 16 | #004 Finding 18 (GPT-G5) | Complete | -- |
| 17 | #004 Finding 14 (GPT-G1) | **Downgraded -- exit content now included in the fingerprint (section 4); not yet re-verified end to end** | confirm the corrected mapping against a concrete attempted-substitution regression |
| 18 | #004 Finding 1 (evaluation_mode marking) | Complete; admission-policy question stays separate | Radu: decide the policy question, jointly with #003's own OOS-discipline framing |

**Scope statement, corrected:** "no remediation design exists anywhere
for Spec #001's/#002's own DEMONSTRATED DEFECTs" is narrowed to: no
remediation design exists in the documents checked this round
(`spec003_remediation_proposal...md`, `spec004_remediation_proposal...
md`, this document, and `contract_index.md`) -- not an unbounded claim
about the entire project's history.

**No code or test was changed to produce this revision; no tests were
rerun. Baseline `3cdc532`, historical acceptances, and the Spec
#005/Batch 3 pause are unchanged.**
