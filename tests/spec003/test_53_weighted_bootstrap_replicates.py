"""TEST 53 -- per-replicate weighted bootstrap estimator (joint
remediation design 003+004 section 6; decision registry A4, Stage 4).

Two separate steps, never conflated: (1) the per-replicate statistic is
the per-security-weighted mean, recomputing `k_rep`/`n_i_rep` from EACH
drawn replicate's OWN resampled composition (block resampling with
replacement can change which/how many rows of each security appear --
the original sample's fixed weights are never reused across
replicates); (2) interval construction from the `B` replicate values is
the plain UNWEIGHTED percentile (`percentile_ci()`) -- weighting is
already fully consumed in step 1, never re-applied.
"""
import pytest

from evaluation.statistics.bootstrap import (
    percentile_ci, stratified_baseline_bootstrap_replicates, weighted_mean_by_security,
)


def test_weighted_mean_by_security_equalizes_per_security_contribution():
    # A has 3 rows, B has 1 -- plain mean would let A dominate 3:1;
    # weighted mean equalizes each security's TOTAL contribution.
    rows = [("A", 0.0), ("A", 1.0), ("A", 2.0), ("B", 100.0)]
    result = weighted_mean_by_security(rows)
    assert result == pytest.approx(1.0 * 0.5 + 100.0 * 0.5)  # A's own mean(=1.0)*0.5 + B*0.5
    plain_mean = sum(v for _, v in rows) / len(rows)
    assert result != pytest.approx(plain_mean)


def test_weighted_mean_by_security_empty_returns_none():
    assert weighted_mean_by_security([]) is None


def test_weighted_mean_by_security_recomputes_from_whatever_composition_is_passed():
    # The SAME function, called with a DIFFERENT composition (as a
    # bootstrap replicate would hand it, post-resampling), recomputes
    # k/n_i fresh -- never reuses a fixed weight from elsewhere.
    original = [("A", 0.0), ("A", 1.0), ("B", 100.0)]  # k=2, A has 2 rows, B has 1
    replicate_drops_b_duplicates_a = [("A", 0.0), ("A", 0.0), ("A", 1.0)]  # now k=1 (A only)
    assert weighted_mean_by_security(original) == pytest.approx((0.5) * 0.5 + 100.0 * 0.5)
    # k=1 (only A) -- reduces to A's own plain mean regardless of row count.
    assert weighted_mean_by_security(replicate_drops_b_duplicates_a) == pytest.approx((0.0 + 0.0 + 1.0) / 3)


def test_stratified_baseline_bootstrap_replicates_uses_weighted_mean_per_bin():
    # One bin, 2 bootstrap-able sessions (so the resample can actually
    # vary), security A with 2 rows and B with 1 row sharing ONE
    # session, enough iterations to see variation driven by the WEIGHTED
    # (not plain) per-block statistic.
    rows_by_bin = {
        "x": [("A", "2024-01-01", 0.0), ("A", "2024-01-01", 2.0), ("B", "2024-01-02", 100.0)],
    }
    session_dates_by_bin = {"x": ["2024-01-01", "2024-01-02"]}
    weights_by_bin = {"x": 1.0}

    replicates = stratified_baseline_bootstrap_replicates(
        rows_by_bin, session_dates_by_bin, weights_by_bin, block_length_bars=1, iterations=50, seed=7,
    )
    assert len(replicates) == 50
    # Every replicate's value must be reachable via weighted_mean_by_security
    # applied to SOME resampled composition drawn from the two real
    # blocks (session "2024-01-01" worth 0 or more draws, session
    # "2024-01-02" worth 0 or more draws, 2 blocks drawn with
    # replacement per replicate) -- never a PLAIN mean of raw rows,
    # which would weight A's 2 rows twice as heavily as B's 1.
    # block_length_bars=1 over 2 sessions makes exactly 2 real blocks
    # (one per session); each replicate draws 2 blocks WITH replacement
    # from those 2 -- so the reachable compositions are exactly
    # (n1, n2) in {(2,0), (1,1), (0,2)}, n1+n2 == 2 always.
    weighted_values = {
        weighted_mean_by_security([("A", 0.0), ("A", 2.0)] * n1 + [("B", 100.0)] * n2)
        for n1, n2 in [(2, 0), (1, 1), (0, 2)]
    }
    assert all(any(r == pytest.approx(w) for w in weighted_values) for r in replicates)
    # Sanity: confirm the weighted mechanics actually differ from a
    # plain row mean for at least the "both drawn once" composition.
    plain_both = (0.0 + 2.0 + 100.0) / 3
    weighted_both = weighted_mean_by_security([("A", 0.0), ("A", 2.0), ("B", 100.0)])
    assert weighted_both != pytest.approx(plain_both)


def test_interval_construction_from_replicates_is_plain_unweighted_percentile():
    # percentile_ci() itself takes plain replicate VALUES -- step 2
    # never re-applies any weighting; this is a structural fact about
    # percentile_ci()'s own signature (list[float] -> ConfidenceInterval),
    # exercised here with hand-built replicate values standing in for
    # step 1's already-weighted output.
    replicates = [1.0, 2.0, 3.0, 4.0, 100.0]
    ci = percentile_ci(replicates)
    assert ci.lower is not None and ci.upper is not None
    assert ci.method == "TIME_BLOCK_BOOTSTRAP_PERCENTILE"


def test_bin_with_no_eligible_rows_in_a_replicate_is_excluded_from_that_replicate():
    # Two bins, weight > 0 in both, but "late" has NO rows at all --
    # must not crash, and the combine step must renormalize over
    # whichever bins DO have replicates for that iteration (mirroring
    # the existing total_weight > 0 guard, unchanged).
    rows_by_bin = {
        "early": [("A", "2024-01-01", 1.0), ("B", "2024-01-02", 3.0)],
        "late": [],
    }
    session_dates_by_bin = {"early": ["2024-01-01", "2024-01-02"], "late": ["2024-06-01"]}
    weights_by_bin = {"early": 0.5, "late": 0.5}
    replicates = stratified_baseline_bootstrap_replicates(
        rows_by_bin, session_dates_by_bin, weights_by_bin, block_length_bars=1, iterations=20, seed=3,
    )
    assert len(replicates) == 20
    assert all(r is not None for r in replicates)
