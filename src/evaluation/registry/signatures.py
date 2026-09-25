"""Spec #003 v1.1 SS26-27 -- freezing a Signature Set.

The exact list of signatures tested in one FORMAL_DEVELOPMENT run is
hashed into a stable `signature_set_id`, so the same set always
reproduces the same id (Spec #003 SS60) and any post-hoc addition or
removal is visible as a DIFFERENT id, never a silent mutation (SS26 --
no "test 1000, pick 10 winners, pretend only 10 were tested").
"""
from __future__ import annotations

import hashlib

from evaluation.models.entities import EvaluationSignatureDefinition, SignatureSet


def _fingerprint(sig: EvaluationSignatureDefinition) -> str:
    lane_part = "&".join(sorted(f"{c.lane}={c.label}" for c in sig.lane_conditions))
    reason_part = "&".join(sorted(c.reason_code for c in sig.reason_code_conditions))
    return f"{sig.signature_id}::{lane_part}::{reason_part}::{sig.timeframe}"


def freeze_signature_set(signatures: list[EvaluationSignatureDefinition]) -> SignatureSet:
    fingerprints = sorted(_fingerprint(s) for s in signatures)
    digest = hashlib.sha256("||".join(fingerprints).encode()).hexdigest()[:12]
    return SignatureSet(signature_set_id=f"sigset_{digest}", signatures=tuple(signatures))
