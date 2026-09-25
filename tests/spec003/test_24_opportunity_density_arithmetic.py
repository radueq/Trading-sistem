"""TEST 24 -- Opportunity-density arithmetic (Spec #003 SS37/SS66).

Purely descriptive frequency-of-occurrence, hand-verified.
"""
import pytest

from evaluation.statistics.opportunity import compute_opportunity_density


def test_opportunity_density_matches_hand_computation():
    session_dates = [f"2024-01-{d:02d}" for d in range(1, 31)]  # 30 sessions
    representative_as_ofs = ["2024-01-05", "2024-01-10", "2024-01-20"]  # 3 episodes
    od = compute_opportunity_density(representative_as_ofs, session_dates)
    assert od.episode_count == 3
    assert od.episodes_per_20_sessions == pytest.approx(3 / 30 * 20)
    assert od.episodes_per_60_sessions == pytest.approx(3 / 30 * 60)
    # bar positions: 4, 9, 19 (0-indexed) -> gaps [5, 10] -> median 7.5
    assert od.median_sessions_between_episodes == pytest.approx(7.5)
