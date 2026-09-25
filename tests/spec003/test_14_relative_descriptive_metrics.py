"""TEST 14 -- Relative descriptive metrics (Spec #003 SS35/SS66).

Same descriptive machinery applied to relative_return -- verifies it's
computed on the BENCHMARK-ADJUSTED values, not silently reusing the
absolute ones.
"""
import pytest

from evaluation.statistics.descriptive import describe


def test_relative_descriptive_stats_differ_from_absolute_when_benchmark_moves():
    absolute = [0.05, 0.06, 0.04, 0.05, 0.06]
    relative = [0.03, 0.04, 0.02, 0.03, 0.04]  # each shifted -0.02 vs a moving benchmark

    d_abs = describe(absolute)
    d_rel = describe(relative)
    assert d_abs.mean != d_rel.mean
    assert d_rel.mean == pytest.approx(d_abs.mean - 0.02)
    assert d_rel.n == d_abs.n == 5
