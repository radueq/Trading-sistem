"""TEST 8 -- Missing future data (Spec #003 SS21/SS57/SS66).

A horizon reaching past the end of available data (no development_end
wall involved) is INSUFFICIENT_FUTURE_DATA -- never a fabricated 0
return, never a silent drop.
"""
from evaluation.models.entities import OutcomeStatus
from evaluation.outcomes.forward_returns import compute_forward_outcome


class Bar:
    def __init__(self, date, close):
        self.date, self.split_adjusted_close = date, close


def test_insufficient_future_data_not_zero_not_dropped():
    bars = [Bar(f"2024-01-{d:02d}", 100.0 + d) for d in range(2, 6)]  # 4 bars only
    o = compute_forward_outcome("sid", bars, "2024-01-04", "1D", 5, None, "cfg_x")
    assert o.outcome_status == OutcomeStatus.INSUFFICIENT_FUTURE_DATA.value
    assert o.forward_return is None
    assert o.exit_reference_price is None
