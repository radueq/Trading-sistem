# Spec #002 -- Test Report

Run: `python3 -m pytest tests/spec002/ -v` -- Python 3.11.15, pytest 9.1.1,
pandas 3.0.6, numpy 2.4.6, PyYAML 6.0.1.

Result: **34 passed, 0 failed, 0 pending** (across the 21 required tests --
several have multiple focused sub-tests). Full repo (Spec #001 + Spec #002):
**57 passed, 1 skipped (Spec #001 TEST 8, PENDING_LEVEL_2_DATA, unaffected)**.

| # | Test | File | Result | Notes |
|---|------|------|--------|-------|
| 1 | Feature determinism | `test_01_feature_determinism.py` | **PASS** | Same universe/as_of/config run twice through `run_discovery()` -> byte-identical `DiscoveryCandidate` lists. |
| 2 | No future candle leakage | `test_02_no_future_candle_leakage.py` | **PASS** | `run_discovery(as_of=X)` snapshot taken, then later-dated candles ingested for the same securities, then repeated at the same `as_of=X` -> identical output. Discovery-level counterpart to Spec #001 TEST 9. |
| 3 | Rolling percentile | `test_03_rolling_percentile.py` | **PASS** (5 sub-tests) | Known series -> hand-verified mean-rank percentile (incl. ties, `min_periods` override, missing input, `min_periods > window` rejected). |
| 4 | Trend calculations | `test_04_trend_calculations.py` | **PASS** (2 sub-tests) | Linear synthetic series -> `return_20d/63d`, `sma_20`, `distance_sma20` match hand computation exactly; `slope_sma20` sign/shrinkage verified against the percentage-slope formula. |
| 5 | Relative Strength | `test_05_relative_strength.py` | **PASS** (2 sub-tests) | Ticker vs benchmark synthetic series -> `relative_return_63d` matches `ticker_return - benchmark_return` exactly; zero against itself as its own benchmark. |
| 6 | BB Width compression | `test_06_bb_width_compression.py` | **PASS** | Constructed wide-then-tight price series -> `BB_width_20` falls during the compressed period. |
| 7 | ATR | `test_07_atr.py` | **PASS** | Hand-picked 8-bar OHLC sequence -> `ATR_14` (window overridden to 5 for a short hand computation) matches the classic Wilder recursive formula exactly. |
| 8 | Volume anomaly | `test_08_volume_anomaly.py` | **PASS** | 10x volume spike on the last bar -> `RVOL_20` > 8; a normal day elsewhere stays near 1.0; `volume_ratio_20` confirmed identical to `RVOL_20` (documented alias). |
| 9 | Momentum delta/acceleration | `test_09_momentum_delta_acceleration.py` | **PASS** | Quadratic synthetic price path -> `ROC_10`, `momentum_delta`, `momentum_acceleration` all match hand computation exactly; acceleration confirmed positive. |
| 10 | Missing history | `test_10_missing_history.py` | **PASS** (2 sub-tests) | 100-of-252 observations -> explicit `INSUFFICIENT_HISTORY`, no silent calculation; the Level 1 `INSUFFICIENT_HISTORY` fixture security (30 days) fails `MINIMUM_HISTORY` eligibility and produces zero candidates. |
| 11 | State mapping | `test_11_state_mapping.py` | **PASS** | Known percentile values -> expected `VERY_LOW..VERY_HIGH` and compression-vocabulary labels at every bucket boundary. |
| 12 | Transition representation | `test_12_transition_representation.py` | **PASS** (2 sub-tests) | Reproduces Spec #002's own worked example exactly (`bb_width_percentile=0.08, delta_5=+0.07, acceleration=+0.03`); insufficient-history case returns `None` deltas rather than a fabricated value. |
| 13 | Convergence without Alpha Score | `test_13_convergence_no_alpha_score.py` | **PASS** (2 sub-tests) | Multi-lane `StateSignature` -> correct `active_lanes`; `DiscoveryCandidate`'s dataclass fields confirmed to contain no `alpha_score`/`score`/`win_rate`/`expectancy`/`sharpe`. |
| 14 | Candidate determinism | `test_14_candidate_determinism.py` | **PASS** | Same universe run twice -> identical candidate list **and** identical order. |
| 15 | Candidate Budget | `test_15_candidate_budget.py` | **PASS** (2 sub-tests) | 31-security eligible universe against a 20-candidate budget -> exactly 20 returned (budget genuinely binds); budget-disabled config returns everything. |
| 16 | Diversity | `test_16_diversity.py` | **PASS** (2 sub-tests) | Budget-selected output spans more than one distinct `state_signature` (no collapse); diversity-disabled config falls back to plain ranking. |
| 17 | No outcome fields | `test_17_no_outcome_fields.py` | **PASS** | AST identifier scan (function/variable/field/attribute/kwarg names, not docstring prose) across all of `src/discovery/` -> zero forbidden outcome-vocabulary identifiers. |
| 18 | PIT gateway enforcement | `test_18_pit_gateway_enforcement.py` | **PASS** (2 sub-tests) | AST import scan mirroring Spec #001 TEST 10 -> no module under `src/discovery/` imports `data_foundation.model.repository` or `data_foundation.storage.db`; `engine.py` confirmed to import `data_foundation.pit.access`. |
| 19 | Total-return prohibition | `test_19_total_return_prohibition.py` | **PASS** | AST attribute-access scan of `_price_series_to_df` -> `total_return_adjusted_close` never accessed; `split_adjusted_close` is. |
| 20 | Benchmark configuration | `test_20_benchmark_configuration.py` | **PASS** (2 sub-tests) | No benchmark ticker string hardcoded in `features/relative_strength.py`; swapping the benchmark security (config/data, no code change) changes RS output, and RS against itself as its own benchmark is exactly 0. |
| 21 | No LLM runtime imports | `test_21_no_llm_imports.py` | **PASS** | AST import scan -> no `anthropic`/`openai`/`google.generativeai`/`cohere`/`langchain` import anywhere under `src/discovery/`. Not numbered in SS38's list; required by SS41's hard rule. |

## How to reproduce

```bash
pip install -r requirements.txt
python3 -m pytest tests/spec002/ -v
# regenerate docs/spec002_examples.md and docs/spec002_volume_report.md:
PYTHONPATH=src:tests python3 -m spec002.generate_report_artifacts
```

No network access is required or attempted -- every test runs against the
fully synthetic, deterministic fixtures in `tests/spec002/fixtures/synthetic_universe.py`
(numpy `default_rng` with fixed seeds) or small hand-constructed series built
directly in the test file, per test.
