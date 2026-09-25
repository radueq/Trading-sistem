"""TEST 10 -- Episode separation (Spec #003 SS30/SS66).

A gap larger than max_gap_bars (intervening non-matching bars) splits
into a NEW episode.
"""
from evaluation.observations.episodes import build_episodes


def test_gap_exceeding_max_gap_bars_splits_episode():
    bar_dates = [f"2024-01-{d:02d}" for d in range(1, 20)]
    matched = ["2024-01-02", "2024-01-08"]  # 5 intervening bars, gap=5 > max_gap_bars=1
    episodes = build_episodes("sidA", "sigX", matched, bar_dates, max_gap_bars=1)
    assert len(episodes) == 2
    assert episodes[0].member_as_ofs == ("2024-01-02",)
    assert episodes[1].member_as_ofs == ("2024-01-08",)


def test_gap_within_tolerance_stays_one_episode():
    bar_dates = [f"2024-01-{d:02d}" for d in range(1, 20)]
    matched = ["2024-01-02", "2024-01-04"]  # 1 intervening bar, gap=1 <= max_gap_bars=1
    episodes = build_episodes("sidA", "sigX", matched, bar_dates, max_gap_bars=1)
    assert len(episodes) == 1
