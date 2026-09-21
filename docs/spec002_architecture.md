# Spec #002 -- Architecture Note

Feature Engine + Outcome-Blind Discovery Engine, Level 1 (Daily).
Depends on Spec #001 Accepted Baseline, commit `918f3f7`.

## Data flow

```
Spec #001 PIT layer (pit.access.get_price_series_as_of)
  -> Feature Engine (5 lanes, computed from one local in-memory series)
  -> TIME_SERIES normalization (rolling percentile, per security)
  -> Eligibility (Universe Eligibility, separate from Data QA) -> eligible_ids
  -> [cross-sectional pass, ELIGIBLE SECURITIES ONLY: CROSS_SECTIONAL RS percentile]
  -> State mapping (percentile -> label, per lane)
  -> Transitions (X, delta X, delta^2 X on each lane's driving percentile)
  -> Convergence (active_lanes, descriptive_metrics, reason_codes -- no Alpha Score)
  -> Candidate Budget + diversity selection (a descriptive deterministic ranking)
  -> DiscoveryCandidate[]
```

**Ordering is load-bearing** (GPT Review #002 Round 1, PATCH #002-A, mandatory fix):
eligibility must run *before* the cross-sectional pass, not after. The first cut of
`run_discovery()` computed `rs_percentile_cross_sectional` over every security in
`security_ids` and only filtered to `eligible_ids` afterward -- so a security that
would never become a candidate (e.g. failing `minimum_price`) could still enter the
cross-sectional distribution and skew the RS percentile of securities that ARE
eligible. At real-data scale (thousands of ineligible penny/illiquid names), that
would have silently distorted which eligible securities look "notable." Fixed;
TEST 22 proves it (fails against the pre-patch ordering, passes against the fix).

`discovery.engine.run_discovery(conn, security_ids, as_of, benchmark_security_id, config)`
is the single entry point. Zero LLM calls anywhere in this path (Spec
#002 SS36/SS41) -- pure Python/pandas numerical computation.

## Package structure

```
src/discovery/
  models/entities.py        FeatureStatus, NormalizationType, SupportStatus,
                             FeatureObservation, NormalizedFeatureObservation,
                             TransitionEntry, TransitionVector, StateSignature,
                             EligibilityResult, DescriptiveMetrics, DiscoveryCandidate
  config/
    loader.py                DiscoveryConfig + config_version (hash of the 4 YAML files)
    features.yaml             window sizes -- TEST_CONFIG
    states.yaml                bucket thresholds + lane_drivers -- TEST_CONFIG
    discovery.yaml              budget/diversity/reason-code thresholds -- TEST_CONFIG
    eligibility.yaml             minimum floors -- TEST_CONFIG
  normalization/
    rolling_percentile.py       TIME_SERIES (mean-rank percentile, explicit min_periods)
    cross_sectional.py           CROSS_SECTIONAL (same formula, across securities)
  features/
    trend.py                    Lane A
    relative_strength.py         Lane B (needs a benchmark price series)
    volatility.py                 Lane C (ATR via Wilder, BB Width, realized vol)
    volume.py                     Lane D
    momentum.py                    Lane E
  states/
    mapper.py                    percentile -> label, lane_states, persistence
    transitions.py                 X(t) / delta_1 / delta_n / acceleration
  eligibility/
    engine.py                    Universe Eligibility (separate from Data QA)
  candidate/
    reason_codes.py               ReasonCode enum
    convergence.py                  active_lanes, extremeness, reason code rules
    selector.py                     deterministic budget + diversity selection
  engine.py                       run_discovery() -- THE single entry point
tests/spec002/
  fixtures/synthetic_universe.py  TEST_CONFIG synthetic securities + benchmark
  test_01..21_*.py                 the 21 required tests (20 from SS38 + no-LLM)
  generate_report_artifacts.py       produces docs/spec002_examples.md + volume report
```

## Feature formulas (exact, for audit)

- **Trend**: `return_Nd = close[t]/close[t-N] - 1`; `sma_N` = simple moving average;
  `distance_smaN = close[t]/sma_N[t] - 1`; `slope_smaN = (sma_N[t]/sma_N[t-w] - 1) / w`
  (a *percentage*-based slope -- on a linear absolute price path it shrinks as price
  grows, since a fixed absolute increment is a smaller percentage at a higher base).
- **Relative Strength**: `relative_return_Nd = ticker_return_Nd - benchmark_return_Nd`
  (a simple difference, not a ratio).
- **Volatility**: ATR uses the classic **Wilder recursive smoothing** (seeded by a
  plain mean of the first `atr_window` true ranges, then `atr[i] = (atr[i-1]*(w-1) +
  tr[i]) / w`) -- chosen over an EWM approximation specifically so a small synthetic
  OHLC sequence stays hand-verifiable. `BB_width_20 = (upper - lower) / sma`, standard
  2-stdev bands. `realized_volatility_20` = rolling stdev of daily log returns.
  Feature names (`ATR_14`, `BB_width_20`) are fixed literal labels matching Spec #002's
  own naming, independent of the configured window value (see `features/volatility.py`).
- **Volume**: `ADV_20` = trailing 20-day average volume **excluding** the current day
  (a reference baseline that doesn't include the day being measured).
  `RVOL_20` and `volume_ratio_20` are the **same** ratio (`volume / ADV_20`) under two
  names -- Spec #002 SS12 lists both without distinguishing them; inventing an
  arbitrary difference the spec doesn't specify would be worse than being explicit
  they're aliases.
- **Momentum**: `ROC_n = close[t]/close[t-n] - 1`; `momentum_delta`/`momentum_acceleration`
  are the first/second difference of the config-selected driving ROC window
  (default `ROC_10`) -- X(t), Delta X(t), Delta^2 X(t) per Spec #002 SS4/SS13.

## Normalization

- **TIME_SERIES** (`normalization/rolling_percentile.py`): mean-rank percentile --
  `(count_strictly_less + 0.5*count_equal) / window_size` over the trailing `window`
  observations. `window` defaults to 252, `min_periods` defaults to `window` (no
  partial-window statistic unless explicitly configured smaller -- Spec #002 SS14/SS30).
- **CROSS_SECTIONAL** (`normalization/cross_sectional.py`): same formula, applied
  across securities at one `as_of` instead of across time. Used for exactly one
  feature at Level 1: `rs_percentile_cross_sectional` (relative_return_63d ranked
  against the eligible universe -- Spec #002 SS15's own example).

Six features get a TIME_SERIES percentile companion (`return_63d`, `BB_width_20`,
`ATR_pct`, `realized_volatility_20`, `volume`, `ROC_10`) -- covering every
`_percentile` feature Spec #002 explicitly names, plus this build's own driver
choices for the trend/momentum lanes (Spec #002 doesn't name one for those two).

## State representation

`states/mapper.py`'s `lane_drivers` (in `config/states.yaml`) names exactly one
normalized feature per lane that drives its label:

| Lane | Driver | Normalization |
|---|---|---|
| trend | `return_63d_percentile` | TIME_SERIES |
| relative_strength | `rs_percentile_cross_sectional` | CROSS_SECTIONAL |
| volatility | `BB_width_percentile` | TIME_SERIES (compression vocabulary) |
| volume | `volume_percentile` | TIME_SERIES |
| momentum | `ROC_10_percentile` | TIME_SERIES |

This is a documented Level 1 design choice (Spec #002 doesn't name a driver for
every lane), external in config rather than hardcoded, per Spec #002 SS16/SS17.

**Persistence** (`states/mapper.compute_persistence`) is computed only over the four
TIME_SERIES-driven lanes' historical combination -- `relative_strength` is excluded
from the historical persistence/transition computation, since its CROSS_SECTIONAL
driver would need the whole eligible universe recomputed at every historical date to
do properly, which is out of scope for Level 1 (see Known Limitations).

## Convergence and candidate reduction

`candidate/convergence.py` produces `active_lanes` (lanes whose label isn't
NEUTRAL/NORMAL) + `descriptive_metrics` (`extremeness`, `persistence`,
`state_frequency`, `sample_count`, `support_status`) + `reason_codes` -- **never an
Alpha Score, and never anything calibrated against outcomes** (Spec #002 SS20/SS24,
enforced structurally by TEST 13/17). `extremeness` is the *max absolute distance
from the 0.5 midpoint* across a candidate's active lane-driving percentiles (not a
weighted sum across lanes), so it never lets one lane's magnitude compensate for
another's the way a blended score would. `state_frequency` is the CROSS_SECTIONAL
rarity of a candidate's exact full `lane_states` combination among *eligible*
securities on that `as_of` (a documented choice, distinct from the TIME_SERIES
`persistence` metric).

**`candidate/selector.py`'s budget selection IS a ranking** -- a **descriptive
deterministic ranking for candidate-budget allocation**, precisely because turning
an unbounded universe into a bounded, LLM-consumable candidate set requires some
ordering mechanism (Spec #002 SS21/SS22). It is not, and must never become, an
Alpha Score: the sort key `(extremeness desc, active-lane-count desc, persistence
desc, security_id asc)` uses only descriptive/statistical properties available at
`as_of`, `security_id` is the explicit tie-breaker Spec #002 SS22 requires, and
nothing in this ranking is or may ever be calibrated against forward
returns/profitability -- doing so would silently end Discovery's outcome-blindness
even though no single field would be named "alpha_score" (GPT Review #002 Round 1).
Diversity (SS23) is a round-robin over buckets keyed by each candidate's sorted
`active_lanes` tuple, iterated in a fixed lexicographic bucket order -- documented,
not a hidden heuristic.

## PIT enforcement

Every module under `src/discovery/` may reach Data Foundation **only** through
`data_foundation.pit.access` -- never `data_foundation.model.repository` or
`data_foundation.storage.db` directly (Spec #002 SS7). Enforced structurally by
TEST 18, an AST scan mirroring Spec #001's TEST 10. `run_discovery()` makes exactly
one PIT call per security (plus one for the benchmark), retrieving the full local
history in a single shot; every feature family is then computed from that same
in-memory series (Spec #002 SS37 -- never one query per feature per ticker per day).

The `as_of` bound itself is enforced entirely by `pit.access.get_price_series_as_of()`
(Spec #001) -- Feature Engine deliberately does **not** re-filter by date; duplicating
that rule here would create two sources of truth for the same guarantee, and
`pit.access` is the single authority (TEST 2 already exercises this end-to-end: bars
dated after an earlier `as_of` don't change that `as_of`'s output). `engine._assert_no_future_leakage()`
is a cheap fail-fast invariant on top -- `assert bars[-1].date <= as_of` -- added per
GPT Review #002 Round 1 (recommended, not a filtering mechanism): it exists only to
raise loudly if the PIT gateway's contract is ever violated, not to enforce
PIT-safety itself.

## Configuration and versioning

Every tunable parameter lives in `config/*.yaml`, never hardcoded in calculation
logic (Spec #002 SS33). `config_version` (`config/loader.py`) is a SHA-256 hash of
the four files' raw content -- any edit to a threshold or window automatically
changes the version, so a silent formula/parameter change is structurally
impossible to hide (Spec #002 SS45). `feature_engine_version` and
`discovery_engine_version` are separate, manually-maintained constants in
`engine.py` for the calculation logic itself (bumped when a formula changes, not
just a config value). Every `DiscoveryCandidate` carries all three.

## Universe Eligibility vs Data QA

Kept explicitly separate (Spec #002 SS29, carrying forward Spec #001 SS2):
`eligibility/engine.py` decides whether the system *wants* to consider an
instrument at all (minimum price/history/liquidity, exchange allowlist), never
whether an observation is trustworthy (QA) or how noteworthy its current state is
(Discovery). `market_cap_floor` is always reported `PENDING_DATA` -- no PIT market
cap field exists anywhere in the Spec #001 schema, never fabricated.

## Adding 4H/1H later (not built now)

Every `FeatureObservation`/`NormalizedFeatureObservation`/`DiscoveryCandidate`
already carries an explicit `timeframe` field (currently always `"1D"`). No
calculation engine assumes internally that Daily is the only timeframe -- lane
`compute()` functions operate on a generic OHLCV DataFrame, `run_discovery()`
doesn't hardcode a bar frequency anywhere. Adding 4H/1H later means: a new PIT
retrieval path for intraday bars (Spec #001 concern) plus passing `timeframe`
through to the existing lane functions -- not a redesign of this module.
