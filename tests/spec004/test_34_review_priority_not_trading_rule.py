"""TEST 34 -- review_priority (and the fields it's derived from) is never
part of a trading rule: it lives only on ResearchQueueEntry, never on
StrategyDefinition/EntryDefinition/ExitHypothesis (Spec #004 SS61-62)."""
import dataclasses

from hypothesis.evidence.queue import build_research_queue
from hypothesis.models.entities import EntryDefinition, ExitHypothesis, StrategyDefinition


def test_no_priority_field_on_runtime_trading_structures():
    for cls in (StrategyDefinition, EntryDefinition, ExitHypothesis):
        for f in dataclasses.fields(cls):
            assert "priority" not in f.name.lower(), f"{cls.__name__}.{f.name} must never carry review priority"


def test_research_queue_entries_never_reference_a_strategy_definition_field(profiles_all_horizons, hypothesis_config):
    entries = build_research_queue(profiles_all_horizons, "run_x", hypothesis_config)
    strategy_field_names = {f.name for f in dataclasses.fields(StrategyDefinition)}
    entry_field_names = {f.name for f in dataclasses.fields(type(entries[0]))}
    assert not (strategy_field_names & entry_field_names), "ResearchQueueEntry must share no fields with StrategyDefinition"
