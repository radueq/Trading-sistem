# Spec #003 -- Remediation Proposal (2026-10-04, revised same day)

**Revision note:** this is a corrected revision of the same-day first
draft, after Radu found the F1 fix still read OOS prices, F3's proposal
insufficient, F4/F5 patched independently rather than designed together,
F2b's gate placement unsafe, and F6's own remediation missing entirely.
Each is marked inline with a "Corrected 2026-10-04 (Radu)" note. **Not
yet approved** -- this revision addresses the structure/soundness of the
proposals themselves; it does not constitute Radu's sign-off on any of
them.

**This document proposes fixes. It does not implement them.** No code or
test in `src/` or `tests/` has been changed to produce this proposal --
see `docs/audit_spec003_requirement_code_test.md`'s Top Findings 11-19
for the reconciled findings this responds to. Implementation requires
Radu's explicit authorization; this round's instruction was reconciliation
and a remediation proposal only, not a patch.

Ordered by GPT's own priority (F1 first, critical).

## F1 -- OOS isolation / knowledge-time leakage into Development

**Problem (Top Finding 11):** `run_evaluation()` fetches PIT price history
at `data_as_of` for every security and the benchmark with no truncation to
`development_end`; a corporate action knowable only after
`development_end` can retroactively change an already-Development forward
return. `research_period` in `evaluation.yaml` is also never read.

**Corrected 2026-10-04 (Radu): the "separate fetch at `data_as_of` for
exit-classification" option below in the previous draft of this proposal
is withdrawn -- it still reads OOS prices, which is the exact thing F1
forbids, not a smaller version of it.** Classification must use the
session calendar and the period boundary, never a price read past the
wall, and must not exceed the caller's own `data_as_of` even when that
value is earlier than `development_end`.

**Note on scope:** `src/backtest/data/calendar.py`'s own docstring
records an explicit prior decision (Spec #005 SS11) that
`evaluation.engine._resolve_session_dates()` "remains unchanged" and
that Spec #005's stricter, separately-verified `TradingCalendar`
contract is "a #005-only concern, never a #003 patch." This proposal
does NOT import or depend on that module -- the fix below stays inside
Spec #003's own existing calendar mechanism (`session_dates`, derived
from the benchmark's own bars) and does not reopen SS11's boundary.
Discovery's own per-session PIT access (`compute_discovery_observations`,
called once per session date from `_collect_observations`) is also
untouched -- this proposal is scoped to Evaluation's own outcome/baseline
computation, not Discovery.

**Proposed fix, three parts, all inside Spec #003's own code:**

1. **Bound every PIT fetch used for Development computation to one
   `effective_as_of`, never to the raw `data_as_of` argument.** Define
   `effective_as_of = min(data_as_of, development_end)` when
   `development_end is not None`, else `effective_as_of = data_as_of`
   (string ISO dates compare correctly lexically). Use `effective_as_of`
   in place of `data_as_of` in `_resolve_session_dates()`'s benchmark
   fetch and in `_fetch_bars_by_security()`. Because
   `pit.access.get_price_series_as_of(conn, sid, as_of)` already gates
   BOTH which bars are returned AND which corporate actions are visible
   by the same single `as_of` (confirmed by reading `pit/access.py`:
   `available_at <= as_of` governs action visibility, and the same
   `as_of` bounds the bar range) -- this one change removes BOTH the
   OOS-bar-read and the knowledge-time leak in a single mechanism, with
   no new PIT function needed. This also directly satisfies "nu trebuie
   depășit nici `data_as_of` cerut de apelant dacă acesta precedă
   `development_end`": `min()` already returns the caller's earlier
   value unchanged in that case.
2. **Reclassify `CROSSES_LOCKED_OOS` structurally, not by reading a
   price past the wall.** Once bars are fetched only through
   `effective_as_of` (point 1), a security's own bar list never contains
   a bar beyond `development_end` when `development_end` is set -- so
   `compute_forward_outcome()` no longer needs to peek at an OOS bar's
   date at all. Change its exit-availability branch: when
   `development_end is not None` and `exit_idx >= len(bars)`, classify
   `CROSSES_LOCKED_OOS` (by construction, anything beyond the bounded
   fetch IS Locked OOS when a wall is set -- no date inspection needed).
   `INSUFFICIENT_FUTURE_DATA` would then apply only when
   `development_end is None` (no wall at all -- running out of bars there
   means data genuinely doesn't exist yet, the only case left). This
   removes the current `exit_bar.date > development_end` check entirely,
   because under the new fetch bound that bar is never present to check.
3. **`research_period` wiring.** Have `run_evaluation()` read
   `evaluation_config.data["research_period"]` as the DEFAULT for
   `development_start`/`development_end` when the caller passes `None` for
   either, with explicit function arguments taking precedence when given
   (matching the existing `data_as_of = data_as_of or development_end`
   pattern already in the code). Removing `research_period` from the
   YAML instead is NOT treated as an equivalent fix here -- the spec text
   describes it explicitly, and dropping it would be a contract change
   that needs Radu's separate approval, not a documentation-integration
   side effect of a bug fix.

**Tests needed:** a regression fixing `development_end` and asserting
that NO PIT call for that run returns a bar dated after it (spy-based, as
in this round's reproduction); a regression planting a late-knowledge
corporate action with an in-Development `effective_date` and asserting
the resulting forward_return is unaffected (pre-fix: this assertion
currently fails); a regression asserting `CROSSES_LOCKED_OOS` is still
produced correctly under the new bounded-fetch design (TEST 27's own
`test_no_valid_outcome_exits_after_development_end` should keep passing
unmodified -- it asserts the outcome, not the mechanism); a `research_period`
wiring test once the precedence rule is implemented.

## F2a -- Frozen signature set accepted without content verification

**Problem (Top Finding 12a):** `run_evaluation()` never recomputes
`freeze_signature_set()` on the incoming `SignatureSet` to check its
`signature_set_id` actually matches its own `signatures`.

**Proposed fix:** at the top of `run_evaluation()`, recompute
`freeze_signature_set(list(signature_set.signatures)).signature_set_id`
and raise if it doesn't equal `signature_set.signature_set_id`. This is a
cheap, deterministic check with no behavior change for any legitimately-
constructed `SignatureSet`.

**Tests needed:** a regression constructing a `SignatureSet` via
`dataclasses.replace()` with mismatched content/id (as in this round's
reproduction) and asserting `run_evaluation()` now raises.

## F2b -- Duplicate `signature_id` collides in BH correction

**Problem (Top Finding 12b):** nothing rejects two
`EvaluationSignatureDefinition`s sharing one `signature_id` within a
`SignatureSet`; `record_key()` then collapses their BH entries into one.

**Corrected 2026-10-04 (Radu): the check must sit at `run_evaluation()`'s
own entry gate -- it cannot rely on `freeze_signature_set()` alone.**
F2a's own reproduction already demonstrates a `SignatureSet` reaching
`run_evaluation()` without ever having passed through
`freeze_signature_set()` (built directly via `dataclasses.replace()` on
an existing frozen instance) -- a uniqueness check placed only inside
`freeze_signature_set()` or a constructor would be bypassed by exactly
that same construction path, for the same reason F2a's own gate must be
at `run_evaluation()`, not at construction time.

**Proposed fix:** at the top of `run_evaluation()`, immediately
alongside the F2a content-verification check (both are entry-gate
checks on the same `signature_set` argument, naturally placed together,
before any PIT/BH work), validate that `len({s.signature_id for s in
signature_set.signatures}) == len(signature_set.signatures)`, raising on
a duplicate. `freeze_signature_set()` can ALSO gain the same check as a
secondary, defense-in-depth guard for any future caller that constructs
a set through it -- but that secondary check is not a substitute for the
engine-entry gate, which is the only check every `run_evaluation()` call
actually passes through regardless of how its `SignatureSet` was built.

**Tests needed:** a regression asserting a `SignatureSet` with two
definitions sharing one `signature_id`, constructed via
`dataclasses.replace()` (bypassing `freeze_signature_set()`, mirroring
F2a's own reproduction) is still rejected by `run_evaluation()` itself --
not only a `SignatureSet` built through the normal constructor path.

## F6 -- `family_test_count` missing (added 2026-10-04, this section was
missing from the previous draft -- Radu's correction)

**Problem (Top Finding 7, re-confirmed as GPT's F6):** SS44 explicitly
names `family_test_count` in `BaselineComparison`'s required field list;
the field does not exist anywhere in `src/` or `tests/`.

**Proposed fix:** add `family_test_count: Optional[int]` to
`BaselineComparison` (`models/entities.py:145-164`). Exact definition,
matching how `benjamini_hochberg()` already groups records (
`multiple_testing.py:46-48`, `families.setdefault(family_id(r),
[]).append(r)`): **`family_test_count` is the number of `PValueRecord`s
actually included in that record's own family** -- i.e. `len(fam_records)`
for the family `benjamini_hochberg()` grouped this profile's own record
into, NOT a count of every signature x horizon combination that exists
in the run (some of those never produce a `raw_p` at all and so are
never tested -- see below).

**Handling profiles without a `raw_p`:** a profile whose
`baseline_comparison.raw_p is None` (e.g. `INSUFFICIENT_SUPPORT`, or the
F3 "comparison unavailable" case this proposal's F3 fix may introduce)
was never a member of any BH family -- `benjamini_hochberg()` already
excludes it from `records` in `engine.py:396-399`. Its
`family_test_count` should be `None`, mirroring the existing pattern for
`adjusted_p`/`family_id` (`engine.py:409-412`), which already leave both
`None` for exactly this case. A profile WITH a `raw_p` always has a
non-`None` `family_test_count` once BH is applied, same as it gets a
non-`None` `adjusted_p`/`family_id`.

**Tests needed:** a regression asserting `family_test_count` equals the
actual number of signature x horizon combinations sharing one family
(timeframe + horizon_bars + outcome_type + evaluation_run) in a
multi-signature FORMAL_DEVELOPMENT run; a regression asserting
`family_test_count is None` for a profile with `raw_p is None`.

## F3 -- Reported effect and tested significance can describe different populations

**Problem (Top Finding 13):** `stratified_permutation_p_value()` drops a
bin with an empty baseline side from both `observed` and the null, but
`mean_difference`/`signature_mean_relative` keep that bin's signature
episodes unconditionally.

**Corrected 2026-10-04 (Radu): a warning alone does not fix this.**
Attaching a warning while still presenting the full-population
`mean_difference` next to a sub-population `raw_p`/CI as "the
significance of that difference" keeps publishing two numbers that
answer different questions under one label -- the warning only
discloses the mismatch, it does not remove it. The proposal must pick
one of two actually-consistent designs, not a disclosed inconsistency:

- **(a) Comparison UNAVAILABLE** when the bins needed to support the
  signature's own full population lack baseline controls -- the
  `BaselineComparison` for that signature/horizon reports no
  `mean_difference`/`raw_p`/CI at all (all `None`), with a status or
  warning naming why (which bins were uncovered). This is the "fail
  closed" option: no comparison is offered unless it covers the same
  population it claims to.
- **(b) Explicit common-support comparison.** Restrict BOTH the
  reported effect (`mean_difference`, `median_difference`) AND the
  tested significance (`raw_p`, `mean_difference_ci`,
  `standardized_effect`) to the identical bin set -- only bins where the
  signature has episodes AND the baseline has controls. Report, alongside
  the numbers, how many signature episodes were excluded and from which
  bins (a new field, or reuse of `warnings`, naming the exclusion
  explicitly) -- so a reader sees the restricted population size, not
  just a disclaimer next to an unrestricted one.

Either way, the signature's own **descriptive statistics** over its FULL
population (`relative_outcome` / `absolute_outcome` -- the plain
`DescriptiveStats`, not the baseline comparison) can stay as they are;
nothing here requires restricting what the signature's own raw outcomes
report, only what is compared against a baseline and tested. The
restriction must never happen silently -- either (a) or (b) makes the
restriction or the unavailability an explicit, visible part of the
output, never something inferred by comparing two numbers side by side.
Which of (a)/(b) to build is Radu's call -- this proposal does not
default to one.

**Tests needed:** whichever direction is chosen, a regression on the
two-bin, one-sided-coverage fixture from this round's reproduction,
asserting that `mean_difference` and `raw_p`/CI either (a) are both
`None` together, or (b) are computed over the identical, explicitly
reported bin subset -- never one over the full population and the other
over a silently narrower one.

## F4 + F5 -- must be designed together, not patched separately (Radu's correction, 2026-10-04)

**Problem (Top Findings 14-15):** `baseline_iqr` pools every bin
unweighted while `baseline_mean`/`baseline_median` are weighted by the
signature's own temporal composition (F4); within each bin,
`stratified_baseline_point_estimate()` averages raw rows rather than
per-security means, letting a security with more sessions dominate (F5,
directly contradicting SS74C's own text).

**Corrected 2026-10-04 (Radu): the two previous drafts of this section
proposed independent patches that do not actually fix the problem.**
Two specific errors in the withdrawn draft:
- A weighted average of each bin's own IQR is **not, in general, equal
  to** the IQR of the properly-weighted combined distribution -- IQR is
  a quantile-based statistic, not a linear one, so combining per-bin
  IQRs by weight does not reconstruct the weighted population's own
  quantiles the way a weighted average of means does. Proposing that as
  "the first option" treated IQR as if it combined like a mean; it does
  not.
- Restricting the IQR's pool to only non-zero-weight bins fixes the
  single case this round's own F4 regression fixture happens to cover
  (one active bin, one inactive) but does nothing for multiple ACTIVE
  bins carrying DIFFERENT weights -- a bin weighted `0.8` and a bin
  weighted `0.2` would still contribute their raw values to the IQR pool
  in equal, unweighted proportion, reintroducing the same class of
  mismatch between mean/median's weighting and IQR's weighting, just
  without the zero-weight edge case to make it obvious.

**Proposed fix, both findings from one consistent definition:** before
computing ANY baseline statistic (mean, median, or IQR), define the
baseline's own weighted empirical distribution explicitly -- e.g. an
explicit list of `(value, weight)` pairs (or an equivalent weighted
resampling), built by: (1) grouping each bin's raw rows by `security_id`
and taking one representative value per security within that bin (the
within-bin fix for F5 -- see estimator choice below); (2) assigning each
bin's resulting per-security values a combined weight of (the
signature's own bin weight) / (number of securities contributing to
that bin), so bins and securities within them are both weighted
consistently. Compute `baseline_mean`, `baseline_median`, AND
`baseline_iqr` all as functions of this ONE weighted distribution (a
weighted mean, a weighted median, and a weighted-quantile-based IQR --
e.g. via a weighted-quantile function, not `statistics.quantiles()` on
an unweighted list) -- not as three separately-maintained code paths
that can drift apart the way mean/median vs. IQR already have.

**Open design questions, Radu's call, not defaults this proposal
assumes:**
- **Within-bin estimator (F5).** Equal weight per security (one
  representative value per security per bin, e.g. that security's own
  mean or median within the bin) is **a proposal to discuss, not a
  requirement already approved** -- SS74C's text names the dominance
  problem to avoid but does not specify the exact estimator. Capping a
  single security's row contribution, or a different declared policy,
  are also open alternatives.
- **Large-universe-period domination.** SS74C's own approved text names
  TWO distortions to avoid: "an action with long history" dominating
  (F5, addressed above) AND **"periods with very large universe"
  dominating** -- a bin drawn from a time when the eligible universe was
  much larger than another bin's. Neither this proposal's within-bin fix
  nor the existing between-bin (signature-composition) weighting
  addresses universe-size variation across bins at all -- this is a
  separate, currently fully open dimension of SS74C that needs its own
  explicit design decision (e.g. capping or weighting by universe size
  per bin) before it can be considered resolved.

**Tests needed:** a regression on this round's zero-weight-bin fixture
(F4's original case: one active bin, one inactive -- `standardized_effect`
currently moves from `14.839` to `0.337` on that fixture when it should
not); a regression on this round's LONG/SHORT fixture (F5's original
case: 2 securities, uneven row counts within one bin); and, **new per
this correction**, a regression with >= 2 ACTIVE bins carrying different,
non-trivial weights (e.g. `0.7`/`0.3`), each with its own multi-security
raw-row population, asserting `baseline_mean`, `baseline_median`, AND
`baseline_iqr` are all computed consistently from the same weighted
distribution -- the single-active-bin fixtures above cannot catch a
cross-active-bin weighting error, only this one can.

## S1 -- Numeric validation gaps (SUSPECTED, not yet a demonstrated contract violation)

**Problem (Top Finding 16):** `compute_forward_outcome()` divides by
`entry_bar.split_adjusted_close` with no zero/finite guard; `0.0` raises
an uncaught exception, `NaN`/negative/`inf` pass through as `VALID`.

**Proposed fix, contingent on Radu's read of whose responsibility this
is:** if Evaluation is meant to be defensive regardless of upstream
guarantees, add a finite-and-positive check on both `entry_bar` and
`exit_bar` prices before the division, routing to `INVALID_INPUT`
(already an available `OutcomeStatus`) rather than raising or returning a
nonsensical `VALID` result. If QA/PIT upstream already guarantees this
and Evaluation is intentionally trusting that boundary, this needs no
code change -- only an explicit note in `spec003_known_limitations.md`
stating the trust boundary, so it isn't silently relied upon.

**Tests needed (if fixed):** regressions for `0.0`, `NaN`, negative, and
`inf` entry/exit prices, asserting `INVALID_INPUT` rather than an
exception or a nonsensical `VALID` result.

## S2 -- Run/config identity incomplete (SUSPECTED, reproducibility)

**Problem (Top Finding 17):** `build_run_id()`'s fingerprint excludes
`security_ids`, `benchmark_security_id`, `data_as_of`, and the actual
`horizons` values run.

**Note, 2026-10-04 (Radu):** this stays a SUSPECTED ISSUE, a
reproducibility proposal, not an already-established contractual
non-compliance -- SS60's own text ("identical inputs -> identical
output") is not itself contradicted by anything demonstrated this round
(no case produced different ids from identical inputs); what's proposed
below is a strengthening of what counts as "identical inputs" for the
id's own purposes, which is a design choice, not a confirmed defect.

**Proposed fix:** extend `build_run_id()`'s fingerprint fields to include
a stable hash of `security_ids` (sorted), `benchmark_security_id`,
`data_as_of`, and `horizons` (sorted). This is additive and does not
change any existing run_id's *meaning* for inputs that were already
distinct on the currently-hashed fields -- it only makes previously-
colliding runs (same hashed fields, different universe/horizon) produce
different ids. **This changes the shape of every future `evaluation_run_id`
and needs its own versioning rule** -- e.g. a `run_id_scheme_version`
marker, or accepting that ids computed before vs. after this change are
simply not comparable -- so that extending the fingerprint is itself
done under a stated version discipline (the same discipline SS45 already
requires of versioning a formula change), not as a silent reinterpretation
of what a stored run_id means.

**Tests needed:** a regression asserting two runs with different
`horizons` (holding everything else equal) now produce different
`evaluation_run_id`s.

## G1 -- TEST 26 AST guard blind to parent-import form

**Problem (Top Finding 18):** same pattern as Spec #002's TEST 17/18 --
`_imported_modules()` never inspects `ast.ImportFrom`'s `names` (the
imported symbols), only `.module`. **Corrected 2026-10-04 (Radu): the
#002 gaps were DOCUMENTED (`docs/audit_spec002_requirement_code_test.md`'s
Top Findings 5/18), not fixed in the verified baseline** -- no code
change has been made to TEST 17 or TEST 18 themselves. This proposal
does not inherit an existing fix to mirror; it proposes the same kind of
fix independently for TEST 26, and if approved, that approval would
still leave TEST 17/18's own documented gaps open as a separate,
not-yet-authorized item.

**Proposed fix:** extend `_imported_modules()` to also collect
`alias.name` for each name in `node.names` when the node is
an `ast.ImportFrom`, so `from src import evaluation as ev` is caught as
importing `evaluation`, not just `src`.

**Tests needed:** a regression using the exact scratch-file probe from
this round (`from src import evaluation as ev`), asserting the guard now
fails as expected.

## G2 -- TEST 34's assertions do not test what they claim

**Problem (Top Finding 19):** `test_34_holding_decay_curve.py:41` ends in
`or True`, making it unconditionally pass; line 43's `hasattr(curve,
"winner")` check is trivially true for any plain list, not a guard
specific to this function.

**Proposed fix:** remove the `or True`; if the intent was to assert no
"OTHER" signature leaks into the curve, that is already implicitly
covered by `curve == [(1, ...), (2, ...), ...]` only ever containing
`SIG`'s own data (the test constructs `decay_curve()`'s real filter logic
is in `engine.py:434`, filtering by `signature_id`) -- a cleaner
assertion would check `curve`'s values directly rather than re-deriving
a filtered list from `profiles` only to compare it to itself. For the
"no winner" check, assert on something that actually could carry a
winner concept if one were added -- e.g. assert `EvidenceProfile` itself
(not a plain list) has no such field, which `dataclasses.fields()` can
check meaningfully.

**Tests needed:** this IS the test fix -- no separate test beyond
correcting `test_34` itself.
