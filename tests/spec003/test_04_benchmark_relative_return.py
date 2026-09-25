"""TEST 4 -- Benchmark-relative return (Spec #003 SS18/SS66).

AR_{i,t,h} = R_{i,t,h} - R_benchmark,t,h, hand-verified.
"""
import pytest

from evaluation.models.entities import OutcomeStatus
from evaluation.outcomes.benchmark import attach_benchmark_return
from evaluation.outcomes.forward_returns import compute_forward_outcome


class Bar:
    def __init__(self, date, close):
        self.date, self.split_adjusted_close = date, close


def test_relative_return_is_forward_minus_benchmark():
    bars = [Bar("2024-01-02", 100.0), Bar("2024-01-03", 110.0)]  # +10%
    bench = [Bar("2024-01-02", 200.0), Bar("2024-01-03", 204.0)]  # +2%

    o = compute_forward_outcome("sid", bars, "2024-01-02", "1D", 1, None, "cfg_x")
    ob = attach_benchmark_return(o, bench)

    assert ob.outcome_status == OutcomeStatus.VALID.value
    assert ob.forward_return == pytest.approx(0.10, rel=1e-12)
    assert ob.benchmark_return == pytest.approx(0.02, rel=1e-12)
    assert ob.relative_return == pytest.approx(0.08, rel=1e-9)
