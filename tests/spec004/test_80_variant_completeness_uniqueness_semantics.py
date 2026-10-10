"""TEST 80 -- Stage 6, Finding 15 (GPT-G2) complete contract, plus
decision registry H1 (Finding 10), whose own verification is "covered by
Finding 15's own variant-uniqueness test matrix".

Finding 15, at `validate_for_preregistration()`:
(i)   exactly one TIME_EXIT variant per `horizon_candidate_set.values`
      entry -- BOTH directions of incompleteness (missing AND extra), and
      no repeat;
(ii)  any number of SIGNAL_INVALIDATION/STOP_MANAGED_INVALIDATION
      variants, each unique by its FULL `variant_fingerprint()` -- two
      differing only in `max_holding_bars` are distinct and both allowed,
      an exact repeat is rejected;
(iii) at least one invalid exit-semantics case per field:
      `time_exit_bars` sign, `horizon_reference_point`,
      `exit_execution_policy`.
H1, at `validate_proposal()`: exit families counted by distinct TYPE
(mandatory TIME_EXIT included), never by raw entries.
"""
import dataclasses

import pytest

from hypothesis.models.entities import ExitFamily, ExitHypothesis, InvalidationCondition, VariantTag
from hypothesis.proposals.validator import validate_proposal
from hypothesis.registry.hypotheses import HypothesisRegistry, build_variant
from hypothesis.validation.rules import validate_for_preregistration

from spec004.conftest import make_proposal_raw
from spec004.gate_inputs import draft_from_proposal, make_proposal, set_variant_ids, with_variants

_SI = ExitHypothesis(
    exit_family=ExitFamily.SIGNAL_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
    exit_execution_policy="BAR_CLOSE", parameter_source="EVIDENCE_DERIVED", max_holding_bars=5,
    invalidation_conditions=(InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),),
)


def _time_exit(bars, **kw):
    return ExitHypothesis(
        exit_family=ExitFamily.TIME_EXIT.value, horizon_reference_point=kw.pop("horizon_reference_point", "ENTRY_BAR"),
        exit_execution_policy=kw.pop("exit_execution_policy", "BAR_CLOSE"), parameter_source="PRE_SPECIFIED",
        time_exit_bars=bars, **kw,
    )


def _validate(draft, variants, hypothesis_config, run_registry):
    hyp = set_variant_ids(draft, variants)
    return validate_for_preregistration(hyp, tuple(variants), HypothesisRegistry(), hypothesis_config.data, run_registry)


def _base(hypothesis_config):
    proposal = make_proposal()
    draft = draft_from_proposal(proposal, hypothesis_config)
    _, variants = with_variants(draft, proposal)
    return draft, list(variants)


def test_the_unperturbed_family_is_valid(hypothesis_config, run_registry):
    draft, variants = _base(hypothesis_config)
    assert _validate(draft, variants, hypothesis_config, run_registry) == (True, ())


def test_a_missing_time_exit_variant_is_rejected(hypothesis_config, run_registry):
    draft, variants = _base(hypothesis_config)
    variants = [v for v in variants if v.exit_hypothesis.time_exit_bars != 5]
    ok, errors = _validate(draft, variants, hypothesis_config, run_registry)
    assert not ok and any("no TIME_EXIT variant for horizon_candidate_set value(s) [5]" in e for e in errors), errors


def test_an_extra_time_exit_variant_outside_the_candidate_set_is_rejected(hypothesis_config, run_registry):
    draft, variants = _base(hypothesis_config)
    variants.append(build_variant(draft, _time_exit(7), VariantTag.EXPERIMENTAL_VARIANT.value, "t"))
    ok, errors = _validate(draft, variants, hypothesis_config, run_registry)
    assert not ok and any("TIME_EXIT variant(s) for time_exit_bars [7] not in horizon_candidate_set.values" in e for e in errors), errors


def test_a_repeated_time_exit_variant_is_rejected(hypothesis_config, run_registry):
    draft, variants = _base(hypothesis_config)
    three = next(v for v in variants if v.exit_hypothesis.time_exit_bars == 3)
    variants.append(dataclasses.replace(three, created_at="later"))
    ok, errors = _validate(draft, variants, hypothesis_config, run_registry)
    assert not ok
    assert any("more than one TIME_EXIT variant for time_exit_bars [3]" in e for e in errors), errors
    assert any("occur more than once in this batch" in e for e in errors), errors


def test_two_signal_invalidation_variants_differing_only_in_max_holding_bars_are_both_allowed(hypothesis_config, run_registry):
    """(ii) + the original key-collapse bug named in the design: an
    `(exit_family, invalidation_conditions)` key would have collapsed
    these two; the full-content fingerprint keeps them distinct."""
    draft, variants = _base(hypothesis_config)
    variants.append(build_variant(draft, dataclasses.replace(_SI, max_holding_bars=3), VariantTag.EXPERIMENTAL_VARIANT.value, "t"))
    assert _validate(draft, variants, hypothesis_config, run_registry) == (True, ())


def test_an_exact_repeat_of_a_signal_invalidation_variant_is_rejected(hypothesis_config, run_registry):
    draft, variants = _base(hypothesis_config)
    si_variant = next(v for v in variants if v.exit_hypothesis.exit_family == ExitFamily.SIGNAL_INVALIDATION.value)
    variants.append(si_variant)
    ok, errors = _validate(draft, variants, hypothesis_config, run_registry)
    assert not ok and any("occur more than once in this batch" in e for e in errors), errors


@pytest.mark.parametrize("bad_bars", [-3, 0, True, 2.0])
def test_a_time_exit_with_non_positive_or_non_integer_bars_is_rejected(bad_bars, hypothesis_config, run_registry):
    draft, variants = _base(hypothesis_config)
    two = next(v for v in variants if v.exit_hypothesis.time_exit_bars == 2)
    variants[variants.index(two)] = build_variant(draft, _time_exit(bad_bars), two.variant_tag, "t")
    ok, errors = _validate(draft, variants, hypothesis_config, run_registry)
    assert not ok and any(f"TIME_EXIT time_exit_bars={bad_bars!r} must be a positive integer" in e for e in errors), errors


def test_a_wrong_horizon_reference_point_is_rejected(hypothesis_config, run_registry):
    draft, variants = _base(hypothesis_config)
    two = next(v for v in variants if v.exit_hypothesis.time_exit_bars == 2)
    variants[variants.index(two)] = build_variant(draft, _time_exit(2, horizon_reference_point="SIGNAL_BAR"), two.variant_tag, "t")
    ok, errors = _validate(draft, variants, hypothesis_config, run_registry)
    assert not ok and any("horizon_reference_point='SIGNAL_BAR', must be 'ENTRY_BAR'" in e for e in errors), errors


def test_a_wrong_exit_execution_policy_is_rejected(hypothesis_config, run_registry):
    draft, variants = _base(hypothesis_config)
    si_variant = next(v for v in variants if v.exit_hypothesis.exit_family == ExitFamily.SIGNAL_INVALIDATION.value)
    variants[variants.index(si_variant)] = build_variant(
        draft, dataclasses.replace(_SI, exit_execution_policy="NEXT_BAR_OPEN"), si_variant.variant_tag, "t",
    )
    ok, errors = _validate(draft, variants, hypothesis_config, run_registry)
    assert not ok and any("exit_execution_policy='NEXT_BAR_OPEN', must be 'BAR_CLOSE'" in e for e in errors), errors


# -- H1 (Finding 10): count by distinct exit-family TYPE --------------------

def _si_raw(**kw):
    return {**make_proposal_raw()["exit_hypotheses"][0], **kw}


def _smi_raw():
    return {
        "exit_family": "STOP_MANAGED_INVALIDATION", "horizon_reference_point": "ENTRY_BAR",
        "exit_execution_policy": "BAR_CLOSE", "parameter_source": "AGENT_PROPOSED",
        "invalidation_conditions": [{"lane": "relative_strength", "holds_labels": ["HIGH", "VERY_HIGH"]}],
        "stop_loss": {"basis": "ATR_TRAILING_V1", "atr_multiple": 2.0},
    }


def test_two_exits_of_one_type_count_as_one_family_type(discovery_config, hypothesis_config):
    """The pre-Stage-6 raw-entry count refused this (TIME_EXIT +
    2 x SIGNAL_INVALIDATION = 2 TYPES, within max_exit_families_per_
    hypothesis=2)."""
    proposal = make_proposal(exit_hypotheses=[_si_raw(), _si_raw(max_holding_bars=3)])
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert result.valid, result.errors


def test_three_distinct_types_still_exceed_the_family_limit(discovery_config, hypothesis_config):
    proposal = make_proposal(exit_hypotheses=[_si_raw(), _smi_raw()])
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("3 distinct exit-family types" in e and "max_exit_families_per_hypothesis=2" in e for e in result.errors), result.errors


def test_total_variant_count_still_bounds_many_exits_of_one_type(discovery_config, hypothesis_config):
    """Counting by TYPE does not unbound the family: 3 TIME_EXIT + 4
    SIGNAL_INVALIDATION = 7 variants > max_variants_per_family=6."""
    proposal = make_proposal(exit_hypotheses=[_si_raw(max_holding_bars=b) for b in (2, 3, 4, 5)])
    result = validate_proposal(proposal, discovery_config, hypothesis_config)
    assert not result.valid
    assert any("total variant count 7 exceeds max_variants_per_family=6" in e for e in result.errors), result.errors
    assert not any("distinct exit-family types" in e for e in result.errors)


def test_stop_managed_exit_alone_with_time_exit_is_two_types(discovery_config, hypothesis_config):
    proposal = make_proposal(exit_hypotheses=[_smi_raw()])
    assert validate_proposal(proposal, discovery_config, hypothesis_config).valid
