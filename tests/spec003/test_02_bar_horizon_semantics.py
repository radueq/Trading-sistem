"""TEST 2 -- Bar-horizon semantics (Spec #003 SS3-4/SS66).

horizon_bars moves N POSITIONS in the security's own bar series, never
N calendar days -- proven with a deliberate calendar gap (a missing
weekday, as if from a holiday or halt) between two bars.
"""
from evaluation.outcomes.forward_returns import compute_forward_outcome
from evaluation.models.entities import OutcomeStatus


class Bar:
    def __init__(self, date, close):
        self.date, self.split_adjusted_close = date, close


def test_horizon_counts_bars_not_calendar_days():
    # A gap: 2024-01-04 is skipped entirely (as if a holiday) -- bar
    # positions are still contiguous 0..4, calendar days are not.
    bars = [
        Bar("2024-01-02", 100.0),
        Bar("2024-01-03", 101.0),
        Bar("2024-01-05", 102.0),  # would be +3 calendar days from 01-02
        Bar("2024-01-08", 103.0),
        Bar("2024-01-09", 104.0),
    ]
    o = compute_forward_outcome("sid", bars, "2024-01-02", "1D", 2, None, "cfg_x")
    assert o.outcome_status == OutcomeStatus.VALID.value
    # 2 BARS forward from 01-02 is bar index 2 = 2024-01-05 (close=102.0),
    # NOT "01-02 + 2 calendar days" (which would be 01-04, a date that
    # has no bar at all).
    assert o.exit_as_of == "2024-01-05"
    assert o.exit_reference_price == 102.0
