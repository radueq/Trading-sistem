# Joint Remediation Design -- Spec #003 + Spec #004 (2026-10-04, revision 2)

**Status: DESIGN ONLY. Implementation NOT AUTHORIZED.** Revision 2,
replacing the independence claim and several "no open question" rows
GPT's own review (relayed by Radu) found insufficiently concrete in
revision 1 (commit `822968b`). This revision is grounded directly in
the actual source read this round (`evaluation/engine.py`,
`evaluation/outcomes/forward_returns.py`, `evaluation/baseline/
universe.py`, `evaluation/statistics/comparison.py`, `hypothesis/
registry/hypotheses.py`, `backtest/data/calendar.py`), not re-derived
from memory of the per-spec proposals alone.

**Scope, stated explicitly (Radu's own point):** this document covers
Spec #003's F1/F2a/F2b/F3/F4+F5/F6/S1/S2/G1/G2 and Spec #004's Top
Findings 1, 2, 10, 11 (Claude-solo round) and 14-20 (GPT round). It
does **not** cover: Spec #001's two DEMONSTRATED DEFECTs
(`PITCorporateAction` embedding the raw `source_status` field;
`ingestion.ensure_security()` discarding `source_security_id`) or
Spec #002's two DEMONSTRATED DEFECTs (`_price_series_to_df()` mixing
raw high/low with adjusted close; `features.yaml`'s
`driving_return_window` never read) -- **neither of these four has any
remediation design proposed anywhere in this project yet.** They are
named here so they are not silently dropped from the overall program;
a remediation design for them has not been started and is not part of
this document.

---

## 1. Cross-module compatibility matrix (replaces revision 1's
independence claim)

**Revision 1's error, stated plainly:** "`src/hypothesis/` never
imports `evaluation.engine`" proves the two packages' ENGINES are
decoupled. It says nothing about whether the VALUES #004 reads out of
#003's already-frozen dataclasses stay meaningful after #003's fixes
change how those values are computed. Three #003 fixes demonstrably
change values #004 actually consumes, and one is a direct input to
#004's own content-addressing. None of this blocks sequencing (#004
never recomputes or re-derives these values; it only reads whatever
#003 hands it), but "no blocking dependency" is a narrower claim than
revision 1 made, and this matrix states exactly what carries over.

| #003 remediation | Field(s)/semantics changed | #004 consumer | Compatibility check needed |
|---|---|---|---|
| F3 (population mismatch) | `mean_difference`, `median_difference`, `raw_p`, `mean_difference_ci` may become `None` (option a) or recomputed over a narrower common-support population (option b) | `_standardized_effect()` (`engine.py:120-123`) computes `standardized_effect = median_difference / (baseline_iqr/1.349)` -- **directly consumes `median_difference`**; `EvidencePacket.primary_standardized_effect`/`primary_adjusted_p` (`evidence/packet.py`) read `baseline_comparison.standardized_effect`/`.adjusted_p` | If F3 makes `median_difference` `None` for records that previously had a value, `standardized_effect` (already `None`-safe per its own guard) becomes `None` too, and `EvidencePacket.primary_standardized_effect` follows. `evidence/queue.py`'s `compute_review_priority()` treats a `None` effect as `effect_key=0.0` (neutral), not as "missing" -- a record that goes from a real effect to `None` under F3 silently gets NEUTRAL priority ranking, not demoted as "data quality issue." **Needed:** decide whether the Research Queue's own priority function should treat a newly-`None` `standardized_effect`/`adjusted_p` as "deprioritize" rather than "neutral" once F3 ships -- a #004-side follow-up, not a #003 change. |
| F4 + F5 (baseline weighting) | `baseline_mean`, `baseline_median`, `baseline_iqr` all change VALUE (not shape) once computed from one consistent weighted distribution instead of today's three inconsistent paths | Same `_standardized_effect()`/`primary_standardized_effect`/`primary_baseline_median` chain as F3 -- `baseline_iqr` is `standardized_effect`'s own denominator | Every `primary_standardized_effect` #004 has ever computed from real #003 output will change numerically once F4/F5 ships (today's `baseline_iqr` is unweighted-pooled across ALL bins, F4's fix makes it match the already-weighted mean/median). **Needed:** no code change in #004 (it only reads the field), but any #004-side regression fixture built from REAL #003 output (none currently exist -- #004's own tests use hand-built `EvidenceProfile` fixtures, confirmed by reading `tests/spec004/conftest.py`) would need updated expected numbers if one is ever added. |
| S2 (run-id fingerprint) | `build_run_id()`'s fingerprint gains `security_ids`/`benchmark_security_id`/`data_as_of`/`horizons` -- `evaluation_run_id`'s own VALUE changes for inputs that previously collided | `hypothesis/registry/hypotheses.py:60-65`'s `_evidence_fp()` bakes `ep.evaluation_run_id` directly into `hypothesis_fingerprint()`'s own input string -- **`evaluation_run_id` is a direct input to #004's own content-addressed `hypothesis_id`/`definition_hash`** | #004 never recomputes `evaluation_run_id`, only copies it through as an opaque string (`check_provenance_matches_run()` does plain equality, never recomputation) -- so S2 does not break any EXISTING #004 check. But it DOES mean: for the SAME signature/evidence/strategy inputs, a hypothesis built against a POST-S2 run_id will get a DIFFERENT `hypothesis_id` than one built against a PRE-S2 run_id for what might otherwise look like "the same" run. **Needed:** S2's own versioning-epoch decision (a `run_id_scheme_version` marker, or accepting pre/post ids are incomparable) must be taken with this consequence in view -- #004's content-addressing inherits S2's epoch boundary whether #004's own code changes or not. |
| F6 (`family_test_count`) | Adds a field `BaselineComparison` does not currently have | `EvidencePacket` does not read `family_test_count` today (confirmed: `evidence/packet.py`'s `DecayPoint`/`primary_*` fields read only `relative_outcome`/`absolute_outcome`/`baseline_comparison.{baseline_median,standardized_effect,adjusted_p}`, never `family_id`/`family_test_count`) | **This proves absence of CURRENT consumption, not that consuming it is unnecessary or already resolved (Radu's own correction).** Open question, not settled by F6 shipping: should `EvidencePacket`/a human reviewer be told HOW MANY comparisons `adjusted_p` was corrected against, so `adjusted_p=0.03` from a family of 2 reads differently than from a family of 200? This is a genuine #004-side design question F6 surfaces but does not answer -- not included in this round's recommended build (see section 6), flagged as a follow-up item needing its own decision. |
| F2a, F2b, F1 part 1, F1 part 3 | Internal to `run_evaluation()`'s own entry checks and PIT-fetch bounding; no field shape or value #004 reads is touched | none | No compatibility check needed -- confirmed by the same field-level read above: these changes happen entirely before `EvidenceProfile`/`EvaluationRunRegistry` are constructed, and change neither their shape nor, for already-passing runs, their values. |
| G1 (#003 TEST 26), G2 (#003 TEST 34), S1 (#003 numeric guards) | Test-file-only or validation-only; no production field change | none | No compatibility check needed. |

---

## 2. F1 -- designed as one complete behavior, not "part 1 settled,
part 2 open"

GPT's correction (relayed by Radu): bounding the fetch is not a
free-standing fix that can ship alone -- it changes what information
is available to classification, so the two must be designed together,
plus the calendar/horizon semantics and the argument-precedence rule
that were previously left implicit.

### 2.1 What the code does today (read directly, not inferred)

- `_resolve_session_dates()` (`engine.py:71-85`) fetches the
  BENCHMARK's bars at `data_as_of` (unbounded by `development_end`),
  derives `dates` from them, then filters `dates <= development_end`
  -- the DATE LIST is filtered after the fact, but the underlying bars
  fetch itself, and the per-security fetch in `_fetch_bars_by_security()`
  (`engine.py:86-87`), are not bounded at all.
- `compute_forward_outcome()` (`outcomes/forward_returns.py:43-103`)
  classifies as follows, given `bars` (today, unbounded by
  `development_end`) and an `exit_idx` computed from `entry_idx +
  horizon_bars`: if `exit_idx` is out of range of `bars` ->
  `INSUFFICIENT_FUTURE_DATA` (line 83); else if `exit_bar.date >
  development_end` -> `CROSSES_LOCKED_OOS` (line 88-89); else ->
  `VALID`. **The `CROSSES_LOCKED_OOS` branch can only ever fire today
  because `bars` already contains a bar dated past `development_end`**
  -- the exact leak F1 names: to classify the crossing, the code must
  first have fetched the OOS bar.

### 2.2 Why bounding the fetch alone breaks classification

Once `bars` is correctly bounded to `effective_as_of = min(data_as_of,
development_end)` (point 1, already agreed), `bars` will NEVER contain
a bar dated past `development_end`. Every true OOS-crossing case then
falls into line 83's `exit_idx` out-of-range branch, producing
`INSUFFICIENT_FUTURE_DATA`, never `CROSSES_LOCKED_OOS` -- exactly
revision 1 of the #003 proposal's own "option (b)" problem, which
contradicts TEST 27's own assertion that `CROSSES_LOCKED_OOS` must be
observed at least once in its fixture.

### 2.3 Recommended mechanism (concrete, not "open design work")

**Classify using a session COUNT computed from a price-independent
calendar, never from a fetched bar's own date.**

1. **Calendar source: reuse `backtest.data.calendar.TradingCalendar`,
   read-only, as a date-arithmetic utility -- NOT as #005's SS11
   fail-closed gate.** `TradingCalendar.session_dates` (built via
   `build_trading_calendar()`) is already a separately-sourced,
   price-independent list of trading session dates -- confirmed by
   reading `backtest/data/calendar.py`: it is built from an external
   calendar source, never from benchmark/security bars. **This is a
   genuine reinterpretation of SS11's own text** ("`_resolve_session_
   dates()` remains unchanged... a #005-only concern, never a #003
   patch") **and needs Radu's explicit sign-off, named as such, not
   assumed:** the proposal is to let `evaluation.engine` READ
   `TradingCalendar.session_dates` as a pure date-lookup (no price, no
   PIT access, no dependency on #005's `require_verified_calendar_for_
   formal_run()` fail-closed gate, no claim that this satisfies SS11's
   own CALENDAR_UNVERIFIED/CALENDAR_COVERAGE_INCOMPLETE checks for a
   formal #005 run) -- `_resolve_session_dates()` itself, and its
   benchmark-bar-derived date list, stay exactly as they are for every
   OTHER purpose; only the NEW classification check below uses the
   calendar.
2. **Classification check, replacing the bar-date comparison at
   `forward_returns.py:88-89`:**
   - Given the entry session date `E` (already known, inside
     Development) and `horizon_bars` = N, look up `E`'s index in
     `TradingCalendar.session_dates` and compute `expected_exit_date =
     session_dates[index_of(E) + N]` (a pure calendar lookup, no price
     access).
   - **If `expected_exit_date > development_end`:** classify
     `CROSSES_LOCKED_OOS`. This is now determined ENTIRELY from the
     calendar, with zero price/PIT access past the wall -- the leak F1
     names is closed.
   - **Else (`expected_exit_date <= development_end`):** the exit
     SHOULD exist within Development. Compare `expected_exit_date`
     against `effective_as_of`:
     - If `expected_exit_date > effective_as_of` (i.e., the caller's
       own `data_as_of` has not yet reached that date): classify
       `INSUFFICIENT_FUTURE_DATA` -- not yet knowable from this
       caller's own vantage point, consistent with the status's
       existing meaning.
     - If `expected_exit_date <= effective_as_of` and the bar is STILL
       absent from the bounded fetch: this is a genuine DATA GAP (a
       missing bar for a date within Development that should have
       been fetched), **not** `CROSSES_LOCKED_OOS` and **not** quite
       the same claim as "insufficient future data" (which implies the
       window hasn't been reached yet, when here it has). **Radu's own
       semantic call, not decided here:** reuse `INSUFFICIENT_FUTURE_
       DATA` for this case too (simplest, but conflates "not yet
       reached" with "genuinely missing"), or introduce a new
       `OutcomeStatus` value (e.g. `DATA_GAP_WITHIN_DEVELOPMENT`) so a
       reviewer can tell the two apart. This directly answers Radu's
       own earlier correction ("a missing bar alone doesn't prove
       OOS -- could be `data_as_of < development_end`, delisting, or a
       data gap") with a concrete three-way split instead of leaving
       it as an acknowledged-but-unresolved ambiguity.
3. **TEST 27 compatibility, confirmed:** `CROSSES_LOCKED_OOS` still
   fires under this mechanism whenever the calendar says the true exit
   falls beyond `development_end`, regardless of what the bounded
   fetch contains -- TEST 27's own assertion stays satisfiable, no
   contradiction with the fetch-bounding fix.

### 2.4 Horizon semantics and calendar source -- named explicitly

SS3-4's own text says only "timeframe + horizon_bars"; counting the
horizon via each security's own PIT bar index
(`forward_returns.py`'s `_exact_entry_index`/`exit_idx = entry_idx +
horizon_bars`) is the CURRENT implementation's choice, not a spec
requirement (per the #003 proposal's own attribution correction). The
calendar-based classification above introduces a SECOND horizon
concept -- "N sessions forward on the TRADING CALENDAR" -- that must
be reconciled with the FIRST -- "N bars forward in THIS security's own
PIT series," since a security with a data gap of its own could have
its Nth-bar index land on a calendar date different from the
calendar's own Nth-session-forward date. **Recommended reconciliation:**
the calendar-based count is used ONLY for the OOS/data-gap
classification question (section 2.3), never to relocate or
reinterpret where the security's own `exit_idx` actually points for
return computation -- the two horizon concepts answer two different
questions (classification vs. actual exit point) and should not be
merged into one. This needs Radu's sign-off as a stated design
decision, not left implicit.

### 2.5 Argument precedence, including the omitted-vs-`None` distinction

The existing code's `data_as_of = data_as_of or development_end`
pattern, and the proposal's own point 3 ("`research_period` as the
default... with explicit function arguments taking precedence when
given"), cannot be implemented as literally stated with a plain
`Optional[str] = None` default parameter: **Python gives the function
no way to distinguish "caller omitted this argument" from "caller
explicitly passed `None`" once both collapse to the same `None`
value inside the function body.** Two concrete fixes, Radu's choice:
- **(a) Redefine the rule, not the code:** state explicitly that
  passing `None` (whether by omission or explicitly) always means
  "use the config default," and there is no way to force "no override,
  ignore the config" short of passing an actual value. Zero code
  change beyond the already-planned config-reading logic.
- **(b) Use a sentinel default** (a module-level `_UNSET = object()`
  marker as the parameter's actual default, with `None` treated as a
  meaningful, intentional override value, e.g. "explicitly disable the
  config default") if some future caller genuinely needs to distinguish
  "pass `None` on purpose" from "didn't pass anything." Given no
  current caller needs that distinction, **(a) is the recommended,
  simpler option** -- (b) is named only so the limitation is not
  silently reintroduced later.

### 2.6 Regression coverage for the complete F1 behavior

- Development-end fetch bound: no PIT call for a run returns a bar
  dated after `development_end` (already specified).
- Late-knowledge corporate action planted within Development: forward
  return unaffected (already specified).
- **New:** a fixture where the calendar's own `expected_exit_date`
  falls beyond `development_end` but NO bar was ever fetched past the
  wall -- asserts `CROSSES_LOCKED_OOS`, confirming classification works
  with zero OOS price access.
- **New:** a fixture where `expected_exit_date <= effective_as_of` but
  the bar is genuinely absent (a data-gap fixture, e.g. a delisted
  security) -- asserts the chosen data-gap status (section 2.3's third
  branch), distinct from a fixture where `expected_exit_date >
  effective_as_of` (not yet reached) asserting `INSUFFICIENT_FUTURE_
  DATA`.
- `research_period` precedence test (already specified), written
  against whichever of 2.5's (a)/(b) is chosen.
- TEST 27 itself re-run unmodified against the new mechanism, confirmed
  still passing (sections 2.3's point 3).

---

## 3. F3 + F4 + F5 -- one consistent mathematical recommendation,
worked numerically

**Grounded in the actual code** (`baseline/universe.py:87-137`,
`statistics/comparison.py:65-113`): `stratified_baseline_point_
estimate()` computes `stat(bin_values)` (a plain, row-based mean or
median) WITHIN each bin, then averages those per-bin statistics
ACROSS bins by `weights_by_bin` -- this is a weighted average of
per-bin statistics, not yet "one weighted distribution." Separately,
`baseline_iqr = robust_iqr([v for _, v in baseline_dated])`
(`engine.py:216`) pools EVERY bin's raw values with NO weighting at
all, between or within bins -- confirmed exactly as F4 describes.

### 3.1 Recommended within-bin weight formula (resolves F5)

For bin `b` with weight `W_b` (`weights_by_bin[b]`, already fixed and
approved) and securities `S = {s_1, ..., s_k}` present in `b`, where
security `s_i` contributes `n_i` baseline rows in `b`: **assign each
row of security `s_i` in bin `b` the weight `w = W_b / (k * n_i)`.**
This makes every security's TOTAL weight within the bin exactly `W_b
/ k` (equal across securities, closing F5's dominance problem), while
every individual row still carries its own value into every statistic
computed from the resulting distribution (closing F4's mean/IQR
inconsistency, since mean/median/IQR are now all computed from the
SAME set of (value, weight) pairs). Summing every row's weight across
the whole bin recovers exactly `W_b` (unchanged from today's
between-bin weighting), so no renormalization against other bins is
needed.

**This formula IS the recommended answer to F5's "(i) vs (ii)"
question: it is the reweight-every-row option (ii), with the exact
weight stated.** Collapse-to-representative (i) is not recommended:
it discards each security's own within-security spread, which this
section's worked example (3.3) shows materially changes `baseline_
iqr`/`standardized_effect` even in the one case where (i) and (ii)
give an identical weighted mean.

**Scope correction, not previously stated:** this reweighting applies
to the BASELINE side only. The SIGNATURE's own per-episode aggregation
(`signature_mean_relative` etc., computed directly from the signature's
own observed episodes, never through `stratified_baseline_point_
estimate()`) stays row-based and unweighted -- a security firing the
signature more often is real signal frequency being measured, not a
universe-composition sampling artifact the way baseline over-
representation is. SS74C's own concern is specifically about the
baseline comparison population, not the signature's own observed rate.

### 3.2 Weighted quantile algorithm (needed for `baseline_median` and
`baseline_iqr` under 3.1's weights)

Standard weighted-percentile via linear interpolation on the weighted
empirical CDF: sort the bin's `(value, weight)` pairs by value;
compute the cumulative weight fraction at each point; the weighted
`p`-th percentile is the value where the cumulative fraction crosses
`p`, linearly interpolated between the two bracketing points (the same
family of method as `statistics.quantiles(..., method="inclusive")`,
generalized to unequal weights). `baseline_median` = weighted 50th
percentile; `baseline_iqr` = weighted 75th percentile minus weighted
25th percentile, computed over the SAME weighted distribution as
`baseline_mean` (a weighted arithmetic mean, which needs no special
algorithm beyond `sum(value*weight) / sum(weight)`).

### 3.3 Worked numerical example

Bin "early" (`W = 0.7`): security A has 3 rows `[1.0, 1.2, 0.8]`;
security B has 1 row `[2.0]`. Bin "late" (`W = 0.3`): security A has 1
row `[1.5]`; security B has 1 row `[2.5]`.

**Today's (buggy) values:** `baseline_mean` = weighted average of
per-bin means = `0.7 * mean(1.0,1.2,0.8,2.0) + 0.3 * mean(1.5,2.5)` =
`0.7*1.25 + 0.3*2.0` = `1.475`. `baseline_iqr` = unweighted IQR of all
6 pooled raw values `[0.8,1.0,1.2,1.5,2.0,2.5]` -- dominated 4:2 by the
"early" bin's own raw row count, not by its 0.7/0.3 weight.

**Recommended (3.1) values:** per-row weights: A's 3 "early" rows each
get `0.7/(2*3) = 0.1167`; B's 1 "early" row gets `0.7/(2*1) = 0.35`;
A's "late" row gets `0.3/(2*1) = 0.15`; B's "late" row gets `0.3/(2*1)
= 0.15`. Weighted distribution: `(1.0, 0.1167), (1.2, 0.1167), (0.8,
0.1167), (2.0, 0.35), (1.5, 0.15), (2.5, 0.15)` (weights sum to `1.0`).
**`baseline_mean = 1.0*0.1167 + 1.2*0.1167 + 0.8*0.1167 + 2.0*0.35 +
1.5*0.15 + 2.5*0.15 = 1.65`** -- different from today's `1.475`, and
different from the buggy unweighted IQR's own implicit 4:2 split.

**Collapse-to-representative (i), for comparison, using each
security's own mean as the representative (the one case where (i) and
(ii) agree on the mean):** A's early representative `= 1.0` (weight
`0.35`), B's early representative `= 2.0` (weight `0.35`), A's late
`= 1.5` (weight `0.15`), B's late `= 2.5` (weight `0.15`). Weighted
mean `= 1.0*0.35+2.0*0.35+1.5*0.15+2.5*0.15 = 1.65` -- **identical to
(ii)**, confirming the already-established math correction (same mean
only because the representative IS the mean). But (i)'s distribution
only has 4 distinct points, discarding A's own `[1.0,1.2,0.8]` spread
entirely -- its weighted IQR is visibly narrower than (ii)'s, which
still carries that spread through 3 separate weighted points. This is
the concrete demonstration (not just the abstract claim) that
collapsing removes within-security variance reweighting preserves.

### 3.4 F3's own choice, and how it composes with 3.1-3.3

**Recommended: option (b), common-support comparison**, for
consistency with 3.1's own philosophy ("define the population once,
compute every statistic from that one definition" rather than
"withhold entirely when something doesn't line up"). Concretely: the
bins eligible for `mean_difference`/`raw_p`/CI are exactly the bins
`stratified_permutation_p_value()` already includes (weight > 0, AND
both signature and baseline pools non-empty, per `comparison.py:82-89`
-- this inclusion rule does not change); `mean_difference`/
`median_difference` must be computed over the SAME bin subset, using
3.1's weighted distribution restricted to those bins (not the full
bin set `stratified_baseline_point_estimate()` currently uses
unconditionally). The excluded bins (and how many signature episodes
they represent) are reported explicitly, per the #003 proposal's own
requirement -- this document does not relax that.

### 3.5 Extending the permutation test to the same baseline weighting

**Concrete mechanism, not previously specified:** `stratified_
permutation_p_value()` (`comparison.py:65-113`) currently shuffles
each bin's pooled `sig_vals + base_vals` as a flat list and splits by
raw count (`n_sig`/`n_base`) -- equivalent to every slot implicitly
carrying weight `1/n_sig` or `1/n_base`. **Generalize by keeping each
baseline row's 3.1-computed weight attached to its SLOT POSITION, and
permuting only the VALUES across slots, never the weights:**
1. Per bin, build two fixed slot-weight lists: `n_sig` signature slots,
   each weight `1/n_sig` (unweighted, matching 3.1's scope correction);
   `n_base` baseline slots, each carrying its own 3.1-computed
   per-security-normalized weight (independent of between-bin `W_b`,
   i.e. normalized to sum to 1 within the bin, matching how `pools`
   are already handled per-bin before the `weights_by_bin[label]`
   multiply at combination time).
2. `observed` per bin `= mean(sig_vals) - weighted_mean(base_vals,
   base_slot_weights)` (3.2's weighted-mean formula on the baseline
   side only).
3. Each permutation iteration: shuffle the VALUES of `pooled =
   sig_vals + base_vals` (exactly as today), then assign the first
   `n_sig` shuffled values to the fixed signature slots (plain mean)
   and the remaining `n_base` shuffled values to the fixed baseline
   slots IN THEIR ORIGINAL ORDER, so each baseline slot's weight stays
   attached to its position, not to whichever value a given shuffle
   happened to place there -- `perm_diff = mean(shuffled[:n_sig]) -
   weighted_mean(shuffled[n_sig:], base_slot_weights)`.
4. Combine across bins by `weights_by_bin` exactly as today (lines
   93-97, 108-109) -- unchanged.

**This is a strict generalization, not a new mechanism:** when every
baseline row's weight is equal (`1/n_base` each, today's implicit
case), step 3's weighted mean reduces to the current plain
`sum(shuffled[n_sig:])/n_base`, reproducing today's exact code path.
It extends cleanly to 3.1's unequal per-security weights without
requiring block/cluster permutation.

### 3.6 Regression coverage for F3+F4+F5 (supersedes the prior,
less specific list)

- The zero-weight-bin fixture (F4's original case) and the LONG/SHORT
  uneven-row-count fixture (F5's original case), both re-asserted
  against the NEW formula's own numbers (recompute expected values
  using 3.1-3.2, not the pre-fix values).
- The >= 2 active-bins-with-different-weights fixture (already
  specified), confirming `baseline_mean`/`baseline_median`/
  `baseline_iqr` are all consistent with ONE weighted distribution.
- **New, from 3.3:** a fixture reproducing this section's own worked
  example exactly, asserting `baseline_mean == 1.65` (hand-computed),
  and asserting `baseline_iqr` differs measurably between the (i) and
  (ii) formulas even though their means agree.
- **New, from 3.4:** a fixture with one bin fully covered and one bin
  one-sided (F3's reproduction fixture), asserting `mean_difference`/
  `raw_p` are computed over the identical bin subset under option (b),
  with the excluded bin's episode count reported explicitly.
- **New, from 3.5:** a fixture with unequal per-security baseline row
  counts, asserting the permutation test's own `raw_p` changes
  relative to today's unweighted version, and that setting every
  security's row count equal reproduces today's exact `raw_p` (the
  reduction-to-current-behavior check).

---

## 4. #004 Findings 1, 2, 10, 11 (Claude-solo round) -- not previously
given a remediation design; added here so they are not dropped

### Finding 1 -- no `evaluation_mode` marking on the frozen record

**Recommended:** add `evaluation_mode: str` to `EvidenceProvenance`,
populated from `run_registry.mode` inside `build_evidence_packet()`
(which already reads and validates `run_registry.mode` internally,
per `evidence/packet.py`'s own cross-artifact check -- it is simply
never written out to the provenance object it returns). Include it in
`_evidence_fp()`'s own fingerprint input (`hypothesis/registry/
hypotheses.py:60-65`), analogous to how `parameter_source` was added to
`_horizon_fp()` under PATCH #004-A finding #5 -- "the same evidence for
a different reason is a different commitment." **Separate, still
Radu's own call, not resolved by adding the field:** whether the gate
should additionally REJECT `evaluation_mode != "FORMAL_DEVELOPMENT"`
outright (an admission policy), vs. only RECORD which mode was used
(a marking requirement) -- section 1's cross-module note already flags
this as worth deciding jointly with #003's own OOS-discipline language,
not twice.

### Finding 2 -- `research_mode` never enforced

**Recommended:** add a check to `validate_for_preregistration()`
rejecting `hypothesis.research_mode != HypothesisResearchMode.
PREREGISTERED_STRATEGY.value`. SS29's own text ("cannot enter formal
backtest validation directly") reads as an outright block, not a
promotion path with its own ceremony -- if Radu intends a DIFFERENT,
explicit EXPLORATORY-to-PREREGISTERED promotion mechanism to exist
later, that is a new, separate feature to design, not an argument
against blocking the direct path now.

### Finding 10 -- `max_exit_families_per_hypothesis` counts variants, not family types

**Recommended:** change `validator.py:256`'s check from `len(proposal.
exit_hypotheses) > max - 1` to `len({e.exit_family for e in proposal.
exit_hypotheses} | {ExitFamily.TIME_EXIT.value}) > max` -- counting
DISTINCT family types actually present (including the mandatory
TIME_EXIT, matching the error message's own "combined with the
mandatory TIME_EXIT family" wording), not raw proposal entries.
**Radu's own call:** whether today's stricter, variant-counting
behavior was ever actually intended (if so, this is a WORKING AS
DESIGNED verdict, not a defect) -- this document recommends the
family-type reading as more consistent with the field's own name, not
as the only defensible one.

### Finding 11 -- `hypothesis_config_version` never cross-checked

**Already covered by this document's design for Top Finding 19/GPT-G6
in section 5 below** (the three-way concordance / registered-version
mechanism) -- the two were always the same root cause; this entry
exists only so Finding 11 has its own row in the order/checklist
(section 6) rather than being implicitly folded into Finding 19 with no
visible trace.

---

## 5. #004 Top Findings 14-20 -- field mappings, mechanisms, and
contract-changing decisions proposed concretely (not left as "Radu's
call" alone)

### Top Finding 14 (GPT-G1) -- content binding: the field-by-field
transformation

**Recommended concrete mapping,** `ApprovedContent` = the tuple of
fields frozen into the `approved_proposal_fingerprint` (section 1 of
`spec004_remediation_proposal...md`) at approval time:

| Draft field | Rule |
|---|---|
| `direction` | must be IDENTICAL to `proposal.direction` |
| `entry_definition` | must be IDENTICAL to `proposal.entry_definition` (after `normalize_proposal()`) -- entry conditions are never legitimately "derived," only copied |
| `entry_execution_policy` | must be IDENTICAL to `proposal.entry_execution_policy` |
| `horizon_candidate_set.values` | must be IDENTICAL (as a set) to `proposal.horizon_candidates.values` |
| `horizon_candidate_set.parameter_source`/`selection_basis` | must be IDENTICAL to the proposal's own declared values |
| `variant_ids` / the materialized `StrategyVariant`s | NOT required to be identical to anything on the proposal -- `materialize_variants()`'s own eager expansion of `horizon_candidate_set.values` into one TIME_EXIT variant per value, plus the proposal's own `exit_hypotheses` list copied through as SIGNAL_INVALIDATION/STOP_MANAGED_INVALIDATION variants, is the one and only allowed "derivation" step; verified not by equality but by replaying `materialize_variants()` against the APPROVED `horizon_candidate_set` and checking the actual registered variants match that replay exactly |

**Mechanism:** `approved_proposal_fingerprint` hashes exactly the first
five rows above (the "must be identical" fields) from the proposal at
approval time. At the gate, recompute the same hash from the DRAFT's
own corresponding fields and compare. Separately (not foldable into one
hash, since it is a replay-equality check, not a hash-equality check),
assert that replaying `materialize_variants()` against the (now
verified-identical) `horizon_candidate_set` and the proposal's own
`exit_hypotheses` produces exactly the registered variant set.

### Top Finding 15 (GPT-G2) -- the exact permitted variant-set contract

**Recommended, stated as a full contract, not just "every horizon
present":** the registered variant set for a hypothesis must satisfy
ALL of: (i) exactly one TIME_EXIT variant per value in `horizon_
candidate_set.values` (no fewer -- Finding 15's own reproduction; no
MORE either -- a TIME_EXIT variant for a bars value NOT in `horizon_
candidate_set.values` is also rejected, closing the symmetric gap
revision 1 left as an open question); (ii) zero or more SIGNAL_
INVALIDATION/STOP_MANAGED_INVALIDATION variants, each appearing AT
MOST ONCE per distinct `(exit_family, invalidation_conditions)` pair
(duplicate variants differing only in an administrative field like
`variant_tag` are rejected as redundant, not silently accepted as
"additional" variants); (iii) every variant's `exit_family`/
`horizon_reference_point`/`exit_execution_policy` validated per the
existing family-specific rules (already specified in `spec004_
remediation_proposal...md` section 2).

### Top Finding 16 (GPT-G3) -- the atomicity mechanism, proposed

**Recommended: option (a) from the existing proposal (validate-before-
write), with its own precondition set DERIVED FROM, not duplicated
from, the actual write-path checks** -- concretely: extract
`_force_register()`'s and `register_variant()`'s own precondition
logic into two small, named predicate functions
(`_hypothesis_registerable(existing, hyp) -> bool` and
`_variant_registerable(existing, variant) -> bool`) that BOTH the dry
run and the actual write call -- not two independently-maintained
copies of the same logic. This directly resolves this document's own
prior concern (section 3 of `spec004_remediation_proposal...md`) that
the dry run's precondition set could drift from the write path's own
preconditions over time: with one shared predicate, drift is
structurally impossible, since there is only one implementation to
change. Stated exception coverage: this guarantees no raise from
`ImmutableHypothesisError`'s own documented conditions (content
mismatch, PREREGISTERED-content-mismatch, variant content mismatch);
it does not and cannot guarantee anything about a failure outside
those three documented conditions (e.g. an `OSError` from the
underlying storage if `HypothesisRegistry` is ever backed by something
other than a plain in-memory dict) -- named explicitly per this
document's own prior correction on "ANY failure" framing.

### Top Finding 18 (GPT-G5) -- justifying the stability summary against
the review's own ask, not just the packet's existing shape

GPT's own finding: §39 lists "stability bins" as a distinct top-level
minimum-content item, separate from §57's "stability availability."
**Recommended field, justified against that specific gap, not merely
"fits the packet's style":** `primary_stability_summary: tuple[tuple[str,
Optional[float], Optional[float], Optional[float], int], ...]` --
`(bin_label, mean, median, positive_rate, valid_n)` per bin, for the
PRIMARY reference horizon only, mirroring the SAME "one reference
horizon only" policy already applied to every other `primary_*` field
on the packet (never "per decay-curve-point stability," which would
multiply the field's own size by every horizon tested). This is the
minimum granularity that actually answers §39's own ask ("stability
bins" as named content, not merely their presence) while staying
consistent with the packet's one-reference-horizon design; a coarser
single boolean (today's `primary_has_stability_bins`) was already shown
insufficient by GPT's own reproduction (G5), and a finer per-horizon
breakdown is not what §39 asks for and would reopen the token-budget
question (Finding 8) unnecessarily.

### Top Finding 19 (GPT-G6) + Finding 11 -- the registered-version
mechanism, proposed concretely

**Recommended:** introduce one new, explicit object,
`RegisteredConfigVersion`, created ONCE per preregistration session or
Research Queue run (whichever operation needs it), via a single
function `register_config_for_operation(config_dir=None) ->
RegisteredConfigVersion` that (1) calls `load_config()` fresh against
the real persisted `hypothesis.yaml`, (2) computes a canonical-content
hash of the loaded `data` (not the raw file text -- see the
versioning-epoch note below), (3) returns an object carrying both the
hash and an IMMUTABLE deep copy of `data` (e.g. via `copy.deepcopy`
wrapped in a frozen dataclass, or recursively through
`types.MappingProxyType`). Every subsequent check during that
operation (the gate's `hypothesis_config_version` comparison, the
queue's `eligibility_config_version` stamp) uses THIS SAME
`RegisteredConfigVersion` object's own `data`/hash -- never a second,
independent `load_config()` call, and never the caller-supplied
`hypothesis_config` dict directly. The three-way concordance check at
each use site: (i) hash of the content actually being used (the
registered object's own `data`, which is now immutable, so this is
really just a one-time check at registration) vs. (ii) the
`hypothesis_config_version`/`eligibility_config_version` value the
calling code CLAIMS it is using vs. (iii) the registered object's own
hash -- reject if (ii) != (iii). **Versioning-epoch decision, Radu's
own call, same as S2's:** canonical-content hashing of `data` produces
different strings than today's raw-file-text hash for the same logical
config -- needs the same scheme-tag-or-epoch-boundary decision as S2,
and this document recommends deciding both epochs in the same sitting
(section 1).

### Top Finding 17 (GPT-G4), Top Finding 20 (P004C)

Unchanged from `spec004_remediation_proposal...md` -- both already
fully concrete with no open design question (confirmed again this
round by re-reading `registry/hypotheses.py:241-249` and `registry/
persistence.py:47-53`).

---

## 6. #003 G1 (TEST 26 AST guard) -- the complete import-resolution
algorithm

**Recommended algorithm, covering every import form, not only the
aliased `from`-import case revision 1 named:**

```
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            # covers: import evaluation
            #         import evaluation as ev        (alias.asname set)
            #         import src.evaluation.engine    (dotted -- alias.name
            #           is the full dotted path; record BOTH the full
            #           path and its first component, since
            #           "import src.evaluation.engine" makes "src",
            #           "src.evaluation", AND "src.evaluation.engine"
            #           all resolvable names depending on usage)
            record(alias.name)
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            record(node.module)               # from X import Y -> records X
        for alias in node.names:
            # covers: from src import evaluation
            #         from src import evaluation as ev   (THIS document's
            #           original #004/#002/#003 finding)
            #         from src.evaluation import engine
            record(f"{node.module}.{alias.name}" if node.module else alias.name)
```

**Required test matrix (four forms, each with and without aliasing --
the minimum revision 1 should have specified but did not):**

| Form | Example | Must be caught |
|---|---|---|
| Direct import | `import evaluation` | yes |
| Direct import, aliased | `import evaluation as ev` | yes |
| Dotted import | `import src.evaluation.engine` | yes |
| Parent-module `from`-import | `from src import evaluation` | yes |
| Parent-module `from`-import, aliased | `from src import evaluation as ev` | yes (this document's/#002's/#004's original finding) |
| Submodule `from`-import | `from src.evaluation import engine` | yes |
| Submodule `from`-import, aliased | `from src.evaluation import engine as e` | yes |
| Unrelated import (negative case) | `import discovery` | must NOT be flagged as importing `evaluation` |

A regression test for each row above, using the exact same scratch-file
probe technique as this round's own reproduction, replaces the single
aliased-form test revision 1 specified.

---

## 7. Revised build order and sign-off checklist (covers every item
named in sections 2-6, including what revision 1 omitted)

| # | Item | Design completeness this round | Radu's decision needed |
|---|---|---|---|
| 1 | #003 F2a + F2b | Complete | Approve |
| 2 | #003 F6 | Complete | Approve |
| 3 | #004 Finding 17 (GPT-G4) | Complete | Approve |
| 4 | #004 Finding 20 (P004C) | Complete | Approve |
| 5 | #003 G1 (AST guard) | Complete (section 6) | Approve |
| 6 | #003 G2 (TEST 34) | Complete | Approve |
| 7 | #004 Finding 15 (GPT-G2) | Complete (section 5) | Approve |
| 8 | #004 Finding 16 (GPT-G3) | Complete (section 5) | Approve |
| 9 | #004 Finding 2 (research_mode) | Complete (section 4) | Approve |
| 10 | #004 Finding 10 (exit-family count) | Direction complete; "intended behavior" reading is Radu's own call (section 4) | Choose: fix, or confirm as working-as-designed |
| 11 | #003 F3 + F4 + F5 | Complete, one recommended answer with worked numbers (section 3) | Approve, or reject the recommendation and send back |
| 12 | #003 F1 (complete behavior) | Complete mechanism proposed (section 2); SS11 reinterpretation named explicitly | Approve the calendar-reuse mechanism AND the SS11 reinterpretation it requires, or reject and this reopens to "no mechanism exists" |
| 13 | #003 S1 | Unchanged -- genuinely a scope/responsibility question, not a mechanism gap | Choose: defensive code, or documented trust boundary |
| 14 | #003 S2 | Mechanism complete; epoch-marker choice open | Choose the versioning-epoch marker |
| 15 | #004 Finding 19 (GPT-G6) + Finding 11 | Mechanism complete (section 5); epoch-marker choice open, same decision as #14 | Choose the versioning-epoch marker (recommend deciding jointly with #14) |
| 16 | #004 Finding 18 (GPT-G5) | Complete, justified against §39 (section 5) | Approve |
| 17 | #004 Finding 14 (GPT-G1) | Complete field mapping proposed (section 5) | Approve the mapping, or propose a different one |
| 18 | #004 Finding 1 (evaluation_mode marking) | Complete (section 4); admission-POLICY question stays separate | Approve the marking fix; separately decide the admission-policy question (recommend jointly with #003 F1's own OOS-discipline framing, section 1) |

**Follow-up items surfaced this round, not yet in any build order
(flagged so they are not lost, per Radu's own point):** whether
`EvidencePacket`/the Research Queue should start consuming F6's
`family_test_count` (section 1's compatibility matrix); whether the
Research Queue's `compute_review_priority()` should treat a
newly-`None` `standardized_effect`/`adjusted_p` (post-F3) as
"deprioritize" rather than today's "neutral" (section 1); Spec #001's
and #002's own four DEMONSTRATED DEFECTs, for which no remediation
design exists anywhere yet (this document's own scope statement).

**Approving a row above authorizes DESIGN completeness for that row,
not implementation.** Where this round found a genuine, complete,
concrete mechanism (the majority of rows), "approve" means the design
itself is accepted as ready for a future implementation-authorization
decision -- still a separate, later step. Where a row still names an
open choice (10, 12's SS11 point, 13, 14, 15, 18's admission-policy
point), approving the row approves only the mechanism that doesn't
depend on that choice; the choice itself remains outstanding until
Radu picks an answer.

**Baseline `3cdc532`, historical acceptances, and the Spec #005/Batch 3
pause are unchanged by this document. No code or test was changed to
produce it; no tests were rerun.**
