# Spec #002 -- Known Limitations

Explicit per Spec #002 SS47C (mirrors Spec #001 SS27E: don't hide
limitations to declare the module "done"). None of these block Level 1
acceptance; they are the honest boundaries of what this build can claim.

## Hard gates inherited from Spec #001 (Spec #002 SS8)

**No result from this module may be labelled research-grade until both
of these are resolved.** Not silently fixed here -- Spec #002 explicitly
forbids that.

- **QA knowledge-time**: `qa_results.qa_pass` is not yet guaranteed
  knowledge-time immutable (Spec #001's own Known Limitations, GPT
  Review #001, 2026-09-21). Feature Engine at Level 1 does **not**
  consume `qa_pass` at all -- no filtering, no gating, nothing reads
  `pit.access.get_data(...).qa_pass_by_date` anywhere in
  `src/discovery/`. This is the safest posture given the acknowledged
  gap: not building on top of a foundation that isn't research-grade
  yet, rather than integrating QA now and inheriting its immutability
  risk silently.
- **Listing status carry-forward**: `pit.access.get_listing_status_as_of()`
  can return `None` (no applicable status) rather than carrying the
  previous status forward when a transition's `available_at` hasn't
  been reached yet (Spec #001's own Known Limitations). Eligibility at
  Level 1 does **not** filter on listing status at all (see below) --
  deliberately, to avoid building a filtering rule on an acknowledged-
  unreliable field.

## Eligibility

- **`EXCHANGE_ELIGIBILITY` cannot be evaluated at Level 1.**
  `pit.access` (Spec #001) doesn't expose `security_master.primary_exchange`
  anywhere in its public interface -- `run_discovery()` always passes
  `primary_exchange=None` to `evaluate_eligibility()`. Rather than read
  `data_foundation.model.repository` directly (forbidden, SS7) or
  unilaterally extend Spec #001's PIT gateway, the rule is simply
  disabled by default (`allowed_exchanges: null` in `eligibility.yaml`).
  **This is exactly the kind of missing interface Radu asked to be
  flagged rather than silently worked around** -- extending
  `pit.access.get_data()` to expose `primary_exchange` (a static,
  non-time-varying field, so no PIT-correctness concern) is a small,
  well-scoped Spec #001 addition if/when exchange filtering is needed.
- **No listing-status-based eligibility rule** (e.g. excluding delisted
  securities) -- deliberately, tied to the listing-status carry-forward
  gate above. Spec #002's own example eligibility dimensions (price,
  history, liquidity, exchange, market cap) don't include it either.
- **`market_cap_floor` is always `PENDING_DATA`.** No PIT market cap
  field exists anywhere in the Spec #001 schema; never fabricated.
  Eligibility proceeds on the other dimensions regardless of
  `eligibility.yaml`'s `market_cap_floor` value.

## Feature computation

- **Volume is now split-adjusted -- CLOSED (PATCH #001-C, Radu's
  correction, 2026-09-21).** Previously a BLOCKER before any real-data
  backtesting (elevated per GPT Review #002 Round 1): `raw_volume`
  (unadjusted) was paired with `split_adjusted_close` (adjusted), so a
  split produced a mechanical level shift in volume that could look
  like a real spike -- a spurious `RVOL_20`/`volume_percentile` reading
  and a false `VOLUME_ANOMALY` reason code near that boundary. Fixed in
  Spec #001, not here: `data_foundation.pit.access.PITPriceBar` now
  exposes `split_adjusted_volume = raw_volume / split_factor` (the
  same PIT-safe `split_factor` as price, opposite direction), and
  `discovery.engine._price_series_to_df()` consumes it instead of
  `raw_volume`. See `docs/architecture.md` and TEST 16 (Spec #001,
  formula/continuity/round-trip) and TEST 23 (Spec #002, proves a split
  alone no longer produces a false `VOLUME_ANOMALY`, both split
  directions). No lane formulas or thresholds changed.
- **`relative_strength`'s historical persistence/transition is not
  computed.** `states/mapper.compute_persistence()` and the
  `TransitionVector` cover only the four TIME_SERIES-driven lanes
  (trend, volatility, volume, momentum). `relative_strength`'s driver
  (`rs_percentile_cross_sectional`) is CROSS_SECTIONAL and would need
  the whole eligible universe recomputed at every historical date to
  measure properly -- an expensive full-universe-across-history
  computation, out of scope for Level 1. `relative_strength`'s current
  `as_of` state IS computed correctly (via the cross-sectional pass);
  only its historical run-length/delta are the gap.
- **`ATR_14` / `BB_width_20` are fixed literal names**, independent of
  the configured `atr_window`/`bb_window` value (matching Spec #002's
  own naming convention of one named feature per volatility measure,
  not a list like the return windows). Reconfiguring the window changes
  the *values*, not the output key -- documented in `features/volatility.py`
  and exercised deliberately in TEST 7 (a small window, for a
  hand-verifiable series, still labeled `ATR_14`).
- **`RVOL_20` and `volume_ratio_20` are literal aliases** of the same
  ratio (`volume / ADV_20`). Spec #002 SS12 lists both names in its
  minimum feature list without distinguishing them; inventing an
  arbitrary difference the spec doesn't specify would be worse than
  being explicit they're the same computation under two names.
- **Lane driver choices for `trend` (`return_63d_percentile`) and
  `momentum` (`ROC_10_percentile`)** are this Level 1 build's own design
  choice -- Spec #002 names a driver for volatility/volume/relative_strength
  implicitly (their own `_percentile` features) but not for trend/momentum.
  Externally configurable (`config/states.yaml`'s `lane_drivers`), not
  claimed to be the only valid choice.
- **`slope_smaN` is a percentage-based slope**
  (`(sma[t]/sma[t-w] - 1) / w`), not an absolute one. On a security with
  a constant *absolute* daily price change, this slope shrinks over
  time as the price base grows -- a real, correct property of a
  percentage-based measure, not a bug (see TEST 4's comments).

## Universe / performance

- **No automatic universe discovery.** `run_discovery()` takes an
  explicit `security_ids` list; nothing in this module decides *which*
  securities exist to run Discovery over -- that's a caller/orchestration
  concern (mirroring Spec #001's `model/ingestion.py` not doing identity
  resolution automatically either).
- **Cross-sectional computations require the whole batch at once.**
  `rs_percentile_cross_sectional` and `state_frequency` are computed in
  a single pass over all securities passed to one `run_discovery()` call
  -- there's no incremental/streaming update if a new security is added
  later; the whole batch is recomputed. Fine at Level 1 synthetic scale
  (~0.03s/security, see `docs/spec002_volume_report.md`); a real
  concern only at much larger universe sizes, deferred per Spec #002
  SS37 ("informational in Level 1, not an acceptance blocker").
- **No live yfinance data** -- same sandbox network restriction as Spec
  #001 (see its Known Limitations). All Spec #002 tests run against
  fully synthetic fixtures (`tests/spec002/fixtures/synthetic_universe.py`),
  explicitly labeled TEST_CONFIG, not claimed to resemble real market
  behavior.

## GPT Review #002 Round 1 (PATCH #002-A, 2026-09-2x)

- **Fixed -- cross-sectional RS was computed before eligibility
  filtering.** The first cut of `run_discovery()` computed
  `rs_percentile_cross_sectional` over every security passed in, then
  filtered to `eligible_ids` afterward -- so an ineligible security
  (e.g. failing `minimum_price`) with an extreme `relative_return_63d`
  could still skew the RS percentile of securities that ARE eligible.
  Reordered: eligibility now runs before the cross-sectional pass, which
  is scoped to `eligible_ids` only. TEST 22 proves it (fails against the
  pre-patch ordering, passes against the fix) -- see
  `docs/spec002_architecture.md`'s Data flow section for the corrected
  pipeline order.
- **Frozen convention, not changed -- rolling percentile includes the
  current observation in its own reference window.** GPT's review noted
  a conceptually cleaner alternative (compare today's value only against
  the *prior* 252 observations, excluding itself) and confirmed the
  current convention is not look-ahead leakage (today's value is known
  at `as_of` either way) and the numerical difference at window=252 is
  small. Per GPT's explicit recommendation, **not changed** without an
  empirical reason -- documented here as a deliberately frozen
  convention ahead of any backtesting work, so a future change (if ever
  made) is a conscious, reviewed decision, not a silent drift.
- **Documentation-only fixes**: `docs/spec002_architecture.md`'s
  Convergence section no longer claims the candidate selector produces
  "never a single combined score" -- it IS a ranking (a **descriptive
  deterministic ranking for candidate-budget allocation**), just never
  an Alpha Score and never calibrated against outcomes; a standing rule
  against ever optimizing selector weights/ordering against forward
  returns is now stated explicitly. `docs/spec002_examples.md`'s intro
  now states plainly that the market data is synthetic (only the
  pipeline computation is "real"), removing the earlier ambiguous
  wording. The unadjusted-volume-around-splits gap (Feature computation,
  above) is elevated from a passive note to an explicit blocker before
  real-data backtesting.
- **Added, non-blocker**: `engine._assert_no_future_leakage()`, a
  fail-fast invariant (`assert bars[-1].date <= as_of`) on every PIT
  call -- not a filtering mechanism (that stays entirely `pit.access`'s
  job), just a loud failure if that contract is ever violated.

## PATCH #001-C (Radu's correction, 2026-09-21)

- **Volume/split mismatch closed.** See "Volume is now split-adjusted"
  above (Feature computation) -- fixed in Spec #001's `pit/access.py`,
  consumed by a one-line change in `discovery.engine._price_series_to_df()`.
  No changes to the 5 lanes, Candidate Budget, extremeness formula, or
  general architecture -- scope was strictly the volume field plus its
  one consumer. TEST 23 added.

## Test coverage

- All 23 required tests (the 20 named in Spec #002 SS38 plus a
  structural no-LLM-imports check, SS41, plus TEST 22 and TEST 23 from
  GPT Review #002 Round 1 / PATCH #001-C) pass -- see
  `docs/spec002_test_report.md`. None are `PENDING`; Level 1's
  synthetic universe is sufficient to exercise every required property.
