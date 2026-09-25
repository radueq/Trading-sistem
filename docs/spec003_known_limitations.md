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
- **The permutation test (raw significance) does not fully model
  temporal/cross-sectional dependence**, unlike the TIME_BLOCK bootstrap
  used for confidence intervals. A block-permutation variant (preserving
  contiguous time blocks the way the bootstrap does) is a natural v2
  refinement if the concentration/stability diagnostics ever show it's
  needed -- not built speculatively now (Spec #003 SS47's own instruction
  not to over-engineer ahead of demonstrated need).
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

## Test coverage

- All 35 required tests (Spec #003 SS66) pass -- see
  `docs/spec003_test_report.md`. None are `PENDING`; the tiny synthetic
  universe plus hand-constructed unit fixtures are sufficient to exercise
  every required property.
