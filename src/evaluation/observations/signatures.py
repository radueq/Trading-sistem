"""Spec #003 v1.1 SS25-29 -- EvaluationSignature matching.

A signature is a pure AND of conditions over fields DiscoveryObservation
(Spec #002) already carries -- lane state labels and/or reason codes.
Never a new outcome-aware indicator (SS25): this module reads
`state_signature`/`reason_codes` only, nothing else, and computes
nothing new from raw/normalized feature values.
"""
from __future__ import annotations

from evaluation.models.entities import EvaluationSignatureDefinition


def matches(observation, signature: EvaluationSignatureDefinition) -> bool:
    for cond in signature.lane_conditions:
        if observation.state_signature.get(cond.lane) != cond.label:
            return False
    for cond in signature.reason_code_conditions:
        if cond.reason_code not in observation.reason_codes:
            return False
    return True


def match_observations(observations, signature: EvaluationSignatureDefinition) -> list:
    return [o for o in observations if matches(o, signature)]
