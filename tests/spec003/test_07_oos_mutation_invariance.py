"""TEST 7 -- OOS mutation invariance (Spec #003 SS12/SS66).

Mutating a bar's price/volume BEYOND development_end must never change
a CROSSES_LOCKED_OOS outcome -- the exit bar's price is never read on
that path, only its date (see outcomes/forward_returns.py docstring).
Mirrors Spec #001 TEST 9 / Spec #002 TEST 2's own look-ahead-immunity
pattern, applied to the Locked-OOS wall instead of `as_of`.
"""
from evaluation.outcomes.forward_returns import compute_forward_outcome


class Bar:
    def __init__(self, date, close):
        self.date, self.split_adjusted_close = date, close


def test_mutating_oos_price_does_not_change_outcome():
    dev_end = "2025-12-31"
    base_bars = [Bar(f"2025-12-{d:02d}", 100.0 + d) for d in range(24, 32)] + [
        Bar("2026-01-02", 999.0), Bar("2026-01-03", 999.0),
    ]
    mutated_bars = [Bar(f"2025-12-{d:02d}", 100.0 + d) for d in range(24, 32)] + [
        Bar("2026-01-02", -12345.0), Bar("2026-01-03", 0.01),
    ]

    o1 = compute_forward_outcome("sid", base_bars, "2025-12-29", "1D", 3, dev_end, "cfg_x")
    o2 = compute_forward_outcome("sid", mutated_bars, "2025-12-29", "1D", 3, dev_end, "cfg_x")

    assert o1.outcome_status == o2.outcome_status == "CROSSES_LOCKED_OOS"
    assert o1 == o2, "mutating a value beyond development_end must never change the outcome"
