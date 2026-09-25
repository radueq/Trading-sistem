"""TEST 23 -- Stability temporal bins (Spec #003 SS42-43/SS66).

Per-bin breakdown, never a single combined "stability score".
"""
import pytest

from evaluation.baseline.universe import partition_temporal_bins
from evaluation.statistics.stability import stability_by_bin


def test_stability_reports_per_bin_not_a_single_score():
    bins = partition_temporal_bins("2024-01-01", "2024-12-30", 3)
    records = [
        {"as_of": "2024-02-01", "security_id": "A", "forward_return": 0.01, "relative_return": 0.005},
        {"as_of": "2024-02-05", "security_id": "B", "forward_return": 0.03, "relative_return": 0.015},
        {"as_of": "2024-06-01", "security_id": "A", "forward_return": -0.02, "relative_return": -0.01},
    ]
    results = stability_by_bin(records, bins)
    assert len(results) == 3  # early/middle/late, always reported even if empty
    early = next(r for r in results if r.bin_label == "early")
    assert early.episode_n == 2
    assert early.unique_securities == 2
    assert early.mean == pytest.approx((0.01 + 0.03) / 2)
    late = next(r for r in results if r.bin_label == "late")
    assert late.episode_n == 0 and late.mean is None
