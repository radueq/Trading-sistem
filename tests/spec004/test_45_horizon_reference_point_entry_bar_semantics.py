"""TEST 45 -- horizon_reference_point=ENTRY_BAR exact bar-counting
semantics, per Radu's SS110-A worked example (2026-09-25):

    Signal: Monday close
    Entry: Tuesday open
    Holding bar 1 = Tuesday, holding bar 2 = Wednesday, holding bar 3 = Thursday
    TIME_EXIT 3 -> exit at Thursday close

I.e. TIME_EXIT N means: exit at the close of the bar whose index is
(entry_bar_index + N - 1), counted from the ENTRY bar (index 0), NOT from
the signal bar. This is a full bar different from Spec #003's OWN
`horizon_bars` semantics (close(signal) -> close(signal+h)) -- the two
number lines (`evidence_horizon_bars` vs `strategy_holding_bars`) must
never be silently treated as the same quantity by #005.
"""
from hypothesis.models.entities import HORIZON_REFERENCE_POINT


def test_horizon_reference_point_constant_is_entry_bar():
    assert HORIZON_REFERENCE_POINT == "ENTRY_BAR"


def test_worked_example_bar_index_arithmetic_matches_radus_example():
    # A tiny bar calendar: Mon=0 (signal), Tue=1 (entry/holding bar 1),
    # Wed=2 (holding bar 2), Thu=3 (holding bar 3), Fri=4.
    calendar = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    signal_index = 0  # Monday close
    entry_index = signal_index + 1  # Tuesday open -- NEXT_BAR_OPEN

    def exit_index_for_time_exit(entry_idx: int, n_bars: int) -> int:
        """TIME_EXIT N: exit at the close of holding bar N, where holding
        bar 1 IS the entry bar itself (entry_idx + 0), so holding bar N is
        entry_idx + (N - 1)."""
        return entry_idx + (n_bars - 1)

    exit_index = exit_index_for_time_exit(entry_index, n_bars=3)
    assert calendar[exit_index] == "Thu"

    # Contrast with Spec #003's OWN horizon_bars semantics, counted from
    # the SIGNAL bar: close(signal) -> close(signal + h). For h=3 that
    # would land on Thursday too by coincidence only because entry is
    # exactly 1 bar after signal -- the two formulas are NOT the same
    # function of N in general (they differ by exactly one bar always):
    evidence_style_exit_index = signal_index + 3
    assert evidence_style_exit_index == exit_index  # Thu == Thu here
    # but the OFFSET FROM SIGNAL differs from the strategy's OWN holding
    # count: evidence counts 3 bars from Monday, the strategy counts 3
    # HOLDING bars starting at Tuesday -- same calendar day only because
    # entry is 1 bar after signal; the strategy's own bar count is
    # (exit_index - entry_index + 1) = 3, holding_bars, not
    # (exit_index - signal_index) = 3 evidence-style bars measured from
    # a DIFFERENT reference point.
    strategy_holding_bars = exit_index - entry_index + 1
    assert strategy_holding_bars == 3
