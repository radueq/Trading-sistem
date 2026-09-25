"""TEST 17 -- no ATR-multiplier/optimized-stop field exists anywhere on
ExitHypothesis or StrategyDefinition (Spec #004 SS23/SS79 -- structural,
not just a config flag)."""
import dataclasses

from hypothesis.models.entities import ExitHypothesis, StrategyDefinition

_FORBIDDEN_TOKENS = ("atr", "trailing", "stop_loss", "take_profit", "kelly")


def test_no_risk_parameter_fields_on_exit_hypothesis():
    for f in dataclasses.fields(ExitHypothesis):
        for token in _FORBIDDEN_TOKENS:
            assert token not in f.name.lower(), f"ExitHypothesis.{f.name} looks like a risk-exit parameter"


def test_no_risk_parameter_fields_on_strategy_definition():
    for f in dataclasses.fields(StrategyDefinition):
        for token in _FORBIDDEN_TOKENS:
            assert token not in f.name.lower(), f"StrategyDefinition.{f.name} looks like a risk-exit parameter"
