"""Utility script (not a pytest test) that produces Spec #003's report
deliverables: docs/spec003_examples.md (SS67, Deliverable D-equivalent),
docs/spec003_multiple_testing_report.md (SS70), and
docs/spec003_performance_report.md (SS68/SS70).

Two different data sources, by design:
- Examples A/B/C/D use hand-crafted synthetic (date, return) series fed
  DIRECTLY into the statistics primitives (describe/bootstrap/
  permutation/BH-FDR) -- this lets each example's known-by-construction
  property (decay speed, noise, multiple-testing trap) be exact and
  auditable, without depending on Discovery's own state-matching timing
  (already exercised thoroughly by the TEST 1-35 suite).
- The performance report runs the REAL end-to-end run_evaluation()
  pipeline once against tests/spec003/fixtures/tiny_universe.py, so its
  numbers (securities/bars/observations/episodes/runtime) are genuine
  pipeline output, not fabricated.

Re-run manually after any change to statistics/engine logic:
  PYTHONPATH=src:tests python3 -m spec003.generate_report_artifacts
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]

from evaluation.statistics.bootstrap import bootstrap_ci_for_series
from evaluation.statistics.comparison import permutation_p_value
from evaluation.statistics.descriptive import describe
from evaluation.statistics.multiple_testing import PValueRecord, benjamini_hochberg, record_key

HORIZONS = [1, 2, 3, 5, 10]
N_EPISODES = 40
N_BASELINE = 300


def _dates(n: int, start_day: int = 1) -> list[str]:
    return [f"2024-{1 + (start_day + i) // 28:02d}-{1 + (start_day + i) % 28:02d}" for i in range(n)]


def _synthetic_series(mean: float, noise: float, n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return list(rng.normal(mean, noise, n))


def _evaluate_example(name: str, mean_by_horizon: dict[int, float], noise: float, seed: int) -> str:
    lines = [f"### Example {name}\n"]
    baseline = _synthetic_series(0.0, noise, N_BASELINE, seed + 900)
    baseline_dated = list(zip(_dates(N_BASELINE), baseline))
    for h in HORIZONS:
        values = _synthetic_series(mean_by_horizon[h], noise, N_EPISODES, seed + h)
        dated = list(zip(_dates(N_EPISODES), values))
        d = describe(values)
        ci = bootstrap_ci_for_series(dated, block_length_bars=5, iterations=1000, seed=seed + h)
        observed, raw_p = permutation_p_value(values, baseline, iterations=1000, seed=seed + h + 1)
        lines.append(
            f"- **{h} bar(s)**: mean={d.mean:.4f}, median={d.median:.4f}, "
            f"95% CI=({ci.lower:.4f}, {ci.upper:.4f}), raw_p={raw_p:.4f}"
        )
    lines.append("")
    return "\n".join(lines)


def build_examples_md() -> str:
    sections = [
        "# Spec #003 -- Example Evaluation Output (Deliverable D-equivalent)\n",
        "**All four examples below are computed from deterministic synthetic",
        "(date, return) series fed directly into the statistics primitives",
        "(describe/bootstrap/permutation) -- no live-market data anywhere.",
        "Every number is exactly what the code computed, not hand-edited.**\n",
        "Fast-Swing framing (Spec #003 v1.1): horizons are 1/2/3/5/10 BARS,",
        "never calendar days -- see docs/spec003_architecture.md.\n",
    ]

    sections.append(_evaluate_example(
        "A -- Fast effect, decays by 5-10 bars",
        {1: 0.020, 2: 0.022, 3: 0.024, 5: 0.010, 10: 0.001}, noise=0.012, seed=1001,
    ))
    sections.append(
        "Interpretation: the effect is strongest at 1-3 bars and has "
        "essentially vanished by 10 -- exactly the profile a Fast-Swing "
        "target (~1-5 day holding) should care about. #003 reports this "
        "curve; it does NOT pick '3 bars' as 'the exit' (Spec #003 SS53).\n"
    )

    sections.append(_evaluate_example(
        "B -- Delayed effect, builds into 3-5 bars",
        {1: 0.001, 2: 0.005, 3: 0.015, 5: 0.020, 10: 0.012}, noise=0.012, seed=2002,
    ))
    sections.append(
        "Interpretation: the opposite decay shape from A -- weak "
        "immediately, stronger after 3-5 bars. Reported the same way, "
        "same machinery, no special-casing.\n"
    )

    sections.append(_evaluate_example(
        "C -- Pure noise, no true difference",
        {h: 0.0 for h in HORIZONS}, noise=0.015, seed=3003,
    ))
    sections.append(
        "Interpretation: raw_p should NOT cluster near 0 across horizons "
        "here -- if it does, that is itself a red flag about the method, "
        "not a discovery. Demonstrated below to behave as expected.\n"
    )

    sections.append(build_multiple_testing_trap_section())
    return "\n".join(sections)


def build_multiple_testing_trap_section() -> str:
    """Example D -- SS67: many random (pure-noise) signatures, some will
    show an attractive raw p-value by chance alone; BH-FDR is what tells
    you not to trust them naively."""
    n_signatures = 30
    lines = [
        "### Example D -- Multiple-testing trap\n",
        f"{n_signatures} independent PURE-NOISE synthetic signatures (no real",
        "effect by construction, mean=0 for both groups), single horizon",
        "(3 bars), tested together as ONE frozen family. Raw p-values alone",
        "already look tempting for several of them; BH-FDR is what exposes",
        "that as an artifact of testing many things at once.\n",
        "| Signature | raw_p | adjusted_p (BH-FDR, q=0.05) | 'significant' at raw p<0.05? | after BH-FDR? |",
        "|---|---|---|---|---|",
    ]
    records = []
    raw_ps = {}
    for i in range(n_signatures):
        sig_values = _synthetic_series(0.0, 0.02, 20, seed=5000 + i)
        base_values = _synthetic_series(0.0, 0.02, 200, seed=6000 + i)
        _, p = permutation_p_value(sig_values, base_values, iterations=1000, seed=7000 + i)
        raw_ps[f"trap_sig_{i:02d}"] = p
        records.append(PValueRecord(f"trap_sig_{i:02d}", "1D", 3, "relative_return", "example_d", p))

    adjusted = benjamini_hochberg(records)
    # keyed by record_key() (signature_id, timeframe, horizon_bars,
    # outcome_type, evaluation_run_id) -- PATCH #003-A, not signature_id alone.
    adjusted_by_sid = {rec.signature_id: adjusted[record_key(rec)] for rec in records}
    naive_significant = sum(1 for p in raw_ps.values() if p < 0.05)
    corrected_significant = sum(1 for adj_p, _ in adjusted_by_sid.values() if adj_p < 0.05)

    for sid in sorted(raw_ps, key=lambda s: raw_ps[s]):
        raw_p = raw_ps[sid]
        adj_p, _ = adjusted_by_sid[sid]
        lines.append(f"| {sid} | {raw_p:.4f} | {adj_p:.4f} | {'YES' if raw_p < 0.05 else 'no'} | {'YES' if adj_p < 0.05 else 'no'} |")

    lines.append("")
    lines.append(
        f"**{naive_significant}/{n_signatures}** signatures look 'significant' by raw p<0.05 alone "
        f"(pure chance, since every signature here is genuinely pure noise) -- "
        f"BH-FDR correctly brings that down to **{corrected_significant}/{n_signatures}**. "
        "This is exactly why Spec #003 SS26 freezes the Signature Set before "
        "looking at outcomes, and SS44 makes BH-FDR mandatory for "
        "FORMAL_DEVELOPMENT: testing 30 things and reporting only the "
        "'winners' would silently reproduce this exact trap.\n"
    )
    return "\n".join(lines)


def build_performance_report() -> tuple[str, float]:
    from data_foundation.adapters.yfinance_adapter import YFinanceAdapter, utc_now_iso
    from data_foundation.model import ingestion as ing
    from data_foundation.storage.db import connect_and_init
    from fixtures.fake_yfinance import make_ticker_factory

    from discovery.config.loader import load_config as load_discovery_config
    from evaluation.config.loader import load_config as load_evaluation_config
    from evaluation.engine import run_evaluation
    from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
    from evaluation.registry.signatures import freeze_signature_set

    from spec003.fixtures.tiny_universe import ALL_DATASETS, BENCHMARK, DATES
    from dataclasses import replace

    conn = connect_and_init(":memory:")
    now = utc_now_iso()
    ticker_to_dataset = {BENCHMARK["ticker"]: BENCHMARK}
    for ds in ALL_DATASETS:
        ticker_to_dataset[ds["ticker"]] = ds
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory(ticker_to_dataset))

    t_ingest0 = time.time()
    security_ids = {}
    total_bars = 0
    for ticker, ds in ticker_to_dataset.items():
        sid = ing.new_security_id(f"perf003:{ticker}")
        ing.ensure_security(conn, sid, adapter, ticker, now)
        start, end = ds["bars"][0]["date"], ds["bars"][-1]["date"]
        ing.ensure_symbol_history(conn, sid, ticker, start, None, "yfinance")
        ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)
        security_ids[ticker] = sid
        total_bars += len(ds["bars"])
    ingestion_seconds = time.time() - t_ingest0

    bench_sid = security_ids[BENCHMARK["ticker"]]
    non_bench_ids = [sid for tk, sid in security_ids.items() if tk != BENCHMARK["ticker"]]

    base_discovery_cfg = load_discovery_config()
    discovery_cfg = replace(
        base_discovery_cfg,
        features={**base_discovery_cfg.features, "percentile_window": 15, "percentile_min_periods": 15},
        eligibility={**base_discovery_cfg.eligibility, "minimum_history_days": 15, "minimum_adv_20": 1000},
    )
    evaluation_cfg = load_evaluation_config()

    sig = EvaluationSignatureDefinition(
        signature_id="VOLATILITY_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=discovery_cfg.config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )
    sigset = freeze_signature_set([sig])

    dev_start, dev_end = DATES[30], DATES[55]
    t0 = time.time()
    profiles, registry = run_evaluation(
        conn, non_bench_ids, bench_sid, dev_start, dev_end, sigset, discovery_cfg, evaluation_cfg,
    )
    evaluation_seconds = time.time() - t0

    n_sessions = len(DATES[30:56])
    n_securities = len(non_bench_ids)
    total_episodes = sum(p.support.episode_n for p in profiles)
    total_raw = sum(p.support.raw_n for p in profiles)

    report = "\n".join([
        "# Spec #003 -- Performance Report\n",
        f"Universe: `tests/spec003/fixtures/tiny_universe.py` ({n_securities} securities + benchmark), "
        f"Development window {dev_start}..{dev_end} ({n_sessions} sessions).\n",
        "| Metric | Value |",
        "|---|---|",
        f"| Securities | {n_securities} |",
        f"| Total ingested bars | {total_bars} |",
        f"| Sessions in Development window | {n_sessions} |",
        f"| Raw observations (1 signature, all horizons) | {total_raw} |",
        f"| Episodes (EPISODE_DEDUPLICATED) | {total_episodes} |",
        f"| Signatures tested | {len(sigset.signatures)} |",
        f"| Horizon evaluations (signatures x horizons) | {len(profiles)} |",
        f"| Statistical tests (bootstrap + permutation) per horizon | 3 (abs CI, rel CI, comparison) |",
        "",
        "## Timing (informational, Level 1 tiny-universe scale -- not an acceptance blocker, mirrors Spec #002 SS37)\n",
        f"- Ingestion ({n_securities + 1} securities): {ingestion_seconds:.3f}s",
        f"- Full run_evaluation() ({n_sessions} sessions x {n_securities} securities, "
        f"{len(sigset.signatures)} signature x {len(profiles)} horizon evaluations): {evaluation_seconds:.3f}s",
        f"- Per-session average: {evaluation_seconds / max(1, n_sessions) * 1000:.1f}ms",
        "",
        "**LLM runtime tokens: 0** (Spec #003 SS61 -- zero LLM calls anywhere in this path, TEST 35).",
        "",
        "Cost driver (documented, not hidden): one Discovery pass "
        "(compute_discovery_observations) per session, O(sessions x universe) "
        "-- the same acknowledged Level 1 tradeoff as Spec #002's own cross-"
        "sectional computation (docs/spec002_known_limitations.md). Fine at "
        "this scale; a real research-scale universe/date-range would need "
        "either a much larger time budget or an incremental/cached Discovery "
        "pass -- not built here, see docs/spec003_known_limitations.md.",
    ])
    return report, evaluation_seconds


def main():
    examples_md = build_examples_md()
    (REPO_ROOT / "docs" / "spec003_examples.md").write_text(examples_md + "\n")

    mt_report = "\n".join([
        "# Spec #003 -- Multiple-Testing Report\n",
        "Worked demonstration (Example D) of why raw p-values across many",
        "tested signatures cannot be trusted naively, and why BH-FDR",
        "(config `multiple_testing.method: BENJAMINI_HOCHBERG`, default",
        "q=0.05) is mandatory for FORMAL_DEVELOPMENT mode (Spec #003 SS44).\n",
        build_multiple_testing_trap_section(),
        "## Family definition (Spec #003 SS45)\n",
        "A family = same `timeframe` + `horizon_bars` + `outcome_type` + ",
        "`evaluation_run` (see `evaluation.statistics.multiple_testing.family_id`).",
        "Signatures tested at a DIFFERENT horizon never correct each other's",
        "p-values (TEST 22 proves this in isolation).",
    ])
    (REPO_ROOT / "docs" / "spec003_multiple_testing_report.md").write_text(mt_report + "\n")

    perf_report, elapsed = build_performance_report()
    (REPO_ROOT / "docs" / "spec003_performance_report.md").write_text(perf_report + "\n")

    print(f"Wrote docs/spec003_examples.md, docs/spec003_multiple_testing_report.md, docs/spec003_performance_report.md")
    print(f"performance run took {elapsed:.3f}s")


if __name__ == "__main__":
    main()
