# Spec #003 v1.1 -- Known Limitations

Explicit per the same discipline Spec #001 SS27E / Spec #002 SS47C
established (don't hide limitations to declare the module "done"). None
of these block Level 1 acceptance; they are the honest boundaries of
what this build can claim.

## Hard gates inherited from Spec #001/#002

Same two hard gates as Spec #002 (QA knowledge-time, listing-status
carry-forward) apply here too, one level further removed: Evaluation
consumes Discovery's observations, and Discovery itself doesn't consume
`qa_pass` or filter on listing status (see
`docs/spec002_known_limitations.md`). Not re-litigated here, not
silently fixed.

## Statistical method scope (V1, documented deliberately)

- **Only `relative_return` is formally significance-tested.**
  `absolute_outcome` (raw forward_return) is fully reported -- descriptive
  stats AND its own bootstrap CI -- but does not get its own BH-FDR
  family/adjusted_p. Rationale: raw absolute returns conflate market beta
  with idiosyncratic signal (in a bull market almost everything has a
  positive raw return, which isn't "edge"); testing both absolute AND
  relative formally would also double the multiple-testing burden for
  limited benefit at Level 1. `OUTCOME_TYPE = "relative_return"` in
  `evaluation/engine.py` is the single constant this decision lives in.
- **The permutation test is stratified by temporal bin (PATCH #003-A),
  but not by finer-grained dependence within a bin.** It now compares
  against the SAME `TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE` pools/weights
  as the point estimate and CI (fixed in PATCH #003-A -- see
  `docs/spec003_architecture.md`), which closes the "different baseline
  for the effect vs the p-value" gap GPT Review #003 Round 1 flagged. It
  still does not model dependence WITHIN one bin (e.g. two securities in
  the same bin moving together for reasons unrelated to the signature).
  A full two-way clustered permutation is a natural v2 refinement if the
  concentration/stability diagnostics ever show it's needed -- not built
  speculatively now (Spec #003 SS47's own instruction not to
  over-engineer ahead of demonstrated need).
- **TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE's point estimate is a
  weighted AVERAGE OF PER-BIN statistics**, not a true pooled weighted
  quantile. For the mean this is exact; for the median it is a
  documented approximation (Radu's own words: "apoi agregam strata" --
  aggregate the strata). A proper weighted-quantile pool across the
  combined stratified sample is a valid v2 refinement, not built here.
- **Two-way (security x time-block) clustered bootstrap is not
  implemented.** V1 uses TIME_BLOCK clustering alone (Radu's Sec.74B/D
  amendment) specifically because it's the mechanism that catches the
  failure mode explicitly flagged (a market-wide shock hitting many
  securities' episodes the same week) -- security-level clustering is
  reported separately as a diagnostic (`concentration.py`) rather than
  folded into the resampling scheme. A combined two-way scheme is a
  natural v2 addition if the diagnostics ever show residual
  security-concentration risk the time-block scheme alone doesn't catch.
- **`minimum_episode_count: 30` / `minimum_unique_securities: 10`
  (config `support`) are Level 1 engineering defaults, not validated
  thresholds** -- same posture as Spec #002's own eligibility floors.
  Per Radu's explicit instruction (Spec #003 v1.1 SS47), never lowered
  to manufacture more "significant" results faster; more opportunities
  must come from a larger universe / shorter holding horizon / real
  signal density, not weaker statistical standards.
- **Terminology: the bootstrap is a FIXED/non-overlapping block bootstrap
  with resampling, not a "moving block bootstrap."** `time_block_bootstrap_
  replicates()` partitions the real session calendar into contiguous,
  non-overlapping blocks of `block_length_bars` sessions and resamples
  WHICH blocks are drawn (with replacement); it does not slide a
  fixed-width window across the calendar (that would be the strict
  "moving block bootstrap" of Kunsch 1989). Flagged by GPT Review #003
  Final as a documentation-only correction -- no code or behavior change,
  recorded here so the method is never mis-cited in future research
  writeups.
- **Signature and baseline bootstrap replicates are drawn separately,
  then paired via `zip()` for `diff_replicates`** (`evaluation/engine.py`,
  `_evaluate_signature_horizon()`) -- each is resampled from its own
  TIME_BLOCK draw independently, not through the SAME drawn blocks. This
  is acceptable for Level 1 (synthetic data, no real-money claims), but
  before these CIs are used to support a research-grade/real-money
  decision, GPT Review #003 Final asked for this to be revisited as a
  **joint/paired time-block resampling**: draw one set of blocks per
  bootstrap iteration and apply it to both the signature's and the
  baseline's dated values, so `diff_replicates` preserves their common
  market/regime covariance instead of pairing two independently-resampled
  series. Not built now -- deferred until a Level 2/3 data provider is
  available and real-money-grade claims are actually being made.

## Performance (informational, not an acceptance blocker -- mirrors Spec #002 SS37)

- **O(sessions x universe) Discovery recomputation.** `run_evaluation()`
  calls `compute_discovery_observations()` once per session across the
  whole Development window -- there is no incremental/cached Discovery
  pass. At `tests/spec003/fixtures/tiny_universe.py` scale (3 securities,
  26 sessions) this is ~1s (see `docs/spec003_performance_report.md`);
  a real research-scale universe/date-range (thousands of securities x
  years of sessions) would need either a much larger time budget or an
  incremental/cached Discovery layer -- not built here, deferred exactly
  as Spec #002 deferred its own analogous cross-sectional-recomputation
  cost.
- **`tests/spec003/fixtures/tiny_universe.py` is deliberately smaller**
  than Spec #002's own 32-security/320-day `synthetic_universe.py` --
  sized for a per-session Evaluation sweep across a whole Development
  window (expensive), not a single-as_of Discovery query (cheap). Both
  fixtures are TEST_CONFIG, neither claims to resemble real market scale.

## Data

- **No live yfinance data** -- same sandbox network restriction as Spec
  #001/#002. All Spec #003 tests and examples run against fully
  synthetic fixtures or hand-constructed series, explicitly labeled
  TEST_CONFIG.
- **Real calendar boundaries (`research_period.development_start/end`,
  `locked_oos_start/end`) are deliberately left `null`** in
  `config/evaluation.yaml` (Spec #003 SS13) -- not hardcoded until a
  research-grade data provider is available. Every test/example supplies
  its own explicit window.
- **Delistings/survivorship**: same posture as Spec #001/#002 -- Level 1
  does not fabricate an economic delisting return; `INSUFFICIENT_FUTURE_DATA`
  is the honest status when a security's history simply ends.

## Out of scope (Spec #003 SS72, not silently included)

MAE/MFE, transaction costs, slippage/spread, executable entries,
next-bar fills, exit strategy, stop loss, sizing, portfolio construction,
walk-forward, Locked-OOS evaluation itself, 4H/1H data ingestion. All
deferred to the Backtesting/Risk-Exit specs this one deliberately does
not reach into.

## PATCH #003-A (GPT Review #003 Round 1, 2026-09-2x)

Six findings against commit `8182e52`, all fixed -- see
`docs/spec003_architecture.md` for full detail on each:

1. **Fixed -- BH-FDR key collision across horizons.**
   `benjamini_hochberg()` returned `{signature_id: ...}`; the same
   signature tested at 5 horizons meant later horizons silently
   overwrote earlier ones, and `run_evaluation()` applied results by
   `signature_id` alone. Now keyed by the full `(signature_id, timeframe,
   horizon_bars, outcome_type, evaluation_run_id)` tuple. TEST 36.
2. **Fixed -- TIME_BLOCK bootstrap now blocks real session dates, not
   row counts.** The original chunked sorted `(date, value)` pairs by
   position, so same-day cross-security observations could split across
   blocks -- exactly the common-market-shock structure TIME_BLOCK
   clustering was chosen to preserve. Now groups by date first, blocks
   over the session-date sequence.
3. **Fixed -- FORMAL_DEVELOPMENT now hard-rejects a non-frozen
   signature.** `run_evaluation()` errors before any PIT work if a
   signature isn't `PRE_REGISTERED` + `created_before_outcome_evaluation
   =True`; the Signature Set fingerprint now includes those two fields
   plus Discovery's own engine/config versions, so a definition quietly
   changing provenance changes `signature_set_id` too. TEST 37.
4. **Fixed -- permutation test now matches the stratified baseline.**
   Previously compared the signature against the raw, unstratified
   baseline pool while the point estimate/CI used
   `TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE` -- two different hypotheses
   behind one reported effect. `stratified_permutation_p_value` now uses
   the identical per-bin pools and weights.
5. **Fixed -- support/concentration now gate on the population actually
   tested.** `SupportInfo.valid_episode_n` (VALID relative outcomes)
   drives `support_status`, not the raw total episode count
   (`episode_n`, kept for reconciliation). `concentration` is computed
   over the same valid population.
6. **Fixed -- entry bar must match `observation_as_of` exactly.** The
   prior "latest bar at or before" lookup could silently predate the
   observation date (a halt/gap), while benchmark alignment requires an
   exact match -- mixing the two could compare a security return and a
   benchmark return measured from different dates. Now `INVALID_INPUT`
   when no bar exists exactly on `observation_as_of`. TEST 38.

No changes to the 5 feature lanes (Spec #002, untouched), Candidate
Budget, the robust standardized-effect formula, or the general
architecture -- scope was strictly these 6 items, per Radu's own
instruction.

## PATCH #003-B (GPT Review #003 Round 2, 2026-09-2x)

One residual finding on the PATCH #003-A TIME_BLOCK fix, plus one
guard GPT flagged during provenance verification -- both fixed:

1. **Fixed -- TIME_BLOCK bootstrap now blocks the REAL session
   calendar, not the dates present in the signature's own values.**
   PATCH #003-A correctly kept same-day cross-security values together,
   but still built blocks over whichever dates happened to have a value
   -- for a rare signature, those dates can be scattered across months
   with no real adjacency between them. `time_block_bootstrap_replicates()`
   now takes the run's real `session_dates` (the benchmark's own bar
   dates within Development) as an explicit parameter; blocks are built
   over that calendar, and a session with no value contributes nothing
   when its block is drawn (normal, not an error). TEST 39.
2. **Fixed -- FORMAL_DEVELOPMENT now rejects a provenance mismatch, not
   just a fingerprint difference.** The Signature Set fingerprint
   (PATCH #003-A) already makes a provenance change produce a different
   `signature_set_id`, but nothing stopped a signature pre-registered
   under one Discovery config/engine/timeframe from being RUN against a
   different one. `run_evaluation()` now hard-checks, per signature:
   `timeframe`, `discovery_engine_version`, and
   `discovery_config_version` all match the actual run. TEST 40.

No changes to the other 5 PATCH #003-A findings, the 5 feature lanes,
Candidate Budget, the robust standardized-effect formula, or the
general architecture.

## GPT Review #003 -- Final verdict

**SPEC #003 v1.1 -- ACCEPTED at commit `d889049`.** No PATCH #003-C was
requested. Two items were explicitly kept here as registry notes rather
than acted on: the bootstrap terminology correction and the joint/paired
time-block resampling revisit, both documented above under "Statistical
method scope." Spec #001 (`aa56bb5`) + Spec #002 (`4f36708` + patches) +
Spec #003 (`d889049`) now form the project's accepted baseline.

## Test coverage

- All 35 required tests (Spec #003 SS66) plus 5 PATCH #003-A/B
  regression tests (TEST 36-40) pass -- see `docs/spec003_test_report.md`.
  None are `PENDING`; the tiny synthetic universe plus hand-constructed unit
  fixtures are sufficient to exercise every required property.
