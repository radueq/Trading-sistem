"""TEST 39 -- TIME_BLOCK bootstrap blocks REAL market sessions, not
event dates (PATCH #003-B, GPT Review #003 Round 2, mandatory finding).

The pre-patch bug: blocks were built over the dates PRESENT in
`dated_values`. For a sparse/rare signature, those dates can be
scattered across months (2 Jan, 18 Jan, 12 Feb, 4 Mar, ...) -- treating
four such dates as "4 consecutive sessions" throws away the actual
local-time-window/regime structure TIME_BLOCK clustering exists to
preserve. Fixed: blocks are now built over the caller-supplied
`session_dates` (the run's real trading calendar), and a session with no
signature value contributes nothing when its block is drawn.
"""
from evaluation.statistics.bootstrap import time_block_bootstrap_replicates


def _daily_calendar(start_day: int, end_day: int) -> list[str]:
    return [f"2024-01-{d:02d}" for d in range(start_day, end_day + 1)]


def test_sparse_event_dates_are_placed_within_the_real_calendar_not_treated_as_consecutive():
    # A rare signature: only 4 matching dates, scattered across a
    # 30-session calendar -- exactly the pathological case from the
    # review (2 Jan, 18 Jan example generalized to fit one month).
    session_dates = _daily_calendar(1, 30)
    dated_values = [
        ("2024-01-02", 10.0),
        ("2024-01-08", 20.0),
        ("2024-01-18", 30.0),
        ("2024-01-29", 40.0),
    ]
    # block_length_bars=30 means ONE block covering the whole 30-session
    # calendar -- every replicate must reconstruct the exact same 4
    # values (nothing to resample among, only one block exists), proving
    # the block was built from the 30-day calendar, not from "4 event
    # dates chunked into 1 block of size 30" (which would be
    # indistinguishable here) -- the real proof is in the next test.
    replicates = time_block_bootstrap_replicates(dated_values, session_dates, block_length_bars=30, iterations=50, seed=1)
    assert len(replicates) == 50
    assert all(r == 25.0 for r in replicates)  # mean(10,20,30,40) = 25, only one block exists


def test_block_length_counts_market_sessions_not_event_dates():
    # 8 sessions total, 2 event dates far apart (session 1 and session 8).
    # block_length_bars=4 over the REAL calendar creates exactly 2 blocks:
    # sessions [1..4] and [5..8]. The event at session 1 and the event at
    # session 8 must be independently drawable -- i.e. a replicate CAN
    # end up with only the 100.0 value, or only the 200.0 value (they are
    # 7 sessions apart, not "2 consecutive event dates"). Composition is
    # inspected via a statistic returning (count(100), count(200)) so
    # each block being drawn multiple times per replicate doesn't average
    # the signal away. If block_length_bars were (mis-)applied to the 2
    # event dates directly, both would always land in the SAME one block
    # and every replicate would show both counts > 0 together, always.
    session_dates = _daily_calendar(1, 8)
    dated_values = [("2024-01-01", 100.0), ("2024-01-08", 200.0)]
    compositions = time_block_bootstrap_replicates(
        dated_values, session_dates, block_length_bars=4, iterations=300, seed=2,
        statistic=lambda vs: (vs.count(100.0), vs.count(200.0)),
    )
    only_100 = any(c[0] > 0 and c[1] == 0 for c in compositions)
    only_200 = any(c[0] == 0 and c[1] > 0 for c in compositions)
    assert only_100 and only_200, (
        "with the 2 events in DIFFERENT real-calendar blocks, some replicates must draw only one "
        "of them -- both always appearing together would mean they were (wrongly) placed in the "
        "same block"
    )


def test_multiple_securities_same_session_stay_together():
    # Same date, three different securities' episodes -- must never be
    # split across different blocks (Spec #003 PATCH #003-A finding #2,
    # re-verified here against the real-calendar fix). Composition
    # statistic counts each value's occurrences; since a block can be
    # drawn more than once per replicate, the invariant to check is that
    # the three same-day values are always drawn in EQUAL multiples.
    session_dates = _daily_calendar(1, 10)
    dated_values = [
        ("2024-01-05", 1.0), ("2024-01-05", 2.0), ("2024-01-05", 3.0),  # NVDA/AMD/AVGO, same day
        ("2024-01-06", 100.0),
    ]
    compositions = time_block_bootstrap_replicates(
        dated_values, session_dates, block_length_bars=1, iterations=200, seed=3,
        statistic=lambda vs: (vs.count(1.0), vs.count(2.0), vs.count(3.0)),
    )
    assert all(c1 == c2 == c3 for c1, c2, c3 in compositions), (
        "the 3 same-day values must always be drawn together in equal multiples, never split apart"
    )
    assert any(c1 > 0 for c1, _, _ in compositions), "sanity: the 2024-01-05 block must be drawn at least once across 200 iterations"


def test_gap_session_with_no_value_contributes_nothing_but_still_exists_as_a_session():
    # Sessions 1..6 exist on the real calendar; only session 1 and
    # session 6 have a value. A session with no value (2..5) must be a
    # normal, silent no-op when its block is drawn -- not an error, and
    # not skipped from the calendar (skipping it would shrink block
    # boundaries and change which sessions group with which).
    session_dates = _daily_calendar(1, 6)
    dated_values = [("2024-01-01", 5.0), ("2024-01-06", 50.0)]
    # One block covering all 6 sessions -- must not raise, and must
    # reconstruct exactly the 2 real values (empty sessions contribute
    # nothing).
    replicates = time_block_bootstrap_replicates(dated_values, session_dates, block_length_bars=6, iterations=20, seed=4)
    assert len(replicates) == 20
    assert all(r == (5.0 + 50.0) / 2 for r in replicates)
