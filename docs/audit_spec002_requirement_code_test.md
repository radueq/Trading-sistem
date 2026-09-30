# Spec #002 -- Requirement -> Code -> Test Correspondence Matrix

**Status: background-agent output, partially spot-checked by Claude, NOT
independently verified by Radu.** Produced by a Claude subagent reading
`docs/Spec_002_Feature_Engine_Discovery_v1.0.md` section-by-section (all
50 sections) against `src/discovery/` and `tests/spec002/`. The agent ran
`python -m pytest tests/spec002/ -q` itself twice and reports **38
passed, 0 failed**.

**Outcome-blindness verdict (the core discipline, checked explicitly):**
the agent found **no actual outcome-contamination** anywhere in
`src/discovery/` -- no forward returns, no alpha score, no
win-rate/expectancy/Sharpe/backtest field on any dataclass or in any
computation. Genuine, verified clean result (see Finding 1 for the one
guardrail blind spot, which is not itself a violation).

**Claude's own spot-check on 3 of the agent's highest-impact claims:**
1. `NormalizedFeatureObservation(` -- grep across all of `src/` and `tests/` returns **zero instantiations**. **Confirmed dead code.**
2. `bucket_key` (in `config/discovery.yaml:23`) -- grep confirms it is **read nowhere** in `src/` or `tests/`; the diversity selector hardcodes its bucket key instead. **Confirmed dead config.**
3. `src/discovery/engine.py:257-259` extracts only `.value` from each normalized-feature series, discarding whatever richer status/point object it came from. **Confirmed the value-only extraction pattern the agent describes.**

All three held up.

---

## Section-by-section table

| # | Requirement (paraphrase) | Code location | Test location | Status |
|---|---|---|---|---|
| 1 | OHLCV->Feature->State->Signature->Transition->Discovery->Candidates pipeline | `engine.py:137-327` | `test_01`, `test_14` (full pipeline), `test_04`-`test_12` (per-stage) | MET |
| 2 | Discovery is OUTCOME-BLIND; forbidden-input list | `models/entities.py:39-160` (no outcome fields anywhere) | `test_17` (AST scan), `test_13` | MET (see Finding 1 -- guardrail blind spot, not a violation) |
| 3 | Feature/State/Transition kept as 3 separate concepts | `entities.py:39-46` (`FeatureObservation`, never instantiated), `80-88`, `61-77`, `111-138` | Indirectly via `test_11/12/20` | PARTIAL -- concepts stay distinct in the real output type, but the literal per-feature dataclasses the spec sketches are dead code |
| 4 | No combinatorial state-graph enumeration; X(t)/dX/d2X | `states/transitions.py:23-44` | `test_12` (reproduces spec's own worked example exactly) | MET |
| 5 | Every feature output carries security_id/as_of/timeframe/name/value | Schema defined but 0 instantiations; equivalent info present in aggregate form | No test builds/validates the literal record | PARTIAL |
| 6 | 3-30 day horizon is not an exit rule; no outcomes computed | No outcome/exit code anywhere | `test_17` | MET (figure itself superseded by #003 -- already documented) |
| 7 | PIT-only data access; architectural test required | `engine.py:39` (only PIT import) | `test_18` (AST import scan) | MET |
| 8 | #001's QA/listing-status limitations remain hard gates | Zero references to `qa_pass`/`listing_status` anywhere in `src/discovery/` | No structural test enforces this | PARTIAL -- correct by inspection, unenforced |
| 9 | Lane A Trend: full field list, no trend_score | `features/trend.py:17-38` | `test_04` hand-verifies only 4 of ~9 fields | PARTIAL |
| 10 | Lane B RS: benchmark-configurable, cross-sectional percentile | `features/relative_strength.py:20-32`; `engine.py:247-253` | `test_05` (63d only); `test_20` | PARTIAL -- `cross_sectional_percentile()` has zero direct unit test |
| 11 | Lane C Volatility: ATR/BB-width/realized-vol, ATR != BBWidth | `features/volatility.py:19-68` | `test_06`, `test_07` (Wilder formula hand-verified) | MET, with an ambiguity noted: spec doesn't say whether "ATR_percentile" means percentile-of-ATR_14 or of-ATR_pct; code chose the latter |
| 12 | Lane D Volume: ADV/volume_ratio/percentile/RVOL | `features/volume.py:21-33` | `test_08` | MET |
| 13 | Lane E Momentum: ROC_5/10/20, delta/acceleration, no BUY/SELL | `features/momentum.py:14-26` | `test_09` -- ROC_10 only | PARTIAL -- ROC_5/20 never individually verified |
| 14 | Rolling percentile normalization (not z-score) | `normalization/rolling_percentile.py:28-52` | `test_03` (formula, ties, min_periods, missing input) | MET |
| 15 | TIME_SERIES vs CROSS_SECTIONAL distinction must survive into output | `entities.py:56` field never populated; real output is a bare dict | `test_22` doesn't check for a normalization-type tag | GAP -- see Finding 2 |
| 16 | State vocabulary + aliases; thresholds external | `config/states.yaml`; `states/mapper.py:19-34` | `test_11` (every bucket boundary) | MET |
| 17 | StateSignature retains underlying features, not just labels | `entities.py:80-88` (all fields required) | No dedicated test | PARTIAL -- structurally guaranteed, not directly asserted |
| 18 | Transition: current/delta_1/delta_n/acceleration | `entities.py:61-69`; `states/transitions.py:23-44` | `test_12` | MET |
| 19 | Discovery flags extremeness/CS+TS/state-change/convergence/**lane contradictions**/persistence/accel-decel | `engine.py:198-311`; `candidate/convergence.py:54-99` | Same suite | PARTIAL/GAP -- "contradictions between lanes" has no reason code, detection, or test anywhere -- see Finding 3 |
| 20 | Convergence: no global Alpha Score; active_lanes description | `candidate/convergence.py:24-28` | `test_13` | MET |
| 21 | Candidate reduction outcome-blind | `candidate/selector.py:1-70` | `test_15/16/17` | MET |
| 22 | Candidate Budget configurable, deterministic tie-break | `config/discovery.yaml:5-7`; `selector.py:18-24` | `test_15`, `test_14` | MET |
| 23 | Diversity: no trivial collapse, policy visible in config | `selector.py:45-70`; `config/discovery.yaml:17-23` | `test_16` | PARTIAL -- **Claude-verified**: `bucket_key` is dead config, see Finding 4 |
| 24 | No Alpha Score | `entities.py:141-160` (no such field) | `test_13`, `test_17` | MET |
| 25 | Rarity (state_frequency) descriptive only | `engine.py:270-288` | No unit test hand-verifies the arithmetic | PARTIAL |
| 26 | Minimum sample support -> explicit SUFFICIENT/INSUFFICIENT | `candidate/convergence.py:43-51`; `config/discovery.yaml:15` | No test drives `sample_count` below the threshold | PARTIAL/GAP |
| 27 | Output contract: full DiscoveryCandidate field list | `entities.py:141-160` (all present) | No single test validates the whole contract at once | PARTIAL |
| 28 | Reason codes explainable, not recommendations | `candidate/reason_codes.py:11-20`; `convergence.py:54-99` | Only ONE assertion in the whole suite touches `reason_codes`, and it's negative | PARTIAL/GAP -- zero positive tests for any of the 9 codes |
| 29 | Universe Eligibility: separate layer, configurable, market-cap floor | `eligibility/engine.py:1-56` | `test_10` (direct); `test_22` (indirect, no assertion on failed_rules) | PARTIAL -- `MINIMUM_LIQUIDITY`/`EXCHANGE_ELIGIBILITY` branches have zero coverage |
| 30 | Missing data: explicit statuses, no silent forward-fill | `entities.py:22-26`; `normalization/rolling_percentile.py:28-52` | `test_03` (thorough at function level) | PARTIAL/GAP -- `INVALID_INPUT` never produced by any code path; per-feature status discarded before final output -- see Finding 6 |
| 31 | Split-adjusted approved; total_return EXPERIMENTAL | `engine.py:90-107` | `test_19` (AST attribute scan) | MET |
| 32 | Benchmark: same PIT/timeframe, explicit missing-data handling | `relative_strength.py:20-32`; `engine.py:213-215` | `test_20` | PARTIAL -- a missing benchmark date silently becomes NaN via pandas merge, not an explicit status |
| 33 | Configuration externalized; config_version on every output | `config/loader.py:18-47` (real SHA-256 hash) | No test asserts `config_version` on actual output objects | PARTIAL |
| 34 | Determinism; no randomness without seed | No `random`/`np.random` anywhere (grep-verified) | `test_01`, `test_14` | MET |
| 35 | Storage: don't modify raw Data Foundation tables | No write/INSERT/UPDATE anywhere in `src/discovery/` | Supported indirectly by `test_18` | MET |
| 36 | 0 LLM tokens at runtime | Pure pandas/python | `test_21` | MET |
| 37 | Avoid 1-query-per-feature-per-ticker-per-day | Exactly one PIT call per security/benchmark | No test counts/mocks PIT calls to enforce this | PARTIAL |
| 38 | Required Tests 1-20 | `test_01`-`test_20` all present | All pass (depth caveats noted above) | MET |
| 39 | >=3 controlled examples with "what this does NOT mean" disclaimer | `docs/spec002_examples.md` -- exactly 3 | Generated by a report script, not a pytest assertion | MET |
| 40 | Volume/telemetry report | `docs/spec002_volume_report.md` | Same report script | MET |
| 41 | No LLM at runtime (repeat) | Same as 36 | `test_21` | MET |
| 42 | Out-of-scope list (17 items) | Confirmed absent throughout (full manual review) | Only a subset (outcome terms, LLM imports) has a test; the rest (crypto, brokers, sentiment, etc.) has none | PARTIAL |
| 43 | 4H/1H architecture-ready, not implemented now | `TIMEFRAME="1D"` constant; lane functions are timeframe-agnostic | N/A -- correctly not built | MET |
| 44 | Don't loosen filters to manufacture a trade-count target | No such feedback mechanism exists | N/A | AMBIGUOUS -- a downstream/future-phase concept, not testable within Discovery's own boundaries as written |
| 45 | Versioning: no silent formula change | `config_version` is a real hash; `feature_engine_version`/`discovery_engine_version` are hardcoded strings with no enforcement tying them to actual formula changes | No test verifies version-bump discipline | PARTIAL -- see Finding 8 |
| 46 | Implementation Blocker Protocol | Procedural rule, not a runtime artifact | N/A | AMBIGUOUS -- assessable only from process history, not current source |
| 47 | Deliverables A-E | All 5 docs present and substantive | N/A | PARTIAL -- content is MET, but per `contract_index.md`, #002 has no dedicated acceptance-record equivalent |
| 48 | Acceptance Gate (aggregate of technical criteria) | Aggregate of sections above | All underlying tests pass (38/38, verified live) | PARTIAL -- every technical criterion has evidence, but nobody has recorded the formal acceptance act itself for #002 |
| 49 | Expected package structure | Matches spec's suggested tree exactly | `test_01`-`test_24` mirror it | MET |
| 50 | Final instruction summary | Aggregate of all sections | Aggregate | MET in aggregate, subject to the PARTIAL/GAP items above |

---

## Top findings

1. **[HIGH PRIORITY -- guardrail blind spot, no current violation] The outcome-blindness scan is identifier-only.** `test_17` scans AST identifiers, never string-literal constants. A future change storing a forbidden concept as a string value (e.g. `reason_codes.append("expected_win_rate")`) would silently pass. No violation exists today (verified by full manual read), but this class of regression wouldn't be caught.
2. **SS15: normalization-type doesn't survive into output (Claude-verified).** `NormalizedFeatureObservation` (which would carry `normalization_type`) is never instantiated; the real output is a bare `dict[str, float]`. A downstream consumer can't tell `rs_percentile_cross_sectional` (CROSS_SECTIONAL) from `BB_width_percentile` (TIME_SERIES) without hardcoding that knowledge externally.
3. **SS19: "contradictions between lanes" is entirely unimplemented.** No reason code represents lane divergence (e.g. TREND=VERY_HIGH with RELATIVE_STRENGTH=VERY_LOW simultaneously) even though the spec names this phenomenon specifically.
4. **SS23: the diversity `bucket_key` is dead config (Claude-verified).** Changing it in `discovery.yaml` to any of the spec's own suggested alternatives (`dominant_lane`, `transition_signature`) does nothing -- the selector hardcodes its bucket key.
5. **SS28: reason codes have almost no test coverage.** Exactly one assertion in the entire 24-test suite touches `reason_codes`, and it's negative. Disabling e.g. `MOMENTUM_ACCELERATION` via a threshold change would leave the full suite green.
6. **SS30: per-feature missing-data status is computed then discarded (Claude-verified pattern).** A security passing eligibility but under the feature engine's own `min_periods` floor gets every percentile-derived feature silently `None`, indistinguishable from a genuinely unremarkable security. `INVALID_INPUT` is fully dead code.
7. **SS26/SS29: untested eligibility/support-status branches.** No test drives sample count below the minimum-support threshold, nor exercises the liquidity/exchange-eligibility branches.
8. **SS45: code-formula versioning is unenforced.** `config_version` is a real hash; `feature_engine_version`/`discovery_engine_version` are just strings nobody is forced to bump when a formula changes.
9. **SS9/10/13: only one window per lane is hand-verified**, even though each lane requires a full set of windows (3 return windows, 3 SMAs, 5 distance/slope fields for Trend; ROC_5/10/20 for Momentum).
10. **SS32: benchmark missing-data has no explicit status** -- silently becomes NaN via a pandas merge rather than a distinguishable status like the rest of the missing-data machinery uses.
