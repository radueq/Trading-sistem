# Spec #002 -- Architecture Note

Feature Engine + Outcome-Blind Discovery Engine, Level 1 (Daily).
Depends on Spec #001 Accepted Baseline, commit `918f3f7`.

## Data flow

```
Spec #001 PIT layer (pit.access.get_price_series_as_of)
  -> Feature Engine (5 lanes, computed from one local in-memory series)
  -> TIME_SERIES normalization (rolling percentile, per security)
  -> [cross-sectional pass across the whole batch: CROSS_SECTIONAL RS percentile]
  -> State mapping (percentile -> label, per lane)
  -> Transitions (X, delta X, delta^2 X on each lane's driving percentile)
  -> Eligibility (Universe Eligibility, separate from Data QA)
  -> Convergence (active_lanes, descriptive_metrics, reason_codes -- no Alpha Score)
  -> Candidate Budget + diversity selection
  -> DiscoveryCandidate[]
```

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
`state_frequency`, `sample_count`, `support_status`) + `reason_codes` -- **never** a
single combined score (Spec #002 SS20/SS24, enforced structurally by TEST 13/17).
`state_frequency` is the CROSS_SECTIONAL rarity of a candidate's exact full
`lane_states` combination among *eligible* securities on that `as_of` (a documented
choice, distinct from the TIME_SERIES `persistence` metric).

`candidate/selector.py`'s budget selection is fully deterministic: ranked by
`(extremeness desc, active-lane-count desc, persistence desc, security_id asc)`,
with `security_id` as the explicit tie-breaker Spec #002 SS22 requires. Diversity
(SS23) is a round-robin over buckets keyed by each candidate's sorted `active_lanes`
tuple, iterated in a fixed lexicographic bucket order -- documented, not a hidden
heuristic.

## PIT enforcement

Every module under `src/discovery/` may reach Data Foundation **only** through
`data_foundation.pit.access` -- never `data_foundation.model.repository` or
`data_foundation.storage.db` directly (Spec #002 SS7). Enforced structurally by
TEST 18, an AST scan mirroring Spec #001's TEST 10. `run_discovery()` makes exactly
one PIT call per security (plus one for the benchmark), retrieving the full local
history in a single shot; every feature family is then computed from that same
in-memory series (Spec #002 SS37 -- never one query per feature per ticker per day).

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
