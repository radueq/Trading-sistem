"""TEST 60 -- `variant_tag` (BASELINE_VARIANT vs EXPERIMENTAL_VARIANT) is
never deduced from `min(horizon)` (PATCH #004-A finding #5, GPT Review
#004 Round 1: "nu rezulta metodologic ca cel mai scurt horizon trebuie sa
fie controlul principal"). By default every TIME_EXIT variant is
EXPERIMENTAL_VARIANT; a caller may EXPLICITLY pre-designate exactly one
horizon as the baseline via `baseline_time_exit_bars`."""
import pytest

from hypothesis.models.entities import VariantTag
from hypothesis.registry.hypotheses import materialize_variants

from spec004.conftest import build_preregistered_hypothesis_for_test


def test_default_materialization_tags_nothing_as_baseline(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    hyp, variants, _ = build_preregistered_hypothesis_for_test(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config)
    time_exit_variants = [v for v in variants if v.exit_hypothesis.exit_family == "TIME_EXIT"]
    assert time_exit_variants
    for v in time_exit_variants:
        assert v.variant_tag == VariantTag.EXPERIMENTAL_VARIANT.value
    # in particular, the SHORTEST horizon (2 bars) is NOT auto-tagged baseline:
    shortest = min(time_exit_variants, key=lambda v: v.exit_hypothesis.time_exit_bars)
    assert shortest.variant_tag == VariantTag.EXPERIMENTAL_VARIANT.value


def test_explicit_baseline_time_exit_bars_tags_exactly_that_one(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    hyp, variants, _ = build_preregistered_hypothesis_for_test(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config, baseline_time_exit_bars=5,
    )
    time_exit_variants = [v for v in variants if v.exit_hypothesis.exit_family == "TIME_EXIT"]
    baseline = [v for v in time_exit_variants if v.variant_tag == VariantTag.BASELINE_VARIANT.value]
    assert len(baseline) == 1
    assert baseline[0].exit_hypothesis.time_exit_bars == 5
    for v in time_exit_variants:
        if v.exit_hypothesis.time_exit_bars != 5:
            assert v.variant_tag == VariantTag.EXPERIMENTAL_VARIANT.value


def test_baseline_time_exit_bars_must_be_one_of_the_candidate_values(horizon_candidates):
    from hypothesis.models.entities import Direction, HypothesisComplexitySnapshot, HypothesisProvenance, HypothesisResearchMode, HypothesisStatus, StrategyHypothesis
    from hypothesis.registry.hypotheses import build_hypothesis_id, hypothesis_fingerprint

    # horizon_candidates.values == (2,3,5); 4 is not one of them.
    import hypothesis.models.entities as ent
    from hypothesis.models.entities import EvidenceProvenance
    ev = EvidenceProvenance("run_x", "v1.0.0", "cfg_eval", "SIG_X", "sigset_x", "v1.0.0", "cfg_disc", "1D")
    entry = ent.EntryDefinition(core_conditions=(ent.LaneStateCondition("volatility", "COMPRESSION"),))
    fp = hypothesis_fingerprint("SIG_X", "LONG", entry, "NEXT_BAR_OPEN", horizon_candidates, ev, "cfg_hyp")
    hid, dh = build_hypothesis_id(fp)
    parent = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.DRAFT.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id="SIG_X",
        signature_set_id="sigset_x", direction="LONG", direction_basis="EVIDENCE_SIGN",
        entry_definition=entry, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizon_candidates,
        variant_ids=(), evidence_provenance=ev,
        hypothesis_provenance=HypothesisProvenance("HUMAN:radu", None, None, "radu", "t"),
        constraints=HypothesisComplexitySnapshot(3, 1, "cfg_hyp"),
        created_at="t", created_by="radu", strategy_config_version="cfg_hyp",
    )
    with pytest.raises(ValueError, match="not one of the candidate values"):
        materialize_variants(parent, created_at="t", baseline_time_exit_bars=4)
