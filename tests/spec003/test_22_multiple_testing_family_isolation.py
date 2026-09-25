"""TEST 22 -- Multiple-testing family isolation (Spec #003 SS45/SS66).

Family = same timeframe + horizon_bars + outcome_type + evaluation_run.
Signatures tested at a DIFFERENT horizon_bars must never affect each
other's BH correction.
"""
from evaluation.statistics.multiple_testing import PValueRecord, benjamini_hochberg


def test_different_horizon_families_are_corrected_independently():
    family_a = [PValueRecord(f"a{i}", "1D", 3, "relative_return", "run1", p) for i, p in enumerate([0.01, 0.02, 0.03])]
    family_b_weak = [PValueRecord(f"b{i}", "1D", 5, "relative_return", "run1", p) for i, p in enumerate([0.01, 0.02, 0.03])]
    result_with_b_weak = benjamini_hochberg(family_a + family_b_weak)

    family_b_strong = [PValueRecord(f"b{i}", "1D", 5, "relative_return", "run1", p) for i, p in enumerate([0.9, 0.95, 0.99])]
    result_with_b_strong = benjamini_hochberg(family_a + family_b_strong)

    for rec in family_a:
        assert result_with_b_weak[rec.signature_id] == result_with_b_strong[rec.signature_id], (
            "family A's adjusted p-values must not depend on family B's p-value distribution"
        )
