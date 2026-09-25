"""Spec #003 v1.1 SS44-45 -- Benjamini-Hochberg FDR correction.

A family: same timeframe + horizon_bars + outcome_type + evaluation_run
(SS45's own default, config `multiple_testing.family`). Every signature
in a frozen Signature Set (SS26) tested in that family together -- no
post-hoc pruning of which p-values count toward the correction.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PValueRecord:
    signature_id: str
    timeframe: str
    horizon_bars: int
    outcome_type: str
    evaluation_run_id: str
    raw_p: float


def family_id(record: PValueRecord) -> str:
    return f"{record.timeframe}|{record.horizon_bars}bars|{record.outcome_type}|{record.evaluation_run_id}"


def benjamini_hochberg(records: list[PValueRecord]) -> dict[str, tuple[float, str]]:
    """Returns {signature_id: (adjusted_p, family_id)}. Standard BH
    step-up procedure applied WITHIN each family independently: sort
    ascending by raw_p, adjusted_p[i] = min(1, min over j>=i of
    raw_p[j] * m / rank[j]) -- enforced monotone non-increasing as rank
    decreases, computed from the largest rank down, capped at 1.0."""
    result: dict[str, tuple[float, str]] = {}
    families: dict[str, list[PValueRecord]] = {}
    for r in records:
        families.setdefault(family_id(r), []).append(r)

    for fam_id, fam_records in families.items():
        m = len(fam_records)
        ranked = sorted(fam_records, key=lambda r: r.raw_p)
        adjusted = [0.0] * m
        adjusted[m - 1] = min(1.0, ranked[m - 1].raw_p)
        for i in range(m - 2, -1, -1):
            candidate = min(1.0, ranked[i].raw_p * m / (i + 1))
            adjusted[i] = min(adjusted[i + 1], candidate)
        for rec, adj_p in zip(ranked, adjusted):
            result[rec.signature_id] = (adj_p, fam_id)
    return result
