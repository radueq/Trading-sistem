# Spec #003 v1.1 -- Requirement -> Code -> Test Correspondence Matrix

**Status: background-agent output, partially spot-checked by Claude, NOT
independently verified by Radu.** Produced by a Claude subagent tasked
with reading `docs/Spec_003_Outcome_Aware_Evaluation_v1.1.md`
section-by-section (all 75 sections, including Radu's second-message
amendments) and citing exact `src/`/`tests/` evidence for each --
conservative by instruction. The agent ran `python -m pytest
tests/spec003/ -q` itself and reports **60 passed**.

**Claude's own spot-check on 3 of the agent's highest-impact claims, done
directly against the source:**
1. `src/evaluation/engine.py:110-111` (`_missingness_from_outcomes`): `eligible_observations=raw_n, raw_observations=raw_n` -- **confirmed identical**, both literally set to the same value.
2. `src/evaluation/engine.py:79-83` (`_collect_observations`) calls `compute_discovery_observations()` once per session date; that function (`src/discovery/engine.py:218-219`) calls `pit.get_price_series_as_of` per security on every invocation. **Confirmed: an O(sessions x universe) PIT re-fetch, not "one fetch per security."**
3. `family_test_count` -- grep across all of `src/` and `tests/` returns **zero hits**. **Confirmed absent.**

All three held up. The rest of the table was not independently
re-verified line-by-line by Claude.

---

## Section-by-section table

| # | Requirement (paraphrase) | Code location | Test location | Status |
|---|---|---|---|---|
| 1 | Pipeline: PIT+Discovery obs -> Outcome Engine -> Episode Engine -> Statistical Eval -> Evidence Profile | `src/evaluation/engine.py:1-29` | End-to-end via `test_31`, `test_32` | MET |
| 2 | Fast-Swing domain, horizons=[1,2,3,5,10] bars | `config/evaluation.yaml:15-17` | `test_01`, `test_34` | MET |
| 3 | Contract = timeframe + horizon_bars, not "1 bar=1 day" | `outcomes/forward_returns.py:9-16,43-105` | `test_02_bar_horizon_semantics.py` (calendar-gap proof) | MET |
| 4 | No hardcoded day-coupled field names | `models/entities.py:42-67` | `test_03` (AST field-name scan) | MET |
| 5 | Keep Daily now; 4H is separate future work | `discovery/engine.py:62`, `evaluation.yaml:10` | N/A (nothing to violate) | MET |
| 6 | Report IMPLEMENTATION BLOCKER before any #001/#002 contract change | Spec file lines 1417-1557 (Radu's §74A exchange); commit `136bf94` | `tests/spec002/test_24_pre_budget_observation_isolation.py` | MET |
| 7 | Designed for 4H but not implemented; no future redesign needed | No 4H code anywhere (grep-verified) | `test_40` treats "4H" as an ordinary string | MET |
| 8 | Live-validation practicality must never mutate outcome-blind Discovery | Static config; no Evaluation->Discovery path | `test_26_discovery_cannot_import_evaluation.py` | MET |
| 9 | Edge vs opportunity density kept separate | `statistics/opportunity.py` isolated, never imported by comparison/multiple_testing | `test_24_opportunity_density_arithmetic.py` | MET |
| 10 | Discovery remains permanently outcome-blind | `discovery/models/entities.py:1-14` | `test_26` (AST import scan) | MET |
| 11 | Evaluation is the authorized outcome-aware zone | `evaluation/models/entities.py:1-11,42-67` | Whole suite | MET |
| 12 | Exclusively Development; Locked OOS never used for debugging/thresholds | `outcomes/forward_returns.py:52-58,86-89` | `test_06`, `test_27` | MET |
| 13 | Real calendar boundaries `null`; tests use synthetic dates | `evaluation.yaml:66-70`; `engine.py:349-351` | All engine tests supply synthetic windows | MET |
| 14 | Outcome cannot cross development boundary (Radu's example) | `forward_returns.py:86-89` | `test_06` (same dates/horizon as Radu's example) | MET |
| 15 | `R = P(t+h)/P(t)-1`, split_adjusted_close | `forward_returns.py:94` | `test_01` | MET |
| 16 | `total_return_adjusted_close` forbidden | N/A | `test_30` (AST scan, zero hits) | MET |
| 17 | Research return != executable trade P&L | Docstring + absence of fill code | Satisfied by absence, not independently testable | MET |
| 18 | `AR = R - R_benchmark` | `outcomes/benchmark.py:46-47` | `test_04` | MET |
| 19 | Benchmark aligned by date, `MISSING_BENCHMARK` if absent | `benchmark.py:18-24,36-44` | `test_05` | MET |
| 20 | `ForwardOutcome` entity, minimum fields | `models/entities.py:42-67` | `test_01`, `test_04` | MET |
| 21 | 5 outcome statuses; never silently drop | `models/entities.py:19-24` | `test_06/07/08/38`; `test_32` | MET |
| 22 | Raw unit = security x as_of x signature, not independent samples | `observations/signatures.py:24-25`, `engine.py:380-383` | `test_09/10/11` | MET |
| 23 | Candidate Budget must NOT define the statistical dataset | `engine.py:38` (imports pre-budget function, never `run_discovery`) | `test_33`; `tests/spec002/test_24` | MET |
| 24 | Pre-budget `DiscoveryObservation`, minimum fields | `discovery/models/entities.py:112-138` | `test_33`, `tests/spec002/test_24` | PARTIAL -- no explicit `eligibility_status` field (implicit: only eligible rows ever constructed); spec's single `engine_version` is split into two version fields. Radu's §74A approval addressed only the type-name split, not this field list. |
| 25 | `EvaluationSignature` = pure AND of existing #002 fields, never a new indicator | `observations/signatures.py:14-21` | **No test exercises a compound (2+ condition) signature** -- every test signature uses exactly one condition | PARTIAL -- mechanism correct, AND-combination logic untested |
| 26 | Signature Set frozen (`signature_set_id`) | `registry/signatures.py:37-40` | `test_28` | MET |
| 27 | Signature provenance, minimum fields | `models/entities.py:83-97` | `test_28/29/37/40` | PARTIAL -- spec's `definition`/`source_fields` aren't explicit fields (implicitly covered by `lane_conditions`, not a traceable list) |
| 28 | Two modes: EXPLORATORY vs FORMAL_DEVELOPMENT | `models/entities.py:27-29`; `engine.py:310-347,395-413` | FORMAL_DEVELOPMENT thoroughly tested; **zero tests run EXPLORATORY end-to-end** | PARTIAL |
| 29 | Consecutive observations != N independent experiments | `observations/episodes.py:1-23` | `test_09/10/11` (mirrors Radu's AAPL example) | MET |
| 30 | Episode defaults: max_gap_bars=1, representative=FIRST | `episodes.py:37-68`; `evaluation.yaml:23-25` | `test_09`, `test_10` | MET |
| 31 | Report both RAW_OBSERVATIONS and EPISODE_DEDUPLICATED views | Only the raw view's *count* is reported; full stats/CI run only on EPISODE_DEDUPLICATED (`engine.py:152-166`) | `test_11` | PARTIAL -- ambiguous whether spec intended a full dual-stats report |
| 32 | Overlapping forward windows possible; no naive t-test | No `ttest`/`scipy.stats` anywhere (grep-verified) | `comparison.py` (permutation), `bootstrap.py` (TIME_BLOCK) | MET |
| 33 | Baseline = eligible-universe distribution (amended: TEMPORALLY_STRATIFIED) + benchmark-relative | `baseline/universe.py:1-15,87-119` | `test_12` | MET |
| 34 | Baseline must NOT come from Candidate Budget | `engine.py:90-103,361-364` (built from full `all_obs`) | `test_33` | MET |
| 35 | Metrics per signature x horizon | `models/entities.py:130-142`; `statistics/descriptive.py:14-30` | `test_13`, `test_14` | MET |
| 36 | Missingness report, counts must reconcile | `models/entities.py:194-203`; `engine.py:106-117` | `test_32` | PARTIAL -- **Claude-verified**: `eligible_observations` and `raw_observations` are always identical (both = the signature's own raw match count), not the full eligible-universe population vs. this signature's matches -- see Top Finding 1 |
| 37 | Opportunity-density metrics excluded from significance calc | `statistics/opportunity.py:1-43` | `test_24` | MET |
| 38 | Effect size + fixed standardized-effect formula | `engine.py:120-123,217`; `baseline/universe.py:132-137` | **No test hand-verifies the formula's arithmetic or the UNDEFINED_ZERO_SCALE branch** | PARTIAL |
| 39 | Bootstrap CIs (mean, relative, vs. baseline), episode-aware resampling | `engine.py:158-205`; `statistics/bootstrap.py:32-154` | Primitives well-tested; **no test asserts a real EvidenceProfile's CI fields are actually populated** | PARTIAL |
| 40 | Statistical comparison method (permutation, documented) | `statistics/comparison.py:1-113` | `test_20` | MET |
| 41 | Security concentration diagnostic | `statistics/concentration.py:13-19` | `test_17` (matches spec's own 80/52 example) | MET |
| 42 | Temporal concentration reported | `statistics/stability.py:17-36` | `test_23` | MET |
| 43 | Stability bins (3, early/mid/late), no "stability score" | `baseline/universe.py:30-61`; `statistics/stability.py` | `test_23` | MET |
| 44 | Multiple testing mandatory for FORMAL_DEVELOPMENT; incl. `family_test_count`; default BH-FDR | `models/entities.py:145-164`; `statistics/multiple_testing.py` | `test_21`, `test_36` | PARTIAL -- **Claude-verified**: `family_test_count` (explicitly named in SS44) is not a field anywhere; must be reconstructed externally |
| 45 | Family = timeframe+horizon_bars+outcome_type+evaluation_run | `statistics/multiple_testing.py:23-24` | `test_22` | MET |
| 46 | Minimum support (30 episodes / 10 securities) -> INSUFFICIENT_SUPPORT | `evaluation.yaml:19-21`; `engine.py:267-278` | `test_15`, `test_16` | MET |
| 47 | Thresholds must not be lowered to manufacture results | Defaults unchanged in config | Policy statement, checkable only via the artifact itself | MET |
| 48 | No automatic sign-flip into a "short strategy" claim | No such logic exists (grep-verified) | Satisfied by absence | MET |
| 49 | No Alpha/Evaluation Score | N/A | `test_25` (AST identifier scan) | MET |
| 50 | `EvidenceProfile` structure | `models/entities.py:225-247` | `test_31`, `test_34` | MET |
| 51 | No verdict output; only SUFFICIENT/INSUFFICIENT_SUPPORT | `models/entities.py:37-39` | **No automated test scans for forbidden verdict words** (GOOD/BAD/TRADE/WINNER/EDGE_CONFIRMED) -- manually verified clean today, unprotected against regression | PARTIAL |
| 52 | Holding-horizon decay profile (1/2/3/5/10) | `engine.py:430-436` | `test_34` | MET |
| 53 | Do not pick a "winning" exit horizon | Returns tuples only, no winner field | `test_34` explicitly asserts no winner attribute | MET |
| 54 | MAE/MFE out of scope | N/A | Grep-verified absence | MET |
| 55 | Transaction costs out of scope | N/A | Grep-verified absence | MET |
| 56 | Slippage/spread out of scope | N/A | Grep-verified absence | MET |
| 57 | Missing future bars -> INSUFFICIENT_FUTURE_DATA, never 0/dropped | `forward_returns.py:81-83` | `test_08` | MET |
| 58 | Delistings: don't fabricate economic delisting return | Same generic "data ends" mechanism as §57 | No dedicated delisting-scenario test | PARTIAL -- plausible via the same mechanism, but spec names it as a distinct concern with no distinct test |
| 59 | Evaluation Registry, minimum metadata | `models/entities.py:250-280`; `engine.py:415-426` | `test_31` | MET |
| 60 | Reproducibility: identical inputs -> identical output | `registry/runs.py:14-17`; `registry/signatures.py:37-40` | `test_31` | MET |
| 61 | Python only, 0 LLM tokens | N/A | `test_35` | MET |
| 62 | Performance: one PIT fetch/security, vectorized, benchmark reuse | Outcome side (`engine.py:359,86-87`) honors it; **observation-collection side does not** | Not caught by any test (only unit-level primitives tested) | PARTIAL -- **Claude-verified**, see Top Finding 2 |
| 63 | Suggested config structure | `config/evaluation.yaml` (matches + Radu-approved additions) | Loaded and exercised by every engine test | MET |
| 64 | Future 4H: same engine, different config | Architecture never branches on timeframe value | `test_40` uses "4H" only as a mismatch/failure case | PARTIAL -- no test demonstrates an actual passing 4H run |
| 65 | Daily+4H compound signature would need its own pre-registration | N/A (4H doesn't exist yet) | Vacuously satisfied | MET |
| 66 | 35 required tests | `test_01`-`test_35` all present | 60 passed total (35 + 5 later regression + multi-assertion files) | MET |
| 67 | >=4 controlled examples (A-D) | `generate_report_artifacts.py:49-160` (real computation) | **Not a pytest test** -- script's own docstring says so; no CI assertion on the examples' qualitative claims | PARTIAL |
| 68 | Performance report | `generate_report_artifacts.py:163-260` (real `run_evaluation()`) | Same as §67 -- standalone, not CI-enforced | PARTIAL |
| 69 | Package structure per suggestion | `src/evaluation/{models,outcomes,observations,baseline,statistics,config,registry}/` | Whole suite | MET |
| 70 | 7 deliverable docs | All 7 `docs/spec003_*.md` present | N/A | MET |
| 71 | 12 hard-FAIL conditions must never occur | Rollup of sections already verified above | Same tests as those sections | MET |
| 72 | Explicit OUT-OF-SCOPE list (17 items) | Grep confirms zero references anywhere in `src/evaluation` | N/A | MET |
| 73 | Success = leakage-free measurement, not "found a strategy" | Consistent with §49/§51 | Same as §49/§51 | MET |
| 74 | Claude's answers to A-E as modified by Radu | Cross-referenced to §23/24, §39/40, §33/34, §64/65 | Same as those sections | MET, inheriting the PARTIALs already flagged there |
| 75 | Final process instructions (confirm, no #004/4H inside #003) | Git history strictly orders `8182e52`->...->`266cc6f` before `6082215`; no 4H code exists | N/A | MET |

---

## Top findings (highest-impact gaps/ambiguities)

1. **SS36's `MissingnessReport` conflates two distinct counts (Claude-verified).** `engine.py:110-111` sets `eligible_observations = raw_observations = raw_n` (the signature's own raw match count), never the size of the full eligible-universe population the signature was drawn from. `test_32:29` asserts this equality as a feature, baking the collapsed semantics into the regression test. A reviewer cannot tell "3 matches out of 500 eligible" from "3 out of 5" -- both report identically.
2. **SS62's own anti-pattern is exactly what the observation-collection stage does (Claude-verified).** The spec literally says "avoid: 1 query x observation x horizon." `_collect_observations` calls `compute_discovery_observations()` once per session date, and that function re-fetches each security's full PIT history from scratch every call -- an O(sessions x universe) re-fetch. (The outcome-computation half correctly fetches once per security and reuses it.) At real research scale this could make a FORMAL_DEVELOPMENT run computationally infeasible.
3. **SS28 EXPLORATORY mode is implemented but never exercised end-to-end.** All engine-integration tests run FORMAL_DEVELOPMENT only. A refactor that silently breaks EXPLORATORY (e.g. accidentally enforcing the PRE_REGISTERED gate there) would stay green.
4. **SS25's own primary example (a compound signature) is never tested.** Every test signature uses exactly one condition; the AND-combination logic across 2+ conditions has zero coverage.
5. **SS38's standardized-effect formula has zero unit test with a known hand-computed number**, despite being the Radu-approved statistic the whole significance story rests on.
6. **SS39: bootstrap CI wiring at the `EvidenceProfile` level is unverified** -- the bootstrap primitive is well tested in isolation, but no test asserts a real profile's CI fields are populated/sane.
7. **SS44's `family_test_count` field, explicitly required by the spec, does not exist anywhere (Claude-verified).** A downstream consumer must reconstruct it by scanning all profiles for a matching `family_id`.
8. **SS24/SS27 field lists don't literally match the spec** (`eligibility_status`, `source_fields` absent, functionally superseded but not literally present) -- Radu's own §74A approval addressed only the type-name split, not this.
9. **SS67/SS68 controlled examples and performance report run outside pytest entirely.** A regression that breaks Example A's decay curve or Example D's multiple-testing trap would not fail CI -- the deliverable docs would quietly go stale.
10. **SS51 has no regression guard for forbidden verdict words**, unlike SS49's score-word scanner. Manually clean today, unprotected going forward.

**Core-discipline check (explicitly requested, no violations found):** Development/Locked-OOS separation, no post-hoc labeling, BH-FDR, and the one-way Discovery/Evaluation dependency all have direct structural tests and no violating code path was found. The issues above are about completeness of guardrails, not active violations of these four disciplines.
