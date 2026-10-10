"""TEST 56 -- F6, `family_test_count` (joint remediation design 003+004
section 9; decision registry F6, Stage 4).

SS44 named `family_test_count` in `BaselineComparison`'s required
field list; the field existed nowhere in `src/` or `tests/` before this
round. `family_test_count` is non-`None` if and only if `mode ==
"FORMAL_DEVELOPMENT"` AND this profile's own `raw_p is not None` --
independent of `support_status` (`stratified_permutation_p_value()`
and the support-sufficiency check are two separate mechanisms).
"""
from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set
from fixtures.config_overrides import evaluation_config_with_overrides

from spec003.conftest import COMPRESSION_WINDOW_END, COMPRESSION_WINDOW_START


def _sig(sid, discovery_config_version):
    return EvaluationSignatureDefinition(
        signature_id=sid, lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=discovery_config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )


def test_family_test_count_equals_the_real_family_size_multi_signature(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    # Two DIFFERENT signatures, IDENTICAL lane_conditions -- both match
    # the SAME underlying observations, so both share the SAME raw_p-or
    # -None status at every horizon; wherever raw_p is populated, the
    # real family at that horizon has exactly 2 members.
    sig_a = _sig("COMPRESSION_A", reduced_discovery_config.config_version)
    sig_b = _sig("COMPRESSION_B", reduced_discovery_config.config_version)
    sigset = freeze_signature_set([sig_a, sig_b])
    profiles, registry = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, fast_evaluation_config,
        calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id,
    )
    assert registry.mode == "FORMAL_DEVELOPMENT"
    populated = [p for p in profiles if p.baseline_comparison.raw_p is not None]
    assert populated, "sanity: need at least one profile with a real raw_p to test family_test_count against"
    for p in populated:
        assert p.baseline_comparison.family_test_count == 2, (
            f"signature={p.signature_id!r} horizon={p.horizon_bars!r}: expected family_test_count=2 "
            f"(both signatures share identical conditions), got {p.baseline_comparison.family_test_count!r}"
        )
    for p in profiles:
        if p.baseline_comparison.raw_p is None:
            assert p.baseline_comparison.family_test_count is None


def test_family_test_count_is_none_in_exploratory_mode_even_with_real_raw_p(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    exploratory_cfg = evaluation_config_with_overrides(
        evaluation_mode="EXPLORATORY",
        support=fast_evaluation_config.data["support"],
        bootstrap=fast_evaluation_config.data["bootstrap"],
        comparison=fast_evaluation_config.data["comparison"],
        stability=fast_evaluation_config.data["stability"],
    )
    sig = _sig("COMPRESSION_EXPLORATORY", reduced_discovery_config.config_version)
    sigset = freeze_signature_set([sig])
    profiles, registry = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, exploratory_cfg,
        calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id,
    )
    assert registry.mode == "EXPLORATORY"
    assert any(p.baseline_comparison.raw_p is not None for p in profiles), (
        "sanity: need at least one profile with non-None raw_p to prove family_test_count "
        "stays None despite it (not just None-because-raw_p-is-None too)"
    )
    for p in profiles:
        assert p.baseline_comparison.family_test_count is None


def test_family_test_count_populated_for_insufficient_support_profile_demonstrating_independence(
    conn, tiny_universe, reduced_discovery_config, fast_evaluation_config, formal_calendar_registry, formal_calendar_id,
):
    # An artificially inflated support threshold forces EVERY profile
    # to INSUFFICIENT_SUPPORT, while leaving stratified_permutation_p_
    # value()'s own (much looser) non-emptiness requirement unaffected
    # -- proving family_test_count depends only on raw_p, never on
    # support_status.
    strict_support_cfg = evaluation_config_with_overrides(
        support={"minimum_episode_count": 10_000, "minimum_unique_securities": 10_000},
        bootstrap=fast_evaluation_config.data["bootstrap"],
        comparison=fast_evaluation_config.data["comparison"],
        stability=fast_evaluation_config.data["stability"],
    )
    sig = _sig("COMPRESSION_INSUFFICIENT", reduced_discovery_config.config_version)
    sigset = freeze_signature_set([sig])
    profiles, registry = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        COMPRESSION_WINDOW_START, COMPRESSION_WINDOW_END, sigset, reduced_discovery_config, strict_support_cfg,
        calendar_registry=formal_calendar_registry, calendar_id=formal_calendar_id,
    )
    assert all(p.support.support_status == "INSUFFICIENT" for p in profiles), (
        "sanity: the inflated threshold must force INSUFFICIENT_SUPPORT on every profile"
    )
    insufficient_with_raw_p = [p for p in profiles if p.baseline_comparison.raw_p is not None]
    assert insufficient_with_raw_p, (
        "sanity: need at least one INSUFFICIENT_SUPPORT profile with a real raw_p to demonstrate "
        "the two mechanisms are independent"
    )
    for p in insufficient_with_raw_p:
        assert p.baseline_comparison.family_test_count is not None
