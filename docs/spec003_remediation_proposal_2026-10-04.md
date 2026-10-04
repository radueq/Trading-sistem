# Spec #003 -- Remediation Proposal (2026-10-04)

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

**Proposed fix, two parts:**
1. **Read-time wall.** Introduce a PIT-bounded fetch for Evaluation's own
   use: either (a) a new `pit.access` function that takes both an
   `as_of` (knowledge-time cutoff for what corporate actions/listings are
   visible) and a `price_through` bound (which bars are returned at all),
   or (b) have `_resolve_session_dates()`/`_fetch_bars_by_security()` call
   the existing `get_price_series_as_of(conn, sid, development_end)` for
   anything that must never see OOS, and keep a *separate*,
   explicitly-named fetch at `data_as_of` only for the exit-classification
   step that legitimately needs to know a date fell in Locked OOS. The
   second option changes less surface area but needs a clear boundary so
   a future caller doesn't accidentally reuse the `data_as_of`-bound fetch
   for computation.
2. **`research_period` wiring.** Either have `run_evaluation()` read
   `evaluation_config.data["research_period"]` as the default for
   `development_start`/`development_end` when the caller passes `None`
   (matching what the config file already implies), or remove the
   `research_period` key from `evaluation.yaml` and the derived docs that
   describe it as load-bearing, so the config stops claiming a behavior
   the code doesn't have. Either is a legitimate choice; leaving the
   current silent mismatch is not.

**Tests needed:** a regression fixing `development_end` and asserting
that NO PIT call for that run returns a bar dated after it (spy-based, as
in this round's reproduction); a regression planting a late-knowledge
corporate action with an in-Development `effective_date` and asserting
the resulting forward_return is unaffected (pre-fix: this assertion
currently fails); a `research_period` wiring test once a direction is
chosen.

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

**Proposed fix:** validate uniqueness of `signature_id` across
`signature_set.signatures` in `run_evaluation()` (or in
`freeze_signature_set()` itself, which would also protect any other
future caller), raising on a duplicate -- mirroring the existing pattern
already used for Spec #004's Research Queue (`PATCH #004-B #5`, which
rejects a duplicate `signature_id`).

**Tests needed:** a regression asserting a `SignatureSet` with two
definitions sharing one `signature_id` is rejected before any PIT/BH
work happens.

## F3 -- Reported effect and tested significance can describe different populations

**Problem (Top Finding 13):** `stratified_permutation_p_value()` drops a
bin with an empty baseline side from both `observed` and the null, but
`mean_difference`/`signature_mean_relative` keep that bin's signature
episodes unconditionally.

**Proposed fix, Radu's call between two options, not a code default to
assume:** (a) restrict the REPORTED `mean_difference`/`median_difference`
to the same bins the permutation test actually used (the two numbers
would then always describe the same population, at the cost of silently
shrinking the signature's own reported sample when any bin lacks
controls); or (b) keep the current reported statistic over the full
signature population, but add an explicit field/warning
(`EvidenceProfile.warnings` already exists as a tuple) naming which bins
were excluded from the significance test and why, so a reader is told
the two numbers differ in scope rather than discovering it by inspection.
Both preserve the stratification Radu approved in SS74C; neither should
be implemented without his read on which framing he wants.

**Tests needed:** whichever direction is chosen, a regression on the
two-bin, one-sided-coverage fixture from this round's reproduction,
asserting the reported statistic and the tested statistic are
consistent (same population) or that a warning is attached naming the
mismatch.

## F4 -- `baseline_iqr` pools every bin unweighted

**Problem (Top Finding 14):** `robust_iqr()` is computed over
`baseline_dated`, the full cross-bin pool, while `baseline_mean`/
`baseline_median` are correctly weighted by the signature's own temporal
composition.

**Proposed fix:** compute the IQR the same way the mean/median are
computed -- either a weighted combination of each bin's own IQR
(skipping zero-weight bins, matching `stratified_baseline_point_estimate`'s
existing skip rule), or restrict the pool feeding `robust_iqr()` to only
the bins with non-zero signature weight before computing IQR on that
restricted pool. The second is simpler and keeps `robust_iqr()`'s own
signature unchanged; the first stays closer to a weighted-quantile
pool. Either removes the mismatch Finding 14 demonstrates.

**Tests needed:** a regression on this round's zero-weight-bin fixture,
asserting `standardized_effect` is unchanged by adding baseline controls
to a bin where the signature has no episodes (currently it changes from
`14.839` to `0.337` on that fixture -- post-fix it should not move).

## F5 -- Within-bin raw-row weighting (direct SS74C contradiction)

**Problem (Top Finding 15):** `stratified_baseline_point_estimate()`
computes each bin's statistic directly over raw `(security_id, as_of,
value)` rows, so a security contributing more sessions to a bin gets
proportionally more weight in that bin's mean/median -- the exact
dominance-by-history-length SS74C's own approved text says to avoid.

**Proposed fix, needs Radu's read on the estimand, not just an
arithmetic patch:** group `bin_values` by `security_id` first, take each
security's own per-security statistic (mean or median) within the bin,
and THEN compute the bin's statistic over those per-security values
(equal weight per security, not per row). This is the most direct fix
matching SS74C's text, but changes what "the baseline" means for a bin
with very unequal security counts (a bin with 1 security contributing
500 rows and 9 contributing 1 row each would move from one row-weighted
number to an equal-weight-per-security number that could differ a lot).
Radu's decision on whether equal-per-security weighting is the right
estimand (vs., e.g., capping per-security row contribution, or a
different declared policy) should precede implementation -- the amendment
text names the problem to avoid but does not specify the exact
estimator.

**Tests needed:** a regression on this round's LONG/SHORT fixture
(2 securities, uneven row counts, known per-security means), asserting
the bin's baseline statistic no longer shifts when one security gains an
extra same-mean row.

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

**Proposed fix:** extend `build_run_id()`'s fingerprint fields to include
a stable hash of `security_ids` (sorted), `benchmark_security_id`,
`data_as_of`, and `horizons` (sorted). This is additive and does not
change any existing run_id's *meaning* for inputs that were already
distinct on the currently-hashed fields -- it only makes previously-
colliding runs (same hashed fields, different universe/horizon) produce
different ids, which is strictly more correct per SS60.

**Tests needed:** a regression asserting two runs with different
`horizons` (holding everything else equal) now produce different
`evaluation_run_id`s.

## G1 -- TEST 26 AST guard blind to parent-import form

**Problem (Top Finding 18):** same pattern already fixed for Spec #002's
TEST 17/18 -- `_imported_modules()` never inspects `ast.ImportFrom`'s
`names` (the imported symbols), only `.module`.

**Proposed fix:** mirror the #002 fix -- extend `_imported_modules()` to
also collect `alias.name` for each name in `node.names` when the node is
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
