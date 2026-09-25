"""TEST 1 -- Forward return arithmetic (Spec #003 SS66/SS15).

Manual 1/2/3/5/10-bar R_{i,t,h} = P(t+h)/P(t) - 1 on a hand-built series.
"""
import pytest

from evaluation.models.entities import OutcomeStatus
from evaluation.outcomes.forward_returns import compute_forward_outcome


class Bar:
    def __init__(self, date, close):
        self.date, self.split_adjusted_close = date, close


def test_forward_return_matches_hand_computation():
    closes = [100.0, 101.0, 103.0, 99.0, 105.0, 110.0, 108.0, 112.0, 115.0, 120.0, 118.0]
    bars = [Bar(f"2024-01-{d:02d}", c) for d, c in zip(range(2, 2 + len(closes)), closes)]
    t0 = bars[0].date  # 2024-01-02, close=100.0

    for h, expected_close in [(1, 101.0), (2, 103.0), (3, 99.0), (5, 110.0), (10, 118.0)]:
        o = compute_forward_outcome("sid", bars, t0, "1D", h, None, "cfg_x")
        assert o.outcome_status == OutcomeStatus.VALID.value
        assert o.entry_reference_price == 100.0
        assert o.exit_reference_price == expected_close
        assert o.forward_return == pytest.approx(expected_close / 100.0 - 1.0, rel=1e-12)
        assert o.horizon_bars == h
