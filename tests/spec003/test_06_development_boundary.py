"""TEST 6 -- Development boundary (Spec #003 SS12/SS14/SS66).

An outcome whose horizon would need a bar dated after development_end
is CROSSES_LOCKED_OOS -- not computed, per Radu's worked example
(development_end=2025-12-31, observation=2025-12-29, horizon=5 bars).
"""
from evaluation.models.entities import OutcomeStatus
from evaluation.outcomes.forward_returns import compute_forward_outcome


class Bar:
    def __init__(self, date, close):
        self.date, self.split_adjusted_close = date, close


def test_exit_past_development_end_is_crosses_locked_oos():
    bars = [Bar(f"2025-12-{d:02d}", 100.0 + d) for d in range(24, 32)] + [
        Bar(f"2026-01-{d:02d}", 200.0 + d) for d in range(1, 5)
    ]
    o = compute_forward_outcome("sid", bars, "2025-12-29", "1D", 5, "2025-12-31", "cfg_x")
    assert o.outcome_status == OutcomeStatus.CROSSES_LOCKED_OOS.value
    assert o.development_end == "2025-12-31"


def test_exit_within_development_end_is_valid():
    bars = [Bar(f"2025-12-{d:02d}", 100.0 + d) for d in range(24, 32)]
    o = compute_forward_outcome("sid", bars, "2025-12-24", "1D", 5, "2025-12-31", "cfg_x")
    assert o.outcome_status == OutcomeStatus.VALID.value
    assert o.exit_as_of <= "2025-12-31"
