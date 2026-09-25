# Spec #003 v1.1 -- Test Report

Run: `PYTHONPATH=src:tests python3 -m pytest tests/spec003/ -v` -- Python
3.11.15, pytest 9.1.1, pandas 3.0.6, numpy 2.4.6, PyYAML 6.0.1.

Result: **60 passed, 0 failed, 0 pending** (across the 35 required tests
plus TEST 36-40, added by PATCH #003-A/B per GPT Review #003 Rounds 1-2
-- several have multiple focused sub-tests). Full repo (Spec #001 +
Spec #002 + Spec #003): **125 passed, 1 skipped (Spec #001 TEST 8,
PENDING_LEVEL_2_DATA, unaffected)**.

Updated 2026-09-2x -- PATCH #003-B (GPT Review #003 Round 2) fixed the
one residual finding from Round 1: TIME_BLOCK bootstrap blocked the
dates present in the signature's own values (not the real trading
calendar), which understates block structure for a rare/sparse
signature. Also added a FORMAL_DEVELOPMENT provenance guard (timeframe/
discovery_engine_version/discovery_config_version must match the actual
run, not just differ in the Signature Set fingerprint). TEST 39-40
added. See `docs/spec003_known_limitations.md`'s PATCH #003-B section.

Prior round -- PATCH #003-A (GPT Review #003 Round 1 on commit
`8182e52`) fixed 6 findings: BH-FDR key collision across horizons,
row-count-based (not real session-date) TIME_BLOCK bootstrap blocks,
missing FORMAL_DEVELOPMENT enforcement of frozen/pre-registered
signatures, a permutation test comparing against an unstratified
baseline while the point estimate used the stratified one, support
gated on raw episode count instead of valid outcomes, and an
at-or-before (not exact) entry-bar lookup. TESTs 21/22/29 updated for
the new BH-FDR key shape; TEST 36-38 added. See
`docs/spec003_known_limitations.md`'s PATCH #003-A section for detail.

| # | Test | File | Result | Notes |
|---|------|------|--------|-------|
| 1 | Forward return arithmetic | `test_01_forward_return_arithmetic.py` | **PASS** | Manual 1/2/3/5/10-bar `R=P(t+h)/P(t)-1` on a hand-built series, exact match. |
| 2 | Bar-horizon semantics | `test_02_bar_horizon_semantics.py` | **PASS** | A deliberate calendar gap (missing weekday) proves horizon moves BAR positions, not calendar days. |
| 3 | Configurable timeframe metadata | `test_03_configurable_timeframe_metadata.py` | **PASS** (2 sub-tests) | `ForwardOutcome`/`EvidenceProfile` field-name scan -- no hardcoded day-coupled structure anywhere. |
| 4 | Benchmark relative return | `test_04_benchmark_relative_return.py` | **PASS** | `AR = R - R_benchmark`, hand-verified. |
| 5 | Benchmark date alignment | `test_05_benchmark_date_alignment.py` | **PASS** (2 sub-tests) | Positionally-offset bar lists still align correctly by date; a missing benchmark bar produces `MISSING_BENCHMARK`, never a wrong value. |
| 6 | Development boundary | `test_06_development_boundary.py` | **PASS** (2 sub-tests) | Exit past `development_end` -> `CROSSES_LOCKED_OOS`; exit within it -> `VALID`. |
| 7 | OOS mutation invariance | `test_07_oos_mutation_invariance.py` | **PASS** | Mutating a price value beyond `development_end` produces a byte-identical `ForwardOutcome`. |
| 8 | Missing future data | `test_08_missing_future_data.py` | **PASS** | Horizon exceeding available bars -> `INSUFFICIENT_FUTURE_DATA`, never a fabricated 0 or a silent drop. |
| 9 | Episode deduplication | `test_09_episode_deduplication.py` | **PASS** | Consecutive matches collapse into one episode, representative=FIRST. |
| 10 | Episode separation | `test_10_episode_separation.py` | **PASS** (2 sub-tests) | Gap beyond `max_gap_bars` splits into a new episode; a tolerated gap stays one. |
| 11 | Raw vs episode counts | `test_11_raw_vs_episode_counts.py` | **PASS** | Every raw match belongs to exactly one episode; episode count <= raw count. |
| 12 | Baseline distribution | `test_12_baseline_distribution.py` | **PASS** | `TEMPORALLY_STRATIFIED_ELIGIBLE_BASELINE` hand-verified: an unrelated-regime outlier with zero signature weight does not leak into the estimate. |
| 13 | Absolute descriptive metrics | `test_13_absolute_descriptive_metrics.py` | **PASS** | mean/median/positive_rate/quantile ordering hand-verified. |
| 14 | Relative descriptive metrics | `test_14_relative_descriptive_metrics.py` | **PASS** | Confirms relative stats are computed on benchmark-adjusted values, not silently reusing absolute ones. |
| 15 | Minimum episode support | `test_15_minimum_episode_support.py` | **PASS** (2 sub-tests) | `support_status` flips INSUFFICIENT/SUFFICIENT around `minimum_episode_count`, via the real end-to-end pipeline. |
| 16 | Minimum unique-security support | `test_16_minimum_unique_security_support.py` | **PASS** | Gates independently on `unique_security_count`, not just episode count. |
| 17 | Security concentration | `test_17_security_concentration.py` | **PASS** | Spec's own "80 episodes, 52 from one security" example reproduced exactly. |
| 18 | Bootstrap determinism | `test_18_bootstrap_determinism.py` | **PASS** (2 sub-tests) | Same seed -> byte-identical replicates/CI; different seed -> different replicates. |
| 19 | Episode-aware (TIME_BLOCK) bootstrap | `test_19_episode_aware_bootstrap.py` | **PASS** (2 sub-tests) | A single whole-series block collapses the CI to a point (proves block, not point, resampling); multiple blocks produce genuine variation. |
| 20 | Statistical comparison | `test_20_statistical_comparison.py` | **PASS** (3 sub-tests) | Permutation test: separated groups -> small p; identical groups -> p near 1; empty group -> `(None, None)`. |
| 21 | BH-FDR hand calculation | `test_21_bh_fdr_hand_calculation.py` | **PASS** (2 sub-tests) | Exact hand-computed BH step-up on 4 p-values; monotonicity property on a 5th. |
| 22 | Multiple-testing family isolation | `test_22_multiple_testing_family_isolation.py` | **PASS** | A different `horizon_bars` family's p-values never affect another family's BH correction. |
| 23 | Stability temporal bins | `test_23_stability_temporal_bins.py` | **PASS** | Per-bin breakdown (episode_n/unique_securities/mean), always reported even when a bin is empty. |
| 24 | Opportunity-density arithmetic | `test_24_opportunity_density_arithmetic.py` | **PASS** | `episodes_per_20/60_sessions` and median bar-gap hand-verified. |
| 25 | No Evaluation/Alpha Score | `test_25_no_evaluation_alpha_score.py` | **PASS** | AST identifier scan across `src/evaluation/` -> zero forbidden combined-score identifiers. |
| 26 | Discovery cannot import Evaluation | `test_26_discovery_cannot_import_evaluation.py` | **PASS** | AST import scan of `src/discovery/` -> no `evaluation` import anywhere. |
| 27 | Locked OOS protection | `test_27_locked_oos_protection.py` | **PASS** (2 sub-tests) | `CROSSES_LOCKED_OOS` never populates `exit_reference_price`; end-to-end run confirms no VALID outcome exits past `development_end`. |
| 28 | Signature set completeness | `test_28_signature_set_completeness.py` | **PASS** (2 sub-tests) | Same set (any order) -> same `signature_set_id`; adding one signature -> a different id. |
| 29 | Post-hoc labeling | `test_29_post_hoc_labeling.py` | **PASS** | `creation_mode` (signature-level) and `evaluation_mode` (run-level) confirmed as two independent, never-conflated concepts. |
| 30 | Total-return prohibition | `test_30_total_return_prohibition.py` | **PASS** | AST attribute-access scan -> `total_return_adjusted_close` never accessed under `src/evaluation/`. |
| 31 | Reproducibility metadata | `test_31_reproducibility_metadata.py` | **PASS** | Identical inputs -> identical `run_id` AND identical `EvidenceProfile` list, via the real pipeline. |
| 32 | Missingness reconciliation | `test_32_missingness_reconciliation.py` | **PASS** | The 5 outcome-status counts sum exactly to `episodes`, for every signature x horizon, via the real pipeline. |
| 33 | Candidate Budget isolation | `test_33_candidate_budget_isolation.py` | **PASS** | Changing `max_candidates` produces byte-identical `EvidenceProfile` output -- re-proves IMPLEMENTATION BLOCKER SS74A's resolution from Evaluation's own consuming side. |
| 34 | Holding-decay curve | `test_34_holding_decay_curve.py` | **PASS** | `decay_curve()` returns the full per-horizon profile, sorted, with no "winner" field anywhere. |
| 35 | Zero LLM imports | `test_35_zero_llm_imports.py` | **PASS** | AST import scan -> no `anthropic`/`openai`/`google.generativeai`/`cohere`/`langchain` import anywhere under `src/evaluation/`. |
| 36 | BH-FDR multi-horizon routing | `test_36_bh_multi_horizon_routing.py` | **PASS** | Added by PATCH #003-A (finding #1). Real pipeline run, one signature across 5 horizons: each `EvidenceProfile.baseline_comparison.family_id` matches ITS OWN `horizon_bars`, and (singleton family) `adjusted_p == raw_p`. Fails against the pre-patch signature_id-only key (verified: reverting the lookup key produces `adjusted_p=None` on 4/5 profiles). |
| 37 | FORMAL_DEVELOPMENT rejects post-hoc signatures | `test_37_formal_development_rejects_post_hoc.py` | **PASS** (2 sub-tests) | Added by PATCH #003-A (finding #3). `run_evaluation()` raises `ValueError` for a signature with `creation_mode=EXPLORATORY_POST_HOC`, and separately for one claiming `PRE_REGISTERED` but with `created_before_outcome_evaluation=False`. |
| 38 | Exact entry-bar required | `test_38_exact_entry_bar_required.py` | **PASS** (2 sub-tests) | Added by PATCH #003-A (finding #6). No bar dated exactly `observation_as_of` (a halt/gap) -> `INVALID_INPUT`, never a silently-shifted at-or-before entry; an exact match is used normally. |
| 39 | TIME_BLOCK blocks the real session calendar | `test_39_time_block_real_session_calendar.py` | **PASS** (4 sub-tests) | Added by PATCH #003-B. Sparse event dates placed within a real calendar, not treated as consecutive; `block_length_bars` counts market sessions (confirmed via composition statistics, not just the mean); same-day cross-security values always drawn together in equal multiples; a gap session with no value contributes nothing without erroring. Verified to reproduce the pre-patch bug when `session_dates` is derived from the event dates themselves. |
| 40 | FORMAL_DEVELOPMENT provenance guard | `test_40_formal_development_provenance_guard.py` | **PASS** (4 sub-tests) | Added by PATCH #003-B. `run_evaluation()` rejects a signature whose `discovery_config_version`, `discovery_engine_version`, or `timeframe` doesn't match the actual run; matching provenance is accepted normally. |

## How to reproduce

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
# regenerate docs/spec003_examples.md, spec003_multiple_testing_report.md, spec003_performance_report.md:
PYTHONPATH=src:tests python3 -m spec003.generate_report_artifacts
```

No network access is required or attempted -- every test runs against
hand-constructed series or the fully synthetic, deterministic
`tests/spec003/fixtures/tiny_universe.py`.
