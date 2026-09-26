"""TEST 40 -- every hypothesis entity uses `timeframe`/`horizon_bars`-
style generic metadata, never a day-coupled field name -- Daily/4H-ready
by construction (Spec #004 SS68-69, mirrors Spec #003's own bar-based
discipline)."""
import dataclasses

from hypothesis.models.entities import EvidencePacket, EvidenceProvenance, ExitHypothesis, HorizonCandidateSet, StrategyDefinition, StrategyHypothesis

_FORBIDDEN_DAY_COUPLED_TOKENS = ("holding_days", "num_days", "day_count", "days_held")


def test_no_day_coupled_field_name_anywhere():
    for cls in (EvidencePacket, EvidenceProvenance, ExitHypothesis, HorizonCandidateSet, StrategyDefinition, StrategyHypothesis):
        for f in dataclasses.fields(cls):
            for token in _FORBIDDEN_DAY_COUPLED_TOKENS:
                assert token not in f.name.lower(), f"{cls.__name__}.{f.name} is day-coupled, not bar-based"


def test_horizon_unit_field_exists_and_is_bars():
    hs = HorizonCandidateSet(unit="BARS", values=(2, 3), selection_basis="x", parameter_source="PRE_SPECIFIED")
    assert hs.unit == "BARS"
