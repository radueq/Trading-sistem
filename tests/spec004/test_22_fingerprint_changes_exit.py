"""TEST 22 -- StrategyVariant fingerprint changes if the exit changes
(Spec #004 SS104-109 -- exit variance lives at the VARIANT level, so this
checks variant_definition_hash, not the parent hypothesis's hash)."""
from hypothesis.models.entities import ExitFamily, ExitHypothesis, ParameterSource
from hypothesis.registry.hypotheses import build_variant_id, variant_fingerprint


def test_variant_fingerprint_differs_when_time_exit_bars_changes():
    exit_2 = ExitHypothesis("TIME_EXIT", "ENTRY_BAR", "BAR_CLOSE", ParameterSource.EVIDENCE_DERIVED.value, time_exit_bars=2)
    exit_3 = ExitHypothesis("TIME_EXIT", "ENTRY_BAR", "BAR_CLOSE", ParameterSource.EVIDENCE_DERIVED.value, time_exit_bars=3)
    fp2 = variant_fingerprint("parent_hash_x", exit_2)
    fp3 = variant_fingerprint("parent_hash_x", exit_3)
    assert fp2 != fp3
    id2, h2 = build_variant_id(fp2)
    id3, h3 = build_variant_id(fp3)
    assert id2 != id3 and h2 != h3


def test_variant_fingerprint_differs_between_time_exit_and_signal_invalidation():
    time_exit = ExitHypothesis("TIME_EXIT", "ENTRY_BAR", "BAR_CLOSE", ParameterSource.EVIDENCE_DERIVED.value, time_exit_bars=3)
    invalidation = ExitHypothesis(
        "SIGNAL_INVALIDATION", "ENTRY_BAR", "BAR_CLOSE", ParameterSource.AGENT_PROPOSED.value, max_holding_bars=5,
    )
    assert variant_fingerprint("parent_hash_x", time_exit) != variant_fingerprint("parent_hash_x", invalidation)
