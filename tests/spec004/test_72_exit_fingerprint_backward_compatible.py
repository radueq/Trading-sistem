"""TEST 72 -- _exit_fp() (hypothesis/registry/hypotheses.py:91) fingerprint
compatibility, per Spec #005 Exit Amendment v1.0 (ACCEPTED) section 13,
regressions 1-2: the STOP_MANAGED_INVALIDATION branch is additive and
family-conditioned, so it must never fire for TIME_EXIT/SIGNAL_INVALIDATION
(byte-identical base string, same formula as before this patch), while two
STOP_MANAGED_INVALIDATION variants differing only by k get different ids."""
from hypothesis.models.entities import ExitFamily, ExitHypothesis, ParameterSource, StopLossRule
from hypothesis.registry.hypotheses import build_variant_id, variant_fingerprint


def test_time_exit_fingerprint_matches_the_pre_patch_formula_exactly():
    ex = ExitHypothesis(
        exit_family=ExitFamily.TIME_EXIT.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.EVIDENCE_DERIVED.value, time_exit_bars=3,
    )
    fp = variant_fingerprint("parent_hash_x", ex)
    # Hand-derived from the documented pre-patch formula: f"{exit_family}::
    # {horizon_reference_point}::{exit_execution_policy}::{time_exit_bars}::
    # {inv}::{max_holding_bars}::{parameter_source}" with inv="" (no
    # invalidation_conditions) and max_holding_bars=None -- no
    # STOP_MANAGED_INVALIDATION suffix, ever, for this family.
    assert fp == "parent_hash_x::TIME_EXIT::ENTRY_BAR::BAR_CLOSE::3::::None::EVIDENCE_DERIVED"


def test_signal_invalidation_fingerprint_matches_the_pre_patch_formula_exactly():
    from hypothesis.models.entities import InvalidationCondition
    ex = ExitHypothesis(
        exit_family=ExitFamily.SIGNAL_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        max_holding_bars=5,
        invalidation_conditions=(InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),),
    )
    fp = variant_fingerprint("parent_hash_x", ex)
    assert fp == (
        "parent_hash_x::SIGNAL_INVALIDATION::ENTRY_BAR::BAR_CLOSE::None::"
        "LANE:relative_strength:HIGH,VERY_HIGH::5::AGENT_PROPOSED"
    )


def test_two_stop_managed_variants_differing_only_by_k_get_different_ids():
    from hypothesis.models.entities import InvalidationCondition
    inv = (InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),)
    exit_k2 = ExitHypothesis(
        exit_family=ExitFamily.STOP_MANAGED_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=inv, stop_loss=StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=2.0),
    )
    exit_k3 = ExitHypothesis(
        exit_family=ExitFamily.STOP_MANAGED_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=inv, stop_loss=StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=3.0),
    )
    fp2 = variant_fingerprint("parent_hash_x", exit_k2)
    fp3 = variant_fingerprint("parent_hash_x", exit_k3)
    assert fp2 != fp3
    id2, h2 = build_variant_id(fp2)
    id3, h3 = build_variant_id(fp3)
    assert id2 != id3 and h2 != h3


def test_stop_managed_fingerprint_includes_partial_profit_presence_and_absence_distinctly():
    from hypothesis.models.entities import InvalidationCondition, PartialProfitRule
    inv = (InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),)
    control = ExitHypothesis(
        exit_family=ExitFamily.STOP_MANAGED_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=inv, stop_loss=StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=2.0),
    )
    partial = ExitHypothesis(
        exit_family=ExitFamily.STOP_MANAGED_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=inv, stop_loss=StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=2.0),
        partial_profit=PartialProfitRule(r_multiple=2.0, fraction=0.5),
    )
    fp_control = variant_fingerprint("parent_hash_x", control)
    fp_partial = variant_fingerprint("parent_hash_x", partial)
    assert fp_control != fp_partial
    assert fp_control.endswith("::NO_PARTIAL_PROFIT")
    assert fp_partial.endswith("::2.0:0.5")
