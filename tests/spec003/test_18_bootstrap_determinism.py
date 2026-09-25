"""TEST 18 -- Bootstrap determinism (Spec #003 SS60/SS66).

Same input + same seed -> byte-identical replicates/CI, every time.
"""
from evaluation.statistics.bootstrap import time_block_bootstrap_replicates, percentile_ci


def test_same_seed_same_input_produces_identical_replicates():
    dated = [(f"2024-01-{d:02d}", float(d)) for d in range(1, 41)]
    r1 = time_block_bootstrap_replicates(dated, block_length_bars=5, iterations=300, seed=7)
    r2 = time_block_bootstrap_replicates(dated, block_length_bars=5, iterations=300, seed=7)
    assert r1 == r2
    assert percentile_ci(r1) == percentile_ci(r2)


def test_different_seed_can_produce_different_replicates():
    dated = [(f"2024-01-{d:02d}", float(d)) for d in range(1, 41)]
    r1 = time_block_bootstrap_replicates(dated, block_length_bars=5, iterations=300, seed=7)
    r2 = time_block_bootstrap_replicates(dated, block_length_bars=5, iterations=300, seed=8)
    assert r1 != r2
