"""TEST 38 -- Exact entry-bar date required (PATCH #003-A, GPT Review
#003 Round 1, mandatory finding #6).

A security with NO bar dated exactly `observation_as_of` (e.g. a halt
or gap) must produce INVALID_INPUT, never silently fall back to an
earlier "at or before" bar -- otherwise the security's return could be
measured from one date while the benchmark is aligned to a different
(later) date, comparing two different time windows as if they were the
same.
"""
from evaluation.models.entities import OutcomeStatus
from evaluation.outcomes.forward_returns import compute_forward_outcome


class Bar:
    def __init__(self, date, close):
        self.date, self.split_adjusted_close = date, close


def test_missing_bar_at_exact_observation_date_is_invalid_input():
    # No bar dated 2024-01-03 -- a halt/gap on that day.
    bars = [
        Bar("2024-01-02", 100.0),
        Bar("2024-01-04", 103.0),
        Bar("2024-01-05", 104.0),
    ]
    o = compute_forward_outcome("sid", bars, "2024-01-03", "1D", 1, None, "cfg_x")
    assert o.outcome_status == OutcomeStatus.INVALID_INPUT.value
    assert o.entry_reference_price is None
    assert o.forward_return is None


def test_exact_match_at_observation_date_is_used():
    bars = [Bar("2024-01-02", 100.0), Bar("2024-01-03", 105.0), Bar("2024-01-04", 110.0)]
    o = compute_forward_outcome("sid", bars, "2024-01-03", "1D", 1, None, "cfg_x")
    assert o.outcome_status == OutcomeStatus.VALID.value
    assert o.entry_reference_price == 105.0
