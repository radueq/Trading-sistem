"""Convergence: descriptive assembly of active lanes + reason codes
(Spec #002 SS19/SS20/SS28).

Convergence Engine does NOT create one global Alpha Score (SS20,
forbidden explicitly: no `0.3*trend + 0.2*rs + ...`). It outputs
`active_lanes` + the underlying `state_signature` -- a description, not
a prediction. `extremeness`/`persistence`/`state_frequency` below mean
"statistically noteworthy," never "expected profitable" (SS24).
"""
from __future__ import annotations

from typing import Optional

from discovery.candidate.reason_codes import ReasonCode
from discovery.models.entities import DescriptiveMetrics, StateSignature, TransitionEntry

_NEUTRAL_LABELS = {"NEUTRAL", "NORMAL"}
_EXTREME_LABELS = {"HIGH", "VERY_HIGH", "LOW", "VERY_LOW"}
_COMPRESSION_LABELS = {"COMPRESSION", "EXTREME_COMPRESSION"}
_EXPANSION_LABELS = {"EXPANSION", "EXTREME_EXPANSION"}
_HIGH_LABELS = {"HIGH", "VERY_HIGH"}


def active_lanes_for(state_signature: StateSignature) -> list[str]:
    return sorted(
        lane for lane, label in state_signature.lane_states.items()
        if label is not None and label not in _NEUTRAL_LABELS
    )


def compute_extremeness(state_signature: StateSignature, states_config: dict, discovery_config: dict) -> float:
    midpoint = discovery_config["extremeness"]["midpoint"]
    lane_drivers: dict[str, str] = states_config["lane_drivers"]
    distances = []
    for driver_feature in lane_drivers.values():
        pct = state_signature.normalized_feature_vector.get(driver_feature)
        if pct is None:
            continue
        distances.append(abs(pct - midpoint) / midpoint)
    return max(distances) if distances else 0.0


def build_descriptive_metrics(
    extremeness: float, persistence: int, state_frequency: Optional[float],
    sample_count: int, min_sample_support: int,
) -> DescriptiveMetrics:
    support_status = "SUFFICIENT" if sample_count >= min_sample_support else "INSUFFICIENT"
    return DescriptiveMetrics(
        extremeness=extremeness, persistence=persistence, state_frequency=state_frequency,
        sample_count=sample_count, support_status=support_status,
    )


def reason_codes_for(
    state_signature: StateSignature,
    transitions: dict[str, TransitionEntry],
    active_lanes: list[str],
    states_config: dict,
    discovery_config: dict,
) -> list[str]:
    codes: list[str] = []
    lane_drivers: dict[str, str] = states_config["lane_drivers"]
    lane_states = state_signature.lane_states

    if lane_states.get("trend") in _EXTREME_LABELS:
        codes.append(ReasonCode.TREND_EXTREME.value)

    if lane_states.get("relative_strength") in _EXTREME_LABELS:
        codes.append(ReasonCode.RS_EXTREME.value)

    if lane_states.get("volume") in _HIGH_LABELS:
        codes.append(ReasonCode.VOLUME_ANOMALY.value)

    vol_label = lane_states.get("volatility")
    if vol_label in _COMPRESSION_LABELS:
        codes.append(ReasonCode.VOLATILITY_COMPRESSION.value)
    elif vol_label in _EXPANSION_LABELS:
        codes.append(ReasonCode.VOLATILITY_EXPANSION.value)

    momentum_transition = transitions.get(lane_drivers.get("momentum"))
    accel_threshold = discovery_config["momentum_acceleration_threshold"]
    if momentum_transition and momentum_transition.acceleration is not None:
        if abs(momentum_transition.acceleration) >= accel_threshold:
            codes.append(ReasonCode.MOMENTUM_ACCELERATION.value)

    if len(active_lanes) >= discovery_config["multi_lane_convergence_min"]:
        codes.append(ReasonCode.MULTI_LANE_CONVERGENCE.value)

    transition_threshold = discovery_config["state_transition_delta_threshold"]
    if any(
        t.delta_n is not None and abs(t.delta_n) >= transition_threshold
        for t in transitions.values()
    ):
        codes.append(ReasonCode.STATE_TRANSITION.value)

    if active_lanes and state_signature.persistence >= discovery_config["persistent_state_min_days"]:
        codes.append(ReasonCode.PERSISTENT_STATE.value)

    return codes
