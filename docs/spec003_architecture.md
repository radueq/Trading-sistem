# Spec #003 v1.1 -- Architecture Note

Outcome-Aware Evaluation Engine, Fast-Swing / Bar-Based. Depends on
Spec #001 Accepted Baseline `aa56bb5` and Spec #002 Accepted Baseline
`4f36708` (+ PATCH #002-B `compute_discovery_observations()`, the
resolution to this spec's own IMPLEMENTATION BLOCKER SS74A).

## Data flow

```
PIT-safe historical data (Spec #001 pit.access)
  + Historical Discovery observations (Spec #002 compute_discovery_observations(), PRE-budget)
  -> Outcome Engine (outcomes/forward_returns.py, outcomes/benchmark.py)
  -> Episode Engine (observations/episodes.py)
  -> Statistical Evaluation (statistics/*)
  -> Evidence Profile (models/entities.py)
```

`discovery.engine.compute_discovery_observations(conn, security_ids,
as_of, benchmark_security_id, config)` is called ONCE PER SESSION across
the Development window -- never `run_discovery()`'s post-budget output
(Candidate Budget is a downstream/LLM compute-budget knob, Spec #002
SS21, not a statistical sampling decision -- IMPLEMENTATION BLOCKER
SS74A, resolved by PATCH #002-B). `evaluation.engine.run_evaluation()`
is the single entry point.

## Bar-based, timeframe-agnostic contract (SS3-4)

Every outcome carries `timeframe` + `horizon_bars`, never a hardcoded
day-coupled field name (`forward_return_5d` and similar are forbidden --
TEST 3). `horizon_bars` moves N POSITIONS in a security's own PIT bar
series (`outcomes/forward_returns.py`'s `_entry_index_at_or_before` +
`entry_idx + horizon_bars`), never calendar-date arithmetic (TEST 2).
At `1D` today, 1 bar happens to equal 1 trading day; the engine never
assumes that equivalence anywhere in its logic, so a future `4H` PIT
extension (Spec #001 concern, not built here -- see
`docs/spec002_architecture.md`'s "Adding 4H/1H later") needs zero
changes to this module -- only Discovery's own hardcoded
`TIMEFRAME = "1D"` constant (a separate, already-documented gap, see
`docs/spec002_known_limitations.md`'s PATCH #001-C note).

Benchmark alignment is the one place position is explicitly WRONG: it
is by actual DATE (`outcomes/benchmark.py`, exact-date lookup), since
the benchmark's own bar series can have different dates present than a
given security's. MISSING_BENCHMARK when no benchmark bar exists at the
needed date -- no silent fallback to a nearby date.

## Locked-OOS wall (SS12/SS14)

`development_end` (nullable, `research_period` config) is the wall.
`outcomes/forward_returns.compute_forward_outcome()` inspects only the
exit bar's DATE to classify `CROSSES_LOCKED_OOS` -- its price/volume
fields are never read on that branch (TEST 27). This is a computation-
level boundary, not a physical storage partition (Level 1 SQLite has
none): the caller can supply `data_as_of` later than `development_end`
(real data genuinely exists beyond the wall, e.g. because time has
since passed) and the wall still holds -- TEST 6/7/27 all exercise this.
`data_as_of` defaults to `development_end` when not given; in that case
there is nothing beyond the wall to fetch at all, so a shortfall reads
as `INSUFFICIENT_FUTURE_DATA` instead (both mean "no valid measurement,"
the distinction only matters when data beyond the wall is actually
available and deliberately not used).

## Two views, one default (SS30-31)

`observations/episodes.py` collapses consecutive matching dates (gap <=
config `episode.max_gap_bars`, in BAR positions) into one Episode,
representative = FIRST (the only value implemented). RAW_OBSERVATIONS
(every matching date) is always available from the raw match list;
EPISODE_DEDUPLICATED (one outcome per episode) is the default and only
statistical view `engine.py` feeds into the descriptive/bootstrap/
comparison layers -- raw consecutive observations are never treated as
independent samples (SS29).

## TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE (SS33-34, Radu's Sec.74C amendment)

`baseline/universe.py`. The control pool is every ELIGIBLE
(security, as_of) observation's outcome across the whole eligible
universe (never just the signature's own matches, never Candidate
Budget's post-selection output) -- but combined using the SIGNATURE's
own temporal-bin composition (`bin_composition()`), not the baseline's
raw bin sizes: per-bin baseline statistic computed directly, then a
weighted average across bins using the signature's own weights
(`stratified_baseline_point_estimate`). A signature that clusters in one
regime is compared against baseline observations drawn from that SAME
regime mix, not diluted/dominated by an unrelated period. The
signature's own `(security_id, observation_as_of)` pairs are excluded
from their own control pool (`exclude_self`). Documented simplification
(not a true weighted-quantile pool): the baseline median is a weighted
average of PER-BIN medians, not a single pooled weighted quantile -- see
`docs/spec003_known_limitations.md`.

## Statistics (Radu's Sec.74B/D amendment, PATCH #003-A per GPT Review #003 Round 1)

- **TIME_BLOCK clustered bootstrap** (`statistics/bootstrap.py`) is the
  PRIMARY V1 inference mechanism for confidence intervals -- resamples
  CONTIGUOUS blocks of `bootstrap.block_length_bars` SESSION DATES (a
  real market-time interval), not a run of `block_length_bars` (date,
  value) rows, and not a run of the dates merely present in the
  signature's own values. PATCH #003-A fix (GPT Review #003 Round 1,
  mandatory finding #2): the original cut sorted `(date, value)` pairs
  and chunked by ROW COUNT, so same-day observations across different
  securities (e.g. NVDA/AMD/AVGO/MRVL/CRDO all showing an episode the
  same week the market jumps) could be split across different blocks --
  destroying exactly the common-shock structure TIME_BLOCK clustering
  exists to preserve. Fixed: values are grouped by date FIRST.
  PATCH #003-B fix (GPT Review #003 Round 2): grouping by date was not
  enough on its own -- blocks were still built over the dates PRESENT IN
  THE SIGNATURE'S OWN VALUES, not the real trading calendar. For a rare
  signature (e.g. 4 matching dates scattered across several months),
  those event dates are not "4 consecutive sessions"; treating them as
  such loses the actual local-time-window/regime structure TIME_BLOCK
  exists to preserve. Fixed: `time_block_bootstrap_replicates()` now
  takes the run's real `session_dates` calendar (the benchmark's own bar
  dates within Development) as an explicit parameter, and every caller
  in `engine.py` passes it -- the global calendar for the signature's own
  bootstrap, and each bin's own slice of it
  (`session_dates_by_bin`) for `stratified_baseline_bootstrap_replicates`.
  A session with no value that day contributes nothing when its block is
  drawn -- normal, not an error (TEST 39). `block_length_bars` is
  configurable and must never be tuned against observed results.
  Security concentration is reported SEPARATELY as a diagnostic
  (`statistics/concentration.py`), not folded into the bootstrap choice.
- **Raw significance is a SEPARATE, STRATIFIED permutation test**
  (`statistics/comparison.py`'s `stratified_permutation_p_value`) --
  NEVER informally derived from whether a bootstrap CI crosses zero
  (Radu's explicit correction: CI and p-value are related but distinct
  objects). PATCH #003-A fix (GPT Review #003 Round 1, mandatory finding
  #4): the original cut compared the signature against the RAW,
  unstratified baseline pool while the point estimate/CI compared
  against `TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE` -- two different
  hypotheses feeding one reported effect. Fixed: permutation now happens
  WITHIN each temporal bin (never across bins, which would re-introduce
  the regime-mixing problem stratification exists to avoid), and the
  per-bin permuted differences are combined using the signature's SAME
  fixed bin weights as the point estimate/CI, via the identical
  inclusion rule (a bin counts only when both its signature and baseline
  pools are non-empty and its weight > 0). The plain, unstratified
  `permutation_p_value` primitive is kept for contexts with no temporal-
  bin structure at all (e.g. Example D's flat synthetic demonstration).
- **BH-FDR** (`statistics/multiple_testing.py`) is mandatory for
  FORMAL_DEVELOPMENT mode, applied within families (same timeframe +
  horizon_bars + outcome_type + evaluation_run, SS45) independently
  (TEST 22 proves family isolation). PATCH #003-A fix (GPT Review #003
  Round 1, mandatory finding #1): `benjamini_hochberg()` used to return
  `{signature_id: (adjusted_p, family_id)}`, but the SAME signature is
  tested at every horizon (a different family each time) -- later
  families silently overwrote earlier ones in that dict, and
  `run_evaluation()`'s application loop looked results up by
  `signature_id` alone, so one horizon's adjusted_p/family_id could end
  up applied to every other horizon of the same signature. Fixed:
  `benjamini_hochberg()` now returns
  `{record_key(record): (adjusted_p, family_id)}`, keyed by the FULL
  `(signature_id, timeframe, horizon_bars, outcome_type,
  evaluation_run_id)` tuple; `run_evaluation()` looks up that same key
  per profile. TEST 36 proves each horizon gets its own family_id/
  adjusted_p (and would fail against the pre-patch key shape). The one
  formally-tested `outcome_type` at Level 1 is `relative_return` (see
  `docs/spec003_known_limitations.md`).
- **Robust standardized effect**: `median_difference / (baseline_IQR /
  1.349)` -- IQR/1.349 is the classical normal-consistent robust-sigma
  estimator, chosen over Cohen's d because of return-distribution
  tails/outliers. `standardized_effect_status = "UNDEFINED_ZERO_SCALE"`
  (never a silent division) when `baseline_IQR` is ~0.

## FORMAL_DEVELOPMENT enforcement (PATCH #003-A finding #3, PATCH #003-B provenance guard)

`run_evaluation()` hard-errors, before any PIT/Discovery work, if `mode
== "FORMAL_DEVELOPMENT"` and any signature in the `SignatureSet` is not
`creation_mode == PRE_REGISTERED` with `created_before_outcome_evaluation
== True` (TEST 37). A frozen Signature Set (SS26) is meaningless if a
post-hoc signature can still run through a formal evaluation. In
addition, `registry.signatures.freeze_signature_set()`'s fingerprint now
includes `creation_mode`, `created_before_outcome_evaluation`,
`discovery_engine_version`, and `discovery_config_version` -- not just
the matching conditions -- so the exact same lane/reason-code
definition flipping from `EXPLORATORY_POST_HOC` to `PRE_REGISTERED` (or
Discovery's own formulas changing underneath it) produces a DIFFERENT
`signature_set_id`, never a silent identity match (TEST 28 covers the
general property; TEST 37 covers the FORMAL_DEVELOPMENT rejection
itself).

**PATCH #003-B guard (GPT Review #003 Round 2):** the fingerprint alone
only guarantees a provenance MISMATCH produces a different
`signature_set_id` -- it does not stop `run_evaluation()` from actually
being called with a signature pre-registered under a DIFFERENT
Discovery config/engine/timeframe than the one it's now being run
against (two legitimately-different entities the engine would otherwise
silently accept together). `run_evaluation()` now additionally checks,
per signature, in `FORMAL_DEVELOPMENT` mode: `sig.timeframe == ` the
run's `timeframe`, `sig.discovery_engine_version ==` the current
`DISCOVERY_ENGINE_VERSION`, and `sig.discovery_config_version ==` the
`discovery_config` actually passed in -- any mismatch is a hard error
(TEST 40).

## Support gated on the population actually tested (PATCH #003-A, GPT Review #003 Round 1, finding #5)

`SupportInfo.episode_n` is the TOTAL episode count (every outcome
status); `SupportInfo.valid_episode_n` is the subset with a usable VALID
relative_return outcome. `support_status` and `concentration`
(`statistics/concentration.py`) are both computed over that VALID
population (`relative_valid` in `engine.py`), never the raw total --
GPT's example: 35 total episodes but only 12 VALID relative outcomes
must not read as `SUFFICIENT_SUPPORT` against a threshold of 30.
`missingness` still reports the total for reconciliation (TEST 32).

## Exact entry-bar alignment (PATCH #003-A, GPT Review #003 Round 1, finding #6)

`outcomes/forward_returns.py` now requires a bar dated EXACTLY
`observation_as_of` -- not "the latest bar at or before" -- else
`INVALID_INPUT` (TEST 38). The earlier at-or-before lookup could silently
predate `observation_as_of` (a halt/gap), while
`outcomes/benchmark.py`'s alignment requires an exact-date benchmark bar
for that same `as_of`; mixing the two would compare a security return
measured from one date against a benchmark return measured from
another.

## No automatic verdict, no combined score (SS49/SS51)

`EvidenceProfile` never contains GOOD/BAD/TRADE/EDGE_CONFIRMED/WINNER,
and no field anywhere aggregates effect size + p-value + frequency +
stability into one number (TEST 25, an AST identifier scan mirroring
Spec #002's own TEST 13/17). `support_status` is the only categorical
verdict-shaped field, and it is purely factual: SUFFICIENT_SUPPORT /
INSUFFICIENT_SUPPORT against `support.minimum_episode_count` AND
`support.minimum_unique_securities` (both must pass).

## Decay curve, not a winner (SS52-53)

`engine.decay_curve(profiles, signature_id)` returns every horizon's
`(mean_forward, mean_relative)`, sorted, for one signature -- the caller
reads the curve; nothing in this module selects or names a "best"
horizon (TEST 34).

## Package structure

```
src/evaluation/
  models/entities.py        ForwardOutcome, OutcomeStatus, Episode,
                             EvaluationSignatureDefinition, SignatureSet,
                             DescriptiveStats, BaselineComparison,
                             ConcentrationStats, StabilityBinResult,
                             OpportunityDensity, MissingnessReport,
                             SupportInfo, EvidenceProfile,
                             EvaluationRunRegistry
  config/
    loader.py                EvaluationConfig + config_version (hash)
    evaluation.yaml            horizons/support/episode/bootstrap/
                                comparison/multiple_testing/stability/
                                research_period -- TEST_CONFIG
  outcomes/
    forward_returns.py         R_{i,t,h}, bar-indexed, Locked-OOS wall
    benchmark.py                 AR_{i,t,h}, date-keyed alignment
  observations/
    signatures.py               EvaluationSignature matching (AND of
                                 lane-state/reason-code conditions)
    episodes.py                   consecutive-observation dedup
  baseline/
    universe.py                 TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE
  statistics/
    descriptive.py               mean/median/std/quantiles/positive_rate
    bootstrap.py                   TIME_BLOCK clustered bootstrap -> CI
    comparison.py                    permutation test -> raw_p
    multiple_testing.py                BH-FDR
    stability.py                        temporal bins
    concentration.py                      security concentration
    opportunity.py                          episode frequency (descriptive only)
  registry/
    runs.py                       EvaluationRunRegistry, deterministic run_id
    signatures.py                   SignatureSet freezing
  engine.py                       run_evaluation() -- THE single entry point
tests/spec003/
  fixtures/tiny_universe.py     TEST_CONFIG small/fast universe (3 securities
                                 + benchmark) -- distinct from Spec #002's own
                                 32-security universe, which is sized for
                                 single-as_of queries, not a per-session
                                 Evaluation sweep across a whole window
  test_01..35_*.py                the 35 required tests
  test_36..38_*.py                  PATCH #003-A regression tests (GPT
                                     Review #003 Round 1 findings #1/#3/#6)
  test_39..40_*.py                   PATCH #003-B regression tests (GPT
                                      Review #003 Round 2: real session
                                      calendar, provenance guard)
  generate_report_artifacts.py      produces spec003_examples/
                                     multiple_testing_report/performance_report.md
```

## PIT enforcement, Discovery isolation

`evaluation/` reaches Data Foundation two ways, both legitimate for an
outcome-aware module: `discovery.engine.compute_discovery_observations()`
for observations (still fully PIT-bounded per-session internally), and
`data_foundation.pit.access.get_price_series_as_of()` directly for
forward-outcome price series (Evaluation is explicitly authorized to see
future data -- that is its whole purpose, SS11). `discovery/` imports
NOTHING from `evaluation/` anywhere -- enforced structurally (TEST 26,
an AST import scan mirroring Spec #001 TEST 10 / Spec #002 TEST 18).

## Configuration and versioning

Mirrors Spec #002's discipline (SS33/SS45): every tunable parameter
lives in `config/evaluation.yaml`, `config_version` is a SHA-256 hash of
its raw content. `evaluation_engine_version` is a separate, manually-
maintained constant in `engine.py` for the calculation logic itself.
Every `EvaluationRunRegistry` carries both, plus Discovery's own
`discovery_engine_version`/`discovery_config_version` (SS59-60).
