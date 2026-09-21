"""TEST 12 -- Transition representation (Spec #002 SS38/SS18).

Known X(t) path -> expected DeltaX/Delta^2X, matching Spec #002's own
worked example: bb_width_percentile=0.08, delta_5=+0.07, acceleration=+0.03.
"""
from discovery.states.transitions import compute_transition


def test_transition_matches_spec_worked_example():
    # indices 0..10; only 0, 5, 10 are load-bearing for delta_5/acceleration
    series = [-0.03, 0.0, 0.0, 0.0, 0.0, 0.01, 0.0, 0.0, 0.0, 0.0, 0.08]
    t = compute_transition("bb_width_percentile", series, delta_n_window=5)

    assert t.current_value == 0.08
    assert abs(t.delta_n - 0.07) < 1e-9
    assert abs(t.acceleration - 0.03) < 1e-9
    assert t.delta_n_window == 5
    assert t.status == "VALID"


def test_transition_missing_when_insufficient_history():
    series = [0.5, 0.4]
    t = compute_transition("x", series, delta_n_window=5)
    assert t.current_value == 0.4
    assert t.delta_n is None  # not enough history to look back 5 steps
    assert t.acceleration is None
