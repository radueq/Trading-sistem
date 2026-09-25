"""TEST 11 -- Raw vs episode counts (Spec #003 SS31/SS36/SS66).

Every raw matching date belongs to exactly one episode (counts
reconcile); episode count is always <= raw count.
"""
from evaluation.observations.episodes import build_episodes


def test_every_raw_match_is_a_member_of_exactly_one_episode():
    bar_dates = [f"2024-01-{d:02d}" for d in range(1, 30)]
    matched = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-10", "2024-01-20", "2024-01-21"]
    episodes = build_episodes("sidA", "sigX", matched, bar_dates, max_gap_bars=1)

    all_members = [d for ep in episodes for d in ep.member_as_ofs]
    assert sorted(all_members) == sorted(matched)
    assert len(set(all_members)) == len(matched), "no date should appear in two episodes"
    assert len(episodes) <= len(matched)
    assert len(episodes) == 3  # {02,03,04}, {10}, {20,21}
