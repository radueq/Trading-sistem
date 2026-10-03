# Spec #002 -- Requirement -> Code -> Test Correspondence Matrix

**Status: background-agent output, partially spot-checked by Claude, NOT
independently verified by Radu.** Produced by a Claude subagent reading
`docs/Spec_002_Feature_Engine_Discovery_v1.0.md` section-by-section (all
50 sections) against `src/discovery/` and `tests/spec002/`. The agent ran
`python -m pytest tests/spec002/ -q` itself twice and reports **38
passed, 0 failed**.

**Revision note (2026-10-03):** Radu's correction on §48 (below) is
applied: the acceptance-evidence question for Spec #002 is resolved (see
`docs/contract_index.md`'s Spec #002 row and
`docs/evidence_spec002_acceptance_message.md`) -- §47/§48 no longer say
nobody recorded the acceptance; the only remaining item is optional
documentation housekeeping. The classification key from
`docs/contract_index.md` is now applied throughout: several rows below
originally read "PARTIAL" for a requirement fully satisfied by the code,
with the only real gap being a missing test -- those now read "MET (by
inspection)" with a separate **TEST-COVERAGE GAP** tag, per the same
correction Radu made on the Spec #001 document.

**Outcome-blindness verdict (the core discipline, checked explicitly):**
the agent found **no actual outcome-contamination** anywhere in
`src/discovery/` -- no forward returns, no alpha score, no
win-rate/expectancy/Sharpe/backtest field on any dataclass or in any
computation. Genuine, verified clean result (see Finding 1 for a
guardrail-robustness point, which is not itself a violation).

**Claude's own spot-check on 3 of the agent's highest-impact claims:**
1. `NormalizedFeatureObservation(` -- grep across all of `src/` and `tests/` returns **zero instantiations**. **Confirmed dead code.**
2. `bucket_key` (in `config/discovery.yaml:23`) -- grep confirms it is **read nowhere** in `src/` or `tests/`; the diversity selector hardcodes its bucket key instead. **Confirmed dead config.** Radu has endorsed this as meriting contractual analysis and a targeted reproduction, not a settled defect -- tagged **SUSPECTED ISSUE -- VERIFICATION PENDING** below, not DEMONSTRATED DEFECT.
3. `src/discovery/engine.py:257-259` extracts only `.value` from each normalized-feature series, discarding whatever richer status/point object it came from. **Confirmed the value-only extraction pattern the agent describes.** Same endorsement and tag as point 2 -- this is the mechanism behind Finding 2/Finding 6 below.

All three held up.

---

## Section-by-section table

| # | Requirement (paraphrase) | Code location | Test location | Status |
|---|---|---|---|---|
| 1 | OHLCV->Feature->State->Signature->Transition->Discovery->Candidates pipeline | `engine.py:137-327` | `test_01`, `test_14` (full pipeline), `test_04`-`test_12` (per-stage) | MET |
| 2 | Discovery is OUTCOME-BLIND; forbidden-input list | `models/entities.py:39-160` (no outcome fields anywhere) | `test_17` (AST scan), `test_13` | MET, no violation found [see Finding 1 -- a robustness point about the guard itself, not a violation of this row] |
| 3 | Feature/State/Transition kept as 3 separate concepts | `entities.py:39-46` (`FeatureObservation`, never instantiated), `80-88`, `61-77`, `111-138` | Indirectly via `test_11/12/20` | MET -- concepts stay distinct in the real output type actually used [**SUSPECTED ISSUE -- VERIFICATION PENDING**, same root cause as Finding 2: the literal per-feature dataclasses the spec sketches are dead code] |
| 4 | No combinatorial state-graph enumeration; X(t)/dX/d2X | `states/transitions.py:23-44` | `test_12` (reproduces spec's own worked example exactly) | MET |
| 5 | Every feature output carries security_id/as_of/timeframe/name/value | Schema defined but 0 instantiations; equivalent info present in aggregate form | No test builds/validates the literal record | MET (equivalent info present in the real output) [**SUSPECTED ISSUE -- VERIFICATION PENDING**, same as row 3/Finding 2] |
| 6 | 3-30 day horizon is not an exit rule; no outcomes computed | No outcome/exit code anywhere | `test_17` | MET (figure itself superseded by #003 -- already documented in `docs/contract_index.md`) |
| 7 | PIT-only data access; architectural test required | `engine.py:39` (only PIT import) | `test_18` (AST import scan) | MET |
| 8 | #001's QA/listing-status limitations remain hard gates | Zero references to `qa_pass`/`listing_status` anywhere in `src/discovery/` | No structural test enforces this | **MET (by inspection)** [TEST-COVERAGE GAP: no AST guard against a future regression] |
| 9 | Lane A Trend: full field list, no trend_score | `features/trend.py:17-38` (generic per-window computation, same formula for every window) | `test_04` hand-verifies 4 of ~9 fields explicitly | **MET (by inspection: the untested fields use the same generic per-window code path as the tested ones)** [TEST-COVERAGE GAP: the other ~5 fields are not individually hand-verified] |
| 10 | Lane B RS: benchmark-configurable, cross-sectional percentile | `features/relative_strength.py:20-32`; `engine.py:247-253`; `normalization/cross_sectional.py` (used throughout the real pipeline, exercised indirectly by every RS-bearing test) | `test_05` (63d only); `test_20` | **MET (by inspection, exercised indirectly throughout)** [TEST-COVERAGE GAP: `cross_sectional_percentile()` has no direct unit test of its own] |
| 11 | Lane C Volatility: ATR/BB-width/realized-vol, ATR != BBWidth | `features/volatility.py:19-68` | `test_06`, `test_07` (Wilder formula hand-verified) | MET -- spec-text ambiguity noted, not an implementation gap: the spec doesn't say whether "ATR_percentile" means percentile-of-ATR_14 or of-ATR_pct; code chose the latter, a defensible reading Radu should confirm |
| 12 | Lane D Volume: ADV/volume_ratio/percentile/RVOL | `features/volume.py:21-33` | `test_08` | MET |
| 13 | Lane E Momentum: ROC_5/10/20, delta/acceleration, no BUY/SELL | `features/momentum.py:14-26` (same generic per-window pattern as Lane A) | `test_09` -- ROC_10 only | **MET (by inspection, same generic-window reasoning as row 9)** [TEST-COVERAGE GAP: ROC_5/20 not individually verified] |
| 14 | Rolling percentile normalization (not z-score) | `normalization/rolling_percentile.py:28-52` | `test_03` (formula, ties, min_periods, missing input) | MET |
| 15 | TIME_SERIES vs CROSS_SECTIONAL distinction must survive into output | `entities.py:56` field never populated; real output is a bare dict | `test_22` doesn't check for a normalization-type tag | **SUSPECTED ISSUE -- VERIFICATION PENDING** -- see Finding 2 |
| 16 | State vocabulary + aliases; thresholds external | `config/states.yaml`; `states/mapper.py:19-34` | `test_11` (every bucket boundary) | MET |
| 17 | StateSignature retains underlying features, not just labels | `entities.py:80-88` (all fields required by the dataclass itself) | No dedicated test | **MET (structurally required, not merely conventional)** [TEST-COVERAGE GAP: not directly asserted by a test] |
| 18 | Transition: current/delta_1/delta_n/acceleration | `entities.py:61-69`; `states/transitions.py:23-44` | `test_12` | MET |
| 19 | Discovery flags extremeness/CS+TS/state-change/convergence/**lane contradictions**/persistence/accel-decel | `engine.py:198-311`; `candidate/convergence.py:54-99` | Same suite | Partially MET: extremeness/CS+TS/state-change/convergence/persistence/accel-decel all have real mechanisms. **SUSPECTED ISSUE -- VERIFICATION PENDING** for "contradictions between lanes" specifically -- see Finding 3 |
| 20 | Convergence: no global Alpha Score; active_lanes description | `candidate/convergence.py:24-28` | `test_13` | MET |
| 21 | Candidate reduction outcome-blind | `candidate/selector.py:1-70` | `test_15/16/17` | MET |
| 22 | Candidate Budget configurable, deterministic tie-break | `config/discovery.yaml:5-7`; `selector.py:18-24` | `test_15`, `test_14` | MET |
| 23 | Diversity: no trivial collapse, policy visible in config | `selector.py:45-70`; `config/discovery.yaml:17-23` | `test_16` | MET (no trivial collapse observed) [**SUSPECTED ISSUE -- VERIFICATION PENDING, Claude-verified `bucket_key` is dead config** -- see Finding 4] |
| 24 | No Alpha Score | `entities.py:141-160` (no such field) | `test_13`, `test_17` | MET |
| 25 | Rarity (state_frequency) descriptive only | `engine.py:270-288` (simple frequency arithmetic) | No unit test hand-verifies the arithmetic | **MET (by inspection)** [TEST-COVERAGE GAP] |
| 26 | Minimum sample support -> explicit SUFFICIENT/INSUFFICIENT | `candidate/convergence.py:43-51`; `config/discovery.yaml:15` (simple threshold comparison) | No test drives `sample_count` below the threshold | **MET (by inspection)** [TEST-COVERAGE GAP] |
| 27 | Output contract: full DiscoveryCandidate field list | `entities.py:141-160` (all fields present) | No single test validates the whole contract at once; subsets covered by `test_13`/`test_16`/`test_20` | **MET (by inspection, all fields present and exercised in parts)** [TEST-COVERAGE GAP: no one test validates the whole contract together] |
| 28 | Reason codes explainable, not recommendations | `candidate/reason_codes.py:11-20`; `convergence.py:54-99` (detection logic present for all 9 codes) | Only ONE assertion in the whole suite touches `reason_codes`, and it's negative | **MET (all 9 codes implemented)** [TEST-COVERAGE GAP for 8 of 9 -- see Finding 5; same STATUS_CONFLICT-style correction as Spec #001's audit] |
| 29 | Universe Eligibility: separate layer, configurable, market-cap floor | `eligibility/engine.py:1-56` (all branches implemented, including `MINIMUM_LIQUIDITY`/`EXCHANGE_ELIGIBILITY`) | `test_10` (direct, `MINIMUM_HISTORY`); `test_22` (indirect) | **MET (by inspection, all branches present)** [TEST-COVERAGE GAP: `MINIMUM_LIQUIDITY`/`EXCHANGE_ELIGIBILITY` branches never exercised by a test] |
| 30 | Missing data: explicit statuses, no silent forward-fill | `entities.py:22-26`; `normalization/rolling_percentile.py:28-52` | `test_03` (thorough at function level) | MET on no-forward-fill. **SUSPECTED ISSUE -- VERIFICATION PENDING**: per-feature status is discarded before the final output (same mechanism as Finding 2/6); `INVALID_INPUT` is never produced by any code path (an unreachable enum value -- may be intentional, needs Radu's read) |
| 31 | Split-adjusted approved; total_return EXPERIMENTAL | `engine.py:90-107` | `test_19` (AST attribute scan) | MET |
| 32 | Benchmark: same PIT/timeframe, explicit missing-data handling | `relative_strength.py:20-32`; `engine.py:213-215` | `test_20` | MET on PIT/timeframe identity. **SUSPECTED ISSUE -- VERIFICATION PENDING**: a missing benchmark date becomes `NaN` via a pandas merge rather than the explicit status machinery used elsewhere -- see Finding 10 |
| 33 | Configuration externalized; config_version on every output | `config/loader.py:18-47` (real SHA-256 hash, populated on output) | No test asserts `config_version` on actual output objects | **MET (by inspection: real hash mechanism, populated)** [TEST-COVERAGE GAP] |
| 34 | Determinism; no randomness without seed | No `random`/`np.random` anywhere (grep-verified) | `test_01`, `test_14` | MET |
| 35 | Storage: don't modify raw Data Foundation tables | No write/INSERT/UPDATE anywhere in `src/discovery/` | Supported indirectly by `test_18` | MET |
| 36 | 0 LLM tokens at runtime | Pure pandas/python | `test_21` | MET |
| 37 | Avoid 1-query-per-feature-per-ticker-per-day | `engine.py:213,219` -- exactly one PIT call per security/benchmark, confirmed by inspection | No test counts/mocks PIT calls to enforce this | **MET (by inspection)** [TEST-COVERAGE GAP: no test enforces the call count going forward] |
| 38 | Required Tests 1-20 | `test_01`-`test_20` all present | All pass (depth caveats noted above) | MET |
| 39 | >=3 controlled examples with "what this does NOT mean" disclaimer | `docs/spec002_examples.md` -- exactly 3 | Generated by a report script, not a pytest assertion | MET |
| 40 | Volume/telemetry report | `docs/spec002_volume_report.md` | Same report script | MET |
| 41 | No LLM at runtime (repeat) | Same as 36 | `test_21` | MET |
| 42 | Out-of-scope list (17 items) | Confirmed absent throughout (full manual review) | Only a subset (outcome terms, LLM imports) has a test | **MET (by inspection, confirmed absent)** [TEST-COVERAGE GAP for the untested subset: crypto, brokers, sentiment, etc.] |
| 43 | 4H/1H architecture-ready, not implemented now | `TIMEFRAME="1D"` constant; lane functions are timeframe-agnostic | N/A -- correctly not built | MET |
| 44 | Don't loosen filters to manufacture a trade-count target | No such feedback mechanism exists | N/A | **FUTURE / PROCEDURAL REQUIREMENT** -- a downstream/future-phase concept, not testable within Discovery's own boundaries as written |
| 45 | Versioning: no silent formula change | `config_version` is a real hash; `feature_engine_version`/`discovery_engine_version` are hardcoded strings with no enforcement tying them to actual formula changes | No test verifies version-bump discipline | **SUSPECTED ISSUE -- VERIFICATION PENDING** -- see Finding 8: the two engine-version strings have no mechanism (unlike `config_version`'s hash) tying them to real formula changes |
| 46 | Implementation Blocker Protocol | Procedural rule, not a runtime artifact | N/A | **FUTURE / PROCEDURAL REQUIREMENT** |
| 47 | Deliverables A-E | All 5 docs present and substantive | N/A | MET -- content complete. Formal acceptance evidence for #002 is now on record (`docs/contract_index.md`'s Spec #002 row, `docs/evidence_spec002_acceptance_message.md`); a dedicated `ACCEPTANCE.md`-style file remains optional housekeeping, not missing evidence, per Radu's own correction |
| 48 | Acceptance Gate (aggregate of technical criteria) | Aggregate of sections above | All underlying tests pass (38/38, verified live) | **MET -- every technical criterion has evidence, and the formal acceptance act is on record.** (Corrected 2026-10-03: this row previously said "nobody has recorded the formal acceptance act itself for #002." Radu's own acceptance message, verbatim, was located directly in this session's transcript and is now a standalone source document -- see row 47. The absence of a file literally named `ACCEPTANCE.md` does not mean the acceptance is unrecorded; it means only that #002, unlike #001/#003/#004, documents it via `contract_index.md` + the evidence file rather than its own dedicated file -- optional to change, not an open gap.) |
| 49 | Expected package structure | Matches spec's suggested tree exactly | `test_01`-`test_24` mirror it | MET |
| 50 | Final instruction summary | Aggregate of all sections | Aggregate | MET in aggregate. The items noted above are, by category: several TEST-COVERAGE GAPs (code correct by inspection, missing regression tests) and a handful of SUSPECTED ISSUES worth Radu's own contractual read (rows 3/5/15/23/30/32/45) -- none are demonstrated defects, and none block the aggregate MET here |

---

## Top findings

1. **[SUSPECTED ISSUE -- VERIFICATION PENDING, guard-robustness, no current violation]** The outcome-blindness scan is identifier-only. `test_17` scans AST identifiers, never string-literal constants. A future change storing a forbidden concept as a string value (e.g. `reason_codes.append("expected_win_rate")`) would silently pass. No violation exists today (verified by full manual read) -- this is about the guard's own coverage, not a finding against the code it guards.
2. **[SUSPECTED ISSUE -- VERIFICATION PENDING, Radu-endorsed for contractual analysis]** SS15: normalization-type doesn't survive into output (Claude-verified). `NormalizedFeatureObservation` (which would carry `normalization_type`) is never instantiated; the real output is a bare `dict[str, float]`. A downstream consumer can't tell `rs_percentile_cross_sectional` (CROSS_SECTIONAL) from `BB_width_percentile` (TIME_SERIES) without hardcoding that knowledge externally.
3. **[SUSPECTED ISSUE -- VERIFICATION PENDING]** SS19: "contradictions between lanes" has no reason code or detection mechanism anywhere, though the spec names this phenomenon specifically (e.g. TREND=VERY_HIGH with RELATIVE_STRENGTH=VERY_LOW simultaneously). Whether this is a required convergence category or an optional extension is Radu's contractual call, not something inspection alone settles.
4. **[SUSPECTED ISSUE -- VERIFICATION PENDING, Radu-endorsed for contractual analysis]** SS23: the diversity `bucket_key` is dead config (Claude-verified). Changing it in `discovery.yaml` to any of the spec's own suggested alternatives (`dominant_lane`, `transition_signature`) does nothing -- the selector hardcodes its bucket key.
5. **[TEST-COVERAGE GAP]** SS28: reason-code detection logic exists for all 9 codes (`convergence.py:54-99`), but only one assertion in the entire suite touches `reason_codes`, and it's negative. The gap is missing positive tests, not missing detection -- the same correction applied to Spec #001's `STATUS_CONFLICT` finding.
6. **[SUSPECTED ISSUE -- VERIFICATION PENDING, same root as Finding 2]** SS30: per-feature missing-data status is computed then discarded before the final output. Separately, `INVALID_INPUT` is never produced by any code path -- an unreachable enum value, possibly intentional, worth Radu's read rather than assumed dead-by-design.
7. **[TEST-COVERAGE GAP]** SS26/SS29: the sample-support and liquidity/exchange-eligibility branches exist in code (simple threshold comparisons) but are never exercised by a test driving the relevant values past their thresholds.
8. **[SUSPECTED ISSUE -- VERIFICATION PENDING]** SS45: `config_version` is a real hash tied to the actual config content; `feature_engine_version`/`discovery_engine_version` are plain strings with no mechanism tying them to the formulas they're meant to version. A formula change with a forgotten version bump would go uncaught.
9. **[TEST-COVERAGE GAP]** SS9/10/13: only one window per lane is hand-verified in a dedicated test, though each lane's remaining windows run through the same generic per-window code path -- by-inspection reasonable, not independently confirmed per window.
10. **[SUSPECTED ISSUE -- VERIFICATION PENDING]** SS32: a missing benchmark date becomes `NaN` via a pandas merge rather than going through the explicit `FeatureStatus` machinery used elsewhere in this same codebase -- a real asymmetry, whose practical consequence (whether downstream code handles the resulting NaN correctly) is not yet traced.
