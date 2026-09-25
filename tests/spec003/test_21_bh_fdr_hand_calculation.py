"""TEST 21 -- BH-FDR hand calculation (Spec #003 SS44-45/SS66).

Hand-verified Benjamini-Hochberg step-up on 4 raw p-values.
raw sorted: [0.001, 0.02, 0.5, 0.8], m=4
rank*: [0.004, 0.04, 0.6667, 0.8], monotone from the top -> identical here.
"""
import pytest

from evaluation.statistics.multiple_testing import PValueRecord, benjamini_hochberg


def test_bh_matches_hand_computed_values():
    records = [
        PValueRecord("s1", "1D", 3, "relative_return", "run1", 0.001),
        PValueRecord("s2", "1D", 3, "relative_return", "run1", 0.02),
        PValueRecord("s3", "1D", 3, "relative_return", "run1", 0.5),
        PValueRecord("s4", "1D", 3, "relative_return", "run1", 0.8),
    ]
    result = benjamini_hochberg(records)
    assert result["s1"][0] == pytest.approx(0.004)
    assert result["s2"][0] == pytest.approx(0.04)
    assert result["s3"][0] == pytest.approx(0.6667, abs=1e-4)
    assert result["s4"][0] == pytest.approx(0.8)
    for sid in result:
        assert result[sid][1] == "1D|3bars|relative_return|run1"


def test_bh_adjusted_p_is_monotone_non_decreasing_with_rank():
    records = [PValueRecord(f"s{i}", "1D", 3, "relative_return", "run1", p) for i, p in enumerate([0.5, 0.1, 0.3, 0.01, 0.9])]
    result = benjamini_hochberg(records)
    ranked = sorted(records, key=lambda r: r.raw_p)
    adj_in_rank_order = [result[r.signature_id][0] for r in ranked]
    assert adj_in_rank_order == sorted(adj_in_rank_order)
