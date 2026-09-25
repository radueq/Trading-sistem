"""TEST 17 -- Security concentration (Spec #003 SS41/SS66).

Spec's own worked example: 80 episodes, 52 from one security -> must be
visible.
"""
import pytest

from evaluation.statistics.concentration import compute_concentration


def test_concentration_reveals_single_security_dominance():
    security_ids = ["AAA"] * 52 + [f"OTHER{i}" for i in range(28)]
    c = compute_concentration(security_ids)
    assert c.unique_security_count == 29
    assert c.largest_security_share_of_episodes == pytest.approx(52 / 80)
