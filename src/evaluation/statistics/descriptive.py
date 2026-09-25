"""Spec #003 v1.1 SS35 -- descriptive statistics for an outcome
distribution (absolute or relative), computed on the EPISODE_DEDUPLICATED
view by default (Spec #003 SS31)."""
from __future__ import annotations

import statistics as pystats
from typing import Optional

import numpy as np

from evaluation.models.entities import ConfidenceInterval, DescriptiveStats


def describe(values: list[float], ci: Optional[ConfidenceInterval] = None) -> DescriptiveStats:
    n = len(values)
    if n == 0:
        return DescriptiveStats(
            n=0, mean=None, median=None, std=None, q10=None, q25=None, q75=None, q90=None,
            positive_rate=None, confidence_interval=ci,
        )
    mean = pystats.fmean(values)
    median = pystats.median(values)
    std = pystats.stdev(values) if n > 1 else 0.0
    arr = np.array(values, dtype=float)
    q10, q25, q75, q90 = (float(np.quantile(arr, q)) for q in (0.10, 0.25, 0.75, 0.90))
    positive_rate = sum(1 for v in values if v > 0) / n
    return DescriptiveStats(
        n=n, mean=mean, median=median, std=std, q10=q10, q25=q25, q75=q75, q90=q90,
        positive_rate=positive_rate, confidence_interval=ci,
    )
