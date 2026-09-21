"""Time-series rolling percentile normalization (Spec #002 SS14).

Method: "mean rank" percentile -- for each point, percentile =
(count_strictly_less + 0.5 * count_equal) / window_size, computed over
the trailing `window` observations ending at that point (inclusive).
Chosen for being simple and hand-verifiable (Spec #002 TEST 3), not
claimed to be the only possible convention.

`window` is a fixed size (e.g. 252); `min_periods` defaults to `window`
(no partial-window percentile unless explicitly configured smaller) --
Spec #002 SS14/SS30: never silently compute an equivalent statistic
from fewer observations than requested.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from discovery.models.entities import FeatureStatus


@dataclass(frozen=True)
class PercentilePoint:
    value: Optional[float]
    status: str


def rolling_percentile(
    values: Sequence[Optional[float]], window: int, min_periods: Optional[int] = None,
) -> list[PercentilePoint]:
    min_periods = window if min_periods is None else min_periods
    if min_periods > window:
        raise ValueError("min_periods cannot exceed window")

    out: list[PercentilePoint] = []
    for i in range(len(values)):
        current = values[i]
        start = max(0, i - window + 1)
        window_data = [v for v in values[start:i + 1] if v is not None]

        if current is None:
            out.append(PercentilePoint(None, FeatureStatus.MISSING_INPUT.value))
            continue
        if len(window_data) < min_periods:
            out.append(PercentilePoint(None, FeatureStatus.INSUFFICIENT_HISTORY.value))
            continue

        count_less = sum(1 for v in window_data if v < current)
        count_equal = sum(1 for v in window_data if v == current)
        percentile = (count_less + 0.5 * count_equal) / len(window_data)
        out.append(PercentilePoint(percentile, FeatureStatus.VALID.value))
    return out
