"""State mapping: percentile -> descriptive label (Spec #002 SS16/SS17).

Thresholds live entirely in config/states.yaml (TEST_CONFIG, not a
validated trading rule). Two vocabularies are supported:
VERY_LOW..VERY_HIGH (default) and the compression vocabulary
(EXTREME_COMPRESSION..EXTREME_EXPANSION) for lanes listed under
compression_vocabulary_lanes -- currently just `volatility`.

Which single normalized feature "drives" each lane's label
(lane_drivers in states.yaml) is a documented Level 1 design choice --
Spec #002 doesn't name one, and this keeps the choice external/auditable
instead of hardcoded here.
"""
from __future__ import annotations

from typing import Mapping, Optional, Sequence


def map_percentile_to_label(percentile: Optional[float], buckets: list[dict]) -> Optional[str]:
    if percentile is None:
        return None
    for bucket in buckets:
        if percentile <= bucket["max"]:
            return bucket["label"]
    return buckets[-1]["label"]


def lane_label_for(lane: str, percentile: Optional[float], states_config: dict) -> Optional[str]:
    compression_lanes = set(states_config.get("compression_vocabulary_lanes", []))
    buckets = (
        states_config["compression_buckets"] if lane in compression_lanes
        else states_config["percentile_buckets"]
    )
    return map_percentile_to_label(percentile, buckets)


def compute_lane_states(
    normalized_by_feature: Mapping[str, Optional[float]], states_config: dict,
) -> dict[str, Optional[str]]:
    lane_drivers: dict[str, str] = states_config["lane_drivers"]
    return {
        lane: lane_label_for(lane, normalized_by_feature.get(driver_feature), states_config)
        for lane, driver_feature in lane_drivers.items()
    }


def compute_persistence(
    lane_states_history: Sequence[Mapping[str, Optional[str]]], lookback_cap: int,
) -> int:
    """Consecutive trailing observations (ending at the most recent) whose
    full lane_states combination matches the most recent one -- capped
    purely to bound computation, not a claim about significance."""
    if not lane_states_history:
        return 0
    current = lane_states_history[-1]
    count = 0
    for entry in reversed(lane_states_history):
        if dict(entry) != dict(current):
            break
        count += 1
        if count >= lookback_cap:
            break
    return count
