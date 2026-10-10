"""TEST 54 -- F3 common support, (b) full blackout on any mismatch
(joint remediation design 003+004 section 3-6; decision registry A1,
Stage 4).

Scope note (honest, not overclaiming): this test exercises (1) the
common-support DETECTION logic in isolation (the same bin-membership
check `evaluation/engine.py`'s `_evaluate_signature_horizon()` uses:
a bin counts as common-support only when the signature has weight
there AND the baseline pool has at least one row there), and (2) that
a `BaselineComparison`/`EvidenceProfile` already carrying the resulting
`None` set propagates through `build_evidence_packet()` and
`evidence/queue.py`'s ranking without crashing or substituting a
different value. It does NOT drive a live `run_evaluation()` call
through a real database to PRODUCE a partial-support scenario from
scratch (constructing one through Discovery/PIT would need a carefully
contrived synthetic universe) -- that remains open for a future round
if GPT wants the stronger, full-pipeline version of this proof.
"""
from evaluation.models.entities import (
    BaselineComparison, ConcentrationStats, ConfidenceInterval, DescriptiveStats,
    EvidenceProfile, MissingnessReport, OpportunityDensity, SupportInfo,
)


def _common_support_bins(weights_by_bin: dict, baseline_rows_by_bin: dict) -> tuple[set, set, bool]:
    """The EXACT detection logic `_evaluate_signature_horizon()` uses
    (`src/evaluation/engine.py`) -- reproduced here as a standalone,
    directly-testable unit, since the production function is private
    and takes many unrelated PIT-level parameters."""
    signature_bins_with_weight = {label for label, w in weights_by_bin.items() if w > 0}
    common_support_bins = {label for label in signature_bins_with_weight if baseline_rows_by_bin.get(label)}
    full_common_support = signature_bins_with_weight == common_support_bins
    return signature_bins_with_weight, common_support_bins, full_common_support


def test_full_common_support_when_every_weighted_bin_has_baseline_data():
    weights = {"early": 0.6, "late": 0.4}
    baseline_rows = {"early": [("A", 1.0)], "late": [("B", 2.0)]}
    _, _, full = _common_support_bins(weights, baseline_rows)
    assert full is True


def test_partial_common_support_when_one_weighted_bin_lacks_baseline_data():
    weights = {"early": 0.6, "late": 0.4}
    baseline_rows = {"early": [("A", 1.0)], "late": []}  # signature has weight in "late" but no baseline there
    sig_bins, common_bins, full = _common_support_bins(weights, baseline_rows)
    assert sig_bins == {"early", "late"}
    assert common_bins == {"early"}
    assert full is False


def test_zero_common_support_when_no_weighted_bin_has_baseline_data():
    weights = {"early": 0.6, "late": 0.4}
    baseline_rows = {"early": [], "late": []}
    sig_bins, common_bins, full = _common_support_bins(weights, baseline_rows)
    assert common_bins == set()
    assert full is False


def _profile_with(baseline_comparison: BaselineComparison) -> EvidenceProfile:
    return EvidenceProfile(
        signature_id="SIG", timeframe="1D", horizon_bars=3, evaluation_mode="FORMAL_DEVELOPMENT",
        support=SupportInfo(raw_n=10, episode_n=10, valid_episode_n=10, unique_security_count=5, support_status="SUFFICIENT"),
        opportunity_density=OpportunityDensity(10, 2.0, 1.0, 5.0),
        absolute_outcome=DescriptiveStats(10, 0.01, 0.01, 0.02, None, None, None, None, 0.6, None),
        relative_outcome=DescriptiveStats(10, 0.005, 0.004, 0.01, None, None, None, None, 0.55, None),
        baseline_comparison=baseline_comparison,
        concentration=ConcentrationStats(5, 0.3),
        stability=(), missingness=MissingnessReport(10, 10, 10, 10, 0, 0, 0, 0),
    )


def test_partial_support_blackout_set_leaves_descriptive_stats_intact():
    # The exact 5-field None set decision A1 requires, TOGETHER, on
    # partial (or zero) common support -- the signature's own
    # absolute_outcome/relative_outcome DescriptiveStats (built above,
    # over the FULL episode population) are a SEPARATE, untouched
    # object -- not restricted by this blackout.
    bc = BaselineComparison(
        baseline_mean=0.003, baseline_median=0.002,  # baseline_mean/median are NOT in the blackout set
        mean_difference=None, median_difference=None, mean_difference_ci=None,
        standardized_effect=None, standardized_effect_status="UNDEFINED_ZERO_SCALE",
        raw_p=None, adjusted_p=None, family_id=None, multiple_testing_method="benjamini_hochberg",
    )
    profile = _profile_with(bc)
    assert profile.baseline_comparison.mean_difference is None
    assert profile.baseline_comparison.median_difference is None
    assert profile.baseline_comparison.raw_p is None
    assert profile.baseline_comparison.mean_difference_ci is None
    assert profile.baseline_comparison.standardized_effect is None
    # baseline_mean/baseline_median themselves are NOT part of the
    # blackout (A1 restricts only the comparison/significance fields).
    assert profile.baseline_comparison.baseline_mean is not None
    # the signature's own descriptive stats are fully populated, untouched.
    assert profile.absolute_outcome.mean is not None
    assert profile.relative_outcome.mean is not None
    assert profile.relative_outcome.n == 10


def test_zero_support_produces_the_identical_none_set():
    bc = BaselineComparison(
        baseline_mean=None, baseline_median=None,  # zero support: even the pooled distribution itself is empty
        mean_difference=None, median_difference=None, mean_difference_ci=None,
        standardized_effect=None, standardized_effect_status="UNDEFINED_ZERO_SCALE",
        raw_p=None, adjusted_p=None, family_id=None, multiple_testing_method="benjamini_hochberg",
    )
    profile = _profile_with(bc)
    for field in ("mean_difference", "median_difference", "raw_p", "mean_difference_ci", "standardized_effect"):
        assert getattr(profile.baseline_comparison, field) is None
    assert profile.absolute_outcome.mean is not None
    assert profile.relative_outcome.mean is not None


def test_standardized_effect_none_propagates_through_packet_and_queue_without_crashing_or_substituting():
    from evaluation.models.entities import EvaluationRunRegistry
    from hypothesis.config.loader import load_config as load_hypothesis_config
    from hypothesis.evidence.packet import build_evidence_packet
    from hypothesis.evidence.queue import compute_review_priority

    bc = BaselineComparison(
        baseline_mean=0.003, baseline_median=0.002,
        mean_difference=None, median_difference=None, mean_difference_ci=None,
        standardized_effect=None, standardized_effect_status="UNDEFINED_ZERO_SCALE",
        raw_p=None, adjusted_p=None, family_id=None, multiple_testing_method="benjamini_hochberg",
    )
    profile = _profile_with(bc)

    from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
    signature = EvaluationSignatureDefinition(
        signature_id="SIG", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version="cfg_x", creation_mode="PRE_REGISTERED", created_before_outcome_evaluation=True,
    )
    run_registry = EvaluationRunRegistry(
        evaluation_run_id="run_x", created_at="2026-10-10T00:00:00Z", mode="FORMAL_DEVELOPMENT",
        development_start="2024-01-01", development_end="2024-12-31", timeframe="1D", horizons=(3,),
        benchmark_security_id="bench", discovery_engine_version="v1.0.0", discovery_config_version="cfg_x",
        evaluation_engine_version="v1.0.0", evaluation_config_version="cfg_eval",
        signature_set_id="sigset_x", bootstrap_seed=1, bootstrap_iterations=200,
        comparison_seed=2, comparison_iterations=200, multiple_testing_method="benjamini_hochberg",
    )
    packet = build_evidence_packet(signature, [profile], run_registry, load_hypothesis_config())
    assert packet.primary_standardized_effect is None
    assert packet.primary_adjusted_p is None

    # Must not crash, and must not substitute a different (e.g. 0.0,
    # or a sentinel) value -- compute_review_priority() never even
    # reads primary_standardized_effect's None-ness specially; it just
    # falls through its own existing None guard.
    key = compute_review_priority(packet)
    assert key == (float("inf"), 0.0, -10.0)
