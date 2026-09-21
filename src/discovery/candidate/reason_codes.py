"""Discovery reason codes (Spec #002 SS28).

Descriptions of WHY a candidate was surfaced, never recommendations.
None of these may be interpreted as "buy" or "sell."
"""
from __future__ import annotations

from enum import Enum


class ReasonCode(str, Enum):
    TREND_EXTREME = "TREND_EXTREME"
    RS_EXTREME = "RS_EXTREME"
    VOLUME_ANOMALY = "VOLUME_ANOMALY"
    VOLATILITY_COMPRESSION = "VOLATILITY_COMPRESSION"
    VOLATILITY_EXPANSION = "VOLATILITY_EXPANSION"
    MOMENTUM_ACCELERATION = "MOMENTUM_ACCELERATION"
    MULTI_LANE_CONVERGENCE = "MULTI_LANE_CONVERGENCE"
    STATE_TRANSITION = "STATE_TRANSITION"
    PERSISTENT_STATE = "PERSISTENT_STATE"
