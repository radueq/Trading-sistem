"""TEST 11 -- State mapping (Spec #002 SS38/SS16).

Known percentile values -> expected state labels.
"""
from discovery.config.loader import load_config
from discovery.states.mapper import lane_label_for


def test_state_mapping_known_percentiles():
    cfg = load_config()

    assert lane_label_for("trend", 0.05, cfg.states) == "VERY_LOW"
    assert lane_label_for("trend", 0.20, cfg.states) == "LOW"
    assert lane_label_for("trend", 0.50, cfg.states) == "NEUTRAL"
    assert lane_label_for("trend", 0.85, cfg.states) == "HIGH"
    assert lane_label_for("trend", 0.95, cfg.states) == "VERY_HIGH"

    # volatility uses the compression vocabulary (Spec #002 SS16)
    assert lane_label_for("volatility", 0.05, cfg.states) == "EXTREME_COMPRESSION"
    assert lane_label_for("volatility", 0.20, cfg.states) == "COMPRESSION"
    assert lane_label_for("volatility", 0.50, cfg.states) == "NORMAL"
    assert lane_label_for("volatility", 0.85, cfg.states) == "EXPANSION"
    assert lane_label_for("volatility", 0.95, cfg.states) == "EXTREME_EXPANSION"

    assert lane_label_for("trend", None, cfg.states) is None
