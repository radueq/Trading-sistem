"""State transitions -- dimensional representation, not a combinatorial
state-graph enumeration (Spec #002 SS4/SS18: no A -> B -> C categorical
path enumeration across all state combinations).

For a normalized (percentile) feature's own historical series, exposes:
  current_value = X(t)
  delta_1       = X(t) - X(t-1)
  delta_n       = X(t) - X(t-n)              (n = TEST_CONFIG window)
  acceleration  = delta_n(t) - delta_n(t-n)  (= Delta^2 X, same spacing)

Matches Spec #002's own worked example: bb_width_percentile=0.08,
delta_5=+0.07, acceleration=+0.03. Numeric values remain the source of
truth; any semantic description ("COMPRESSION -> EXPANDING") is a label
layered on top, never the other way around.
"""
from __future__ import annotations

from typing import Optional, Sequence

from discovery.models.entities import FeatureStatus, TransitionEntry


def compute_transition(
    feature_name: str, percentile_series: Sequence[Optional[float]], delta_n_window: int,
) -> TransitionEntry:
    i = len(percentile_series) - 1
    current = percentile_series[i] if i >= 0 else None

    def at(idx: int) -> Optional[float]:
        return percentile_series[idx] if 0 <= idx < len(percentile_series) else None

    def delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
        return a - b if a is not None and b is not None else None

    delta_1 = delta(current, at(i - 1))
    delta_n = delta(current, at(i - delta_n_window))
    delta_n_prev = delta(at(i - delta_n_window), at(i - 2 * delta_n_window))
    acceleration = delta(delta_n, delta_n_prev)

    status = FeatureStatus.VALID.value if current is not None else FeatureStatus.MISSING_INPUT.value
    return TransitionEntry(
        feature_name=feature_name, current_value=current, delta_1=delta_1,
        delta_n=delta_n, delta_n_window=delta_n_window, acceleration=acceleration, status=status,
    )
