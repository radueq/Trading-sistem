"""TEST 5 -- Benchmark actual-date alignment, not DataFrame position
(Spec #003 SS19/SS66).

The security's and benchmark's bar lists have DIFFERENT lengths/offsets
-- alignment must go by DATE, never by list index, and a missing
benchmark bar at the needed date must produce MISSING_BENCHMARK, not a
silently wrong value from whatever happens to sit at that position.
"""
import pytest

from evaluation.models.entities import OutcomeStatus
from evaluation.outcomes.benchmark import attach_benchmark_return
from evaluation.outcomes.forward_returns import compute_forward_outcome


class Bar:
    def __init__(self, date, close):
        self.date, self.split_adjusted_close = date, close


def test_alignment_by_date_survives_positional_offset():
    # Security has an EXTRA bar at the start the benchmark doesn't --
    # positionally, security[1]/security[2] would NOT line up with
    # benchmark[0]/benchmark[1], but the actual DATES still match.
    bars = [Bar("2024-01-01", 50.0), Bar("2024-01-02", 100.0), Bar("2024-01-03", 105.0)]
    bench = [Bar("2024-01-02", 200.0), Bar("2024-01-03", 206.0)]

    o = compute_forward_outcome("sid", bars, "2024-01-02", "1D", 1, None, "cfg_x")
    ob = attach_benchmark_return(o, bench)
    assert ob.outcome_status == OutcomeStatus.VALID.value
    assert ob.benchmark_return == pytest.approx(206.0 / 200.0 - 1.0, rel=1e-12)


def test_missing_benchmark_bar_at_needed_date():
    bars = [Bar("2024-01-02", 100.0), Bar("2024-01-03", 105.0)]
    bench_missing_exit = [Bar("2024-01-02", 200.0)]  # no 01-03 bar

    o = compute_forward_outcome("sid", bars, "2024-01-02", "1D", 1, None, "cfg_x")
    ob = attach_benchmark_return(o, bench_missing_exit)
    assert ob.outcome_status == OutcomeStatus.MISSING_BENCHMARK.value
    assert ob.benchmark_return is None and ob.relative_return is None
