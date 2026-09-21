"""Cross-sectional percentile normalization (Spec #002 SS15).

Where a feature's TIME_SERIES percentile asks "where is this security
relative to ITS OWN history", cross-sectional percentile asks "where is
this security relative to the rest of the eligible universe on this
same as_of." Same mean-rank formula as rolling_percentile.py, applied
across securities instead of across time -- the distinction must survive
into output (normalization_type on NormalizedFeatureObservation).
"""
from __future__ import annotations

from discovery.models.entities import FeatureStatus
from discovery.normalization.rolling_percentile import PercentilePoint


def cross_sectional_percentile(values_by_security: dict[str, float | None]) -> dict[str, PercentilePoint]:
    valid_items = [(sid, v) for sid, v in values_by_security.items() if v is not None]
    n = len(valid_items)

    result: dict[str, PercentilePoint] = {}
    for sid, v in values_by_security.items():
        if v is None:
            result[sid] = PercentilePoint(None, FeatureStatus.MISSING_INPUT.value)
            continue
        if n == 0:
            result[sid] = PercentilePoint(None, FeatureStatus.INSUFFICIENT_HISTORY.value)
            continue
        count_less = sum(1 for _, ov in valid_items if ov < v)
        count_equal = sum(1 for _, ov in valid_items if ov == v)
        percentile = (count_less + 0.5 * count_equal) / n
        result[sid] = PercentilePoint(percentile, FeatureStatus.VALID.value)
    return result
