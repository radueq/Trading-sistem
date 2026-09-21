"""Utility script (not a pytest test) that runs Discovery once against
the full synthetic universe and writes the two deliverables that need
real computed output: docs/spec002_examples.md (Spec #002 SS39) and
docs/spec002_volume_report.md (Spec #002 SS40). Re-run manually after
any change to features/config; not part of the automated test suite.
"""
from __future__ import annotations

import time
from pathlib import Path

# Run as: PYTHONPATH=src:tests python3 -m spec002.generate_report_artifacts
# (from repo root) -- NOT as a direct script path, which would put
# tests/spec002/ itself on sys.path ahead of tests/ and shadow the
# top-level `fixtures` package (tests/fixtures/) with
# tests/spec002/fixtures/ (the Spec #002 synthetic-universe fixtures).
REPO_ROOT = Path(__file__).resolve().parents[2]

from data_foundation.adapters.yfinance_adapter import YFinanceAdapter, utc_now_iso
from data_foundation.model import ingestion as ing
from data_foundation.storage.db import connect_and_init
from fixtures.fake_yfinance import make_ticker_factory

from discovery.config.loader import load_config
from discovery.eligibility.engine import evaluate_eligibility
from discovery.engine import _compute_security_local, run_discovery
from spec002.fixtures.synthetic_universe import ALL_DATASETS, AS_OF, BENCHMARK


def build_universe():
    conn = connect_and_init(":memory:")
    now = utc_now_iso()

    ticker_to_dataset = {BENCHMARK["ticker"]: BENCHMARK}
    for ds in ALL_DATASETS:
        ticker_to_dataset[ds["ticker"]] = ds
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory(ticker_to_dataset))

    security_ids = {}
    t0 = time.time()
    for ticker, ds in ticker_to_dataset.items():
        sid = ing.new_security_id(f"spec002:{ticker}")
        ing.ensure_security(conn, sid, adapter, ticker, now)
        start, end = ds["bars"][0]["date"], ds["bars"][-1]["date"]
        ing.ensure_symbol_history(conn, sid, ticker, start, None, "yfinance")
        ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)
        security_ids[ticker] = sid
    ingestion_seconds = time.time() - t0

    bench_sid = security_ids[BENCHMARK["ticker"]]
    non_bench_ids = [sid for tk, sid in security_ids.items() if tk != BENCHMARK["ticker"]]
    return conn, security_ids, bench_sid, non_bench_ids, ingestion_seconds


def format_example(c) -> str:
    lines = [
        f"### Ticker: {c.ticker_as_of}",
        "",
        f"as_of: {c.as_of}  |  timeframe: {c.timeframe}",
        "",
        "State signature:",
    ]
    for lane, label in sorted(c.state_signature.items()):
        lines.append(f"  {lane}: {label}")
    lines += [
        "",
        "Selected raw measurements:",
        f"  return_63d: {c.feature_vector.get('return_63d')}",
        f"  relative_return_63d: {c.feature_vector.get('relative_return_63d')}",
        f"  BB_width_20: {c.feature_vector.get('BB_width_20')}",
        f"  RVOL_20: {c.feature_vector.get('RVOL_20')}",
        f"  ROC_10: {c.feature_vector.get('ROC_10')}",
        "",
        "Reason codes:",
    ]
    for code in c.reason_codes:
        lines.append(f"  {code}")
    lines += [
        "",
        "Descriptive metrics:",
        f"  extremeness: {round(c.descriptive_metrics.extremeness, 4)}",
        f"  persistence: {c.descriptive_metrics.persistence} trading days",
        f"  state_frequency: {round(c.descriptive_metrics.state_frequency, 4) if c.descriptive_metrics.state_frequency is not None else None}"
        f" (sample_count={c.descriptive_metrics.sample_count}, support={c.descriptive_metrics.support_status})",
        "",
        "Why candidate: statistically unusual/notable current state relative to",
        "its own history and/or the eligible universe on this date.",
        "",
        "What this does NOT mean: no claim that forward return will be positive,",
        "no claim this is a trade recommendation -- Discovery is outcome-blind",
        "(Spec #002 SS2) and produced this candidate using only information",
        "available at as_of.",
        "",
    ]
    return "\n".join(lines)


def main():
    conn, security_ids, bench_sid, non_bench_ids, ingestion_seconds = build_universe()
    config = load_config()

    t0 = time.time()
    candidates = run_discovery(conn, non_bench_ids, AS_OF, bench_sid, config)
    discovery_seconds = time.time() - t0

    # Volume report counts (Spec #002 SS40)
    initial_universe_count = len(non_bench_ids)
    eligibility_results = []
    valid_feature_count = 0
    for sid in non_bench_ids:
        bars = None
        from data_foundation.pit import access as pit
        bars = pit.get_price_series_as_of(conn, sid, AS_OF)
        r = _compute_security_local(bars, _bench_df(conn, bench_sid), config)
        eligibility_results.append(evaluate_eligibility(
            security_id=sid, as_of=AS_OF, latest_close=r["latest_close"],
            history_days=r["history_days"], latest_adv_20=r["latest_adv_20"],
            primary_exchange=None, config=config.eligibility,
        ))
        if r["history_days"] >= config.features["percentile_min_periods"]:
            valid_feature_count += 1
    eligibility_count = sum(1 for e in eligibility_results if e.eligible)
    discovery_observation_count = eligibility_count  # every eligible security gets a StateSignature/candidate assembly pass
    candidate_count_after_budget = len(candidates)

    # 3 controlled examples: the most extreme, the most persistent, and
    # a multi-lane-convergence one, drawn from the ACTUAL computed
    # output (not cherry-picked to match a hoped-for narrative).
    by_extremeness = sorted(candidates, key=lambda c: -c.descriptive_metrics.extremeness)
    by_persistence = sorted(candidates, key=lambda c: -c.descriptive_metrics.persistence)
    by_lane_count = sorted(candidates, key=lambda c: -len(c.active_lanes))

    chosen = []
    seen = set()
    for pool in (by_extremeness, by_persistence, by_lane_count):
        for c in pool:
            if c.security_id not in seen:
                chosen.append(c)
                seen.add(c.security_id)
                break

    examples_md = "\n".join([
        "# Spec #002 -- Example Discovery Output (Deliverable D)\n",
        "Three controlled examples drawn from an actual `run_discovery()` run",
        "against the Level 1 synthetic universe (`tests/spec002/fixtures/synthetic_universe.py`).",
        "All figures below are as literally computed -- not hand-edited to match a hoped-for story.\n",
        format_example(chosen[0]),
        format_example(chosen[1]),
        format_example(chosen[2]),
    ])

    volume_md = "\n".join([
        "# Spec #002 -- Volume / Performance Report (Deliverable E)\n",
        f"Universe: synthetic Level 1 test fixtures ({len(ALL_DATASETS)} named + filler securities), as_of={AS_OF}.\n",
        "| Stage | Count |",
        "|---|---|",
        f"| Initial universe | {initial_universe_count} |",
        f"| Eligibility count (passed Universe Eligibility) | {eligibility_count} |",
        f"| Valid-feature count (>= percentile_min_periods history) | {valid_feature_count} |",
        f"| Discovery-observation count (state signatures assembled) | {discovery_observation_count} |",
        f"| Candidate count after budget | {candidate_count_after_budget} |",
        "",
        "## Timing (informational, Level 1 synthetic scale -- not an acceptance blocker per Spec #002 SS37)",
        "",
        f"- Ingestion ({len(security_ids)} securities x ~320 daily bars): {ingestion_seconds:.3f}s",
        f"- Discovery ({initial_universe_count} securities, {config.features['percentile_window']}-day percentile window): {discovery_seconds:.3f}s",
        f"- Per-security average: {discovery_seconds / max(1, initial_universe_count) * 1000:.1f}ms",
    ])

    (REPO_ROOT / "docs" / "spec002_examples.md").write_text(examples_md + "\n")
    (REPO_ROOT / "docs" / "spec002_volume_report.md").write_text(volume_md + "\n")
    print("Wrote docs/spec002_examples.md and docs/spec002_volume_report.md")
    print(f"ingestion={ingestion_seconds:.3f}s discovery={discovery_seconds:.3f}s candidates={len(candidates)}")


def _bench_df(conn, bench_sid):
    from data_foundation.pit import access as pit
    from discovery.engine import _price_series_to_df
    return _price_series_to_df(pit.get_price_series_as_of(conn, bench_sid, AS_OF))


if __name__ == "__main__":
    main()
