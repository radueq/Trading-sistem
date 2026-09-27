"""TEST 17 -- no ATR-multiplier/optimized-stop field exists anywhere on
ExitHypothesis or StrategyDefinition, beyond the two named exceptions
PATCH #004-C explicitly approved (Spec #004 SS23/SS79-81 -- structural,
not just a config flag). Spec #005 Exit Amendment v1.0 (docs/spec005_
exit_amendment_v1.0.md, ACCEPTED, section 1) carries a STRICT, NARROW
derogation from this guard: it authorizes exactly `stop_loss`/
`partial_profit` on `ExitHypothesis`, and only there -- `StrategyDefinition`
gets no exception at all, and no other field name on either dataclass is
permitted to match a forbidden token. This test is UPDATED, not removed,
per Radu's explicit instruction: the exception is enumerated exhaustively
below, never a loosened pattern."""
import dataclasses

from hypothesis.models.entities import ExitHypothesis, StrategyDefinition

_FORBIDDEN_TOKENS = ("atr", "trailing", "stop_loss", "take_profit", "kelly")

# PATCH #004-C / Spec #005 Exit Amendment v1.0 (ACCEPTED) -- the ONLY two
# field names exempted from the scan below, and ONLY on ExitHypothesis.
_APPROVED_EXIT_HYPOTHESIS_EXCEPTIONS = frozenset({"stop_loss", "partial_profit"})


def test_no_risk_parameter_fields_on_exit_hypothesis():
    for f in dataclasses.fields(ExitHypothesis):
        if f.name in _APPROVED_EXIT_HYPOTHESIS_EXCEPTIONS:
            continue
        for token in _FORBIDDEN_TOKENS:
            assert token not in f.name.lower(), f"ExitHypothesis.{f.name} looks like a risk-exit parameter"


def test_exit_hypothesis_exception_is_exactly_the_two_approved_fields_no_more():
    """Guards against the exception widening silently: confirms every
    ExitHypothesis field name that matches a forbidden token is one of the
    two APPROVED exceptions -- never a third, unapproved field added under
    cover of this derogation (Radu's explicit review requirement). Not an
    equality check: `partial_profit` happens to match no forbidden token
    today (it is exempted defensively anyway, in case the token list ever
    grows), but any match outside the approved set must still fail here."""
    matching_forbidden = {
        f.name for f in dataclasses.fields(ExitHypothesis)
        if any(token in f.name.lower() for token in _FORBIDDEN_TOKENS)
    }
    assert matching_forbidden <= _APPROVED_EXIT_HYPOTHESIS_EXCEPTIONS, (
        f"expected only {_APPROVED_EXIT_HYPOTHESIS_EXCEPTIONS} to match a forbidden token on "
        f"ExitHypothesis, got {matching_forbidden} -- an unapproved risk-exit field may have been added"
    )
    field_names = {f.name for f in dataclasses.fields(ExitHypothesis)}
    assert _APPROVED_EXIT_HYPOTHESIS_EXCEPTIONS <= field_names


def test_no_risk_parameter_fields_on_strategy_definition():
    """Unchanged: StrategyDefinition gets NO exception at all -- the
    SS79-81 derogation is scoped exclusively to ExitHypothesis.stop_loss/
    partial_profit (Spec #005 Exit Amendment v1.0 section 1), never
    extended to this dataclass."""
    for f in dataclasses.fields(StrategyDefinition):
        for token in _FORBIDDEN_TOKENS:
            assert token not in f.name.lower(), f"StrategyDefinition.{f.name} looks like a risk-exit parameter"
