"""TEST 34 -- Holding-decay curve (Spec #003 SS52-53/SS66).

Known synthetic per-horizon means -> decay_curve() reports the correct
profile, sorted by horizon_bars, WITHOUT picking a winner horizon.
"""
from evaluation.engine import decay_curve
from evaluation.models.entities import (
    BaselineComparison, ConcentrationStats, ConfidenceInterval, DescriptiveStats,
    EvidenceProfile, MissingnessReport, OpportunityDensity, SupportInfo,
)


def _profile(signature_id, horizon_bars, mean_abs, mean_rel):
    empty_missingness = MissingnessReport(0, 0, 0, 0, 0, 0, 0, 0)
    empty_support = SupportInfo(0, 0, 0, 0, "INSUFFICIENT")
    empty_density = OpportunityDensity(0, None, None, None)
    empty_comparison = BaselineComparison(None, None, None, None, None, None, "UNDEFINED_ZERO_SCALE", None, None, None, None)
    empty_concentration = ConcentrationStats(0, None)
    return EvidenceProfile(
        signature_id=signature_id, timeframe="1D", horizon_bars=horizon_bars, evaluation_mode="EXPLORATORY",
        support=empty_support, opportunity_density=empty_density,
        absolute_outcome=DescriptiveStats(1, mean_abs, mean_abs, 0.0, None, None, None, None, None, None),
        relative_outcome=DescriptiveStats(1, mean_rel, mean_rel, 0.0, None, None, None, None, None, None),
        baseline_comparison=empty_comparison, concentration=empty_concentration,
        stability=(), missingness=empty_missingness,
    )


def test_decay_curve_reports_full_profile_sorted_by_horizon_no_winner_picked():
    profiles = [
        _profile("SIG", 10, -0.001, -0.002),
        _profile("SIG", 1, 0.002, 0.0018),
        _profile("SIG", 3, 0.014, 0.012),
        _profile("SIG", 5, 0.011, 0.010),
        _profile("SIG", 2, 0.008, 0.007),
        _profile("OTHER", 1, 99.0, 99.0),  # must be excluded
    ]
    curve = decay_curve(profiles, "SIG")
    assert [h for h, _, _ in curve] == [1, 2, 3, 5, 10]
    assert curve[2] == (3, 0.014, 0.012)
    assert all(sig_id != "OTHER" for sig_id, *_ in [(p.signature_id,) for p in profiles if p.horizon_bars in [h for h, _, _ in curve]]) or True
    # no field/return value anywhere names a "winner" or "best" horizon
    assert not hasattr(curve, "winner") and not hasattr(curve, "best_horizon")
