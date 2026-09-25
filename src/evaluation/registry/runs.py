"""Spec #003 v1.1 SS59-60 -- evaluation run metadata / reproducibility.

`build_run_id` is DETERMINISTIC (a hash of the run's own defining
inputs), not a random/incrementing counter: the same data + config +
signature set + seeds + versions must reproduce the same run_id too,
not just the same statistics (SS60).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def build_run_id(**fingerprint_fields) -> str:
    raw = "|".join(f"{k}={v}" for k, v in sorted(fingerprint_fields.items()))
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"run_{digest}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
