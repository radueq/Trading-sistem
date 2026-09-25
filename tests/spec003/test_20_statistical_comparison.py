"""TEST 20 -- Statistical comparison via permutation test (Spec #003
SS40, Radu's explicit correction/SS66).

A clear group separation gives a small p-value; identical groups give a
p-value near 1 -- and raw_p is NEVER derived from a bootstrap CI.
"""
from evaluation.statistics.comparison import permutation_p_value


def test_clearly_separated_groups_give_small_p_value():
    signature = [0.05] * 15
    baseline = [0.0] * 15
    observed, p = permutation_p_value(signature, baseline, iterations=2000, seed=1)
    assert observed > 0
    assert p < 0.01


def test_identical_distributions_give_p_near_one():
    signature = [0.01, -0.01, 0.02, -0.02, 0.0] * 4
    baseline = [0.01, -0.01, 0.02, -0.02, 0.0] * 4
    observed, p = permutation_p_value(signature, baseline, iterations=2000, seed=1)
    assert observed == 0.0
    assert p > 0.9


def test_empty_group_returns_none():
    observed, p = permutation_p_value([], [0.01], iterations=100, seed=1)
    assert observed is None and p is None
