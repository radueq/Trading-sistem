"""TEST 51 -- every ResearchQueueEntry with a populated review_priority_key
carries priority_basis="DEVELOPMENT_OUTCOME_AWARE_SELECTION" permanently,
and this never enters a StrategyDefinition (Radu's SS110-H guard)."""
import dataclasses

from hypothesis.evidence.queue import PRIORITY_BASIS_NOT_APPLICABLE, PRIORITY_BASIS_OUTCOME_AWARE, build_research_queue
from hypothesis.models.entities import StrategyDefinition


def test_every_ranked_entry_carries_the_outcome_aware_label(profiles_all_horizons, hypothesis_config):
    entries = build_research_queue(profiles_all_horizons, "run_x", hypothesis_config)
    for e in entries:
        if e.review_priority_key is not None:
            assert e.priority_basis == PRIORITY_BASIS_OUTCOME_AWARE
        else:
            assert e.priority_basis == PRIORITY_BASIS_NOT_APPLICABLE


def test_priority_basis_constant_never_appears_as_a_strategy_definition_field():
    field_names = {f.name for f in dataclasses.fields(StrategyDefinition)}
    assert "priority_basis" not in field_names
    assert "review_priority_rank" not in field_names
    assert "review_priority_key" not in field_names
