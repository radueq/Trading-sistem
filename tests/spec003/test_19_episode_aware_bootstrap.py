"""TEST 19 -- Episode-aware (TIME_BLOCK) bootstrap (Spec #003 SS39,
Radu's Sec.74B/D amendment/SS66).

Blocks are resampled as UNITS, not individual points. Proof: when
block_length_bars equals the full series length, only ONE block exists
-- every replicate reconstructs the exact original sequence in the
exact original order, so the statistic is IDENTICAL across all
replicates (a zero-width CI). This could not happen under point-level
(non-block) resampling, which would shuffle order/composition freely.
"""
from evaluation.statistics.bootstrap import time_block_bootstrap_replicates, percentile_ci


def test_whole_series_as_one_block_collapses_ci_to_a_point():
    dated = [(f"2024-01-{d:02d}", float(d)) for d in range(1, 21)]  # 20 points, mean=10.5
    session_dates = [d for d, _ in dated]
    replicates = time_block_bootstrap_replicates(dated, session_dates, block_length_bars=len(dated), iterations=100, seed=1)
    assert len(replicates) == 100
    assert all(r == replicates[0] for r in replicates), "a single-block series must reproduce the same statistic every replicate"
    ci = percentile_ci(replicates)
    assert ci.lower == ci.upper == replicates[0]


def test_small_blocks_produce_variation_multi_block_series():
    dated = [(f"2024-01-{d:02d}", float(d)) for d in range(1, 21)]
    session_dates = [d for d, _ in dated]
    replicates = time_block_bootstrap_replicates(dated, session_dates, block_length_bars=2, iterations=200, seed=1)
    assert len(set(replicates)) > 1, "with multiple resampleable blocks, replicates should vary"
