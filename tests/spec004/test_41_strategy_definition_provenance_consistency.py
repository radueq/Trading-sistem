"""TEST 41 -- a StrategyDefinition's provenance stays traceable to its
hypothesis (Spec #004 SS63/SS70-71: source_feature_or_state/source_engine
provenance discipline)."""
from hypothesis.registry.strategy_registry import build_strategy_definition

from spec004.conftest import build_preregistered_hypothesis_for_test


def test_strategy_definition_traces_back_to_its_hypothesis_and_variant(entry_definition, horizon_candidates, evidence_provenance, hypothesis_config):
    hyp, variants, registry = build_preregistered_hypothesis_for_test(
        entry_definition, horizon_candidates, evidence_provenance, hypothesis_config,
    )

    for v in variants:
        sd = build_strategy_definition(hyp, v, registry)
        assert sd.hypothesis_id == hyp.hypothesis_id
        assert sd.strategy_variant_id == v.strategy_variant_id
        assert sd.timeframe == evidence_provenance.timeframe
        assert sd.direction == hyp.direction
        assert sd.exit_definition == v.exit_hypothesis
