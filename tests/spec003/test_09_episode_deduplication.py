"""TEST 9 -- Episode deduplication (Spec #003 SS30-31/SS66).

Consecutive matching dates for the same (security, signature) collapse
into ONE episode, representative = FIRST.
"""
from evaluation.observations.episodes import build_episodes


def test_consecutive_matches_form_one_episode():
    bar_dates = [f"2024-01-{d:02d}" for d in range(1, 20)]
    matched = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    episodes = build_episodes("sidA", "sigX", matched, bar_dates, max_gap_bars=1)
    assert len(episodes) == 1
    assert episodes[0].member_as_ofs == tuple(matched)
    assert episodes[0].representative_as_of == "2024-01-02"
