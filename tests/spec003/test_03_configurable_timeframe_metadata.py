"""TEST 3 -- Configurable timeframe metadata (Spec #003 SS3-4/SS66).

No outcome structure hardcodes "DAYS" internally -- `timeframe` +
`horizon_bars` is the whole contract (e.g. ForwardOutcome(timeframe="1D",
horizon_bars=5), never a field like forward_return_5d).
"""
import dataclasses

from evaluation.models.entities import EvidenceProfile, ForwardOutcome

_ALLOWED_DAY_SUBSTRINGS = {"horizon_bars"}  # "bars", not "days" -- the one allowed exception


def _assert_no_day_coupled_field_names(cls):
    for f in dataclasses.fields(cls):
        name = f.name
        if name in _ALLOWED_DAY_SUBSTRINGS:
            continue
        assert "_day" not in name and "day_" not in name and name != "days", (
            f"{cls.__name__}.{name} is a day-coupled field name -- Spec #003 SS3-4 forbids hardcoding "
            "a calendar-day unit into the outcome contract; use timeframe + horizon_bars instead"
        )


def test_forward_outcome_has_timeframe_and_horizon_bars_not_hardcoded_days():
    fields = {f.name for f in dataclasses.fields(ForwardOutcome)}
    assert "timeframe" in fields
    assert "horizon_bars" in fields
    _assert_no_day_coupled_field_names(ForwardOutcome)


def test_evidence_profile_has_timeframe_and_horizon_bars_not_hardcoded_days():
    fields = {f.name for f in dataclasses.fields(EvidenceProfile)}
    assert "timeframe" in fields
    assert "horizon_bars" in fields
    _assert_no_day_coupled_field_names(EvidenceProfile)
