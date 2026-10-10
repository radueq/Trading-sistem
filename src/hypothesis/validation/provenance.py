"""Spec #004 SS33-34, TEST 42-43 -- provenance consistency checks.

Mirrors Spec #003's FORMAL_DEVELOPMENT provenance guard (PATCH #003-B): a
hypothesis's `evidence_provenance` must match the ACTUAL Discovery/
Evaluation run it claims to rest on, not merely be internally self-
consistent. A hypothesis whose provenance no longer matches reality
(Discovery's engine/config changed underneath it, or it points at a
different Evaluation run than the one supplied) must be caught here,
before PREREGISTERED -- never silently reused across a changed pipeline
(SS34: a new interpretation under new provenance is a NEW hypothesis).
"""
from __future__ import annotations

from evaluation.models.entities import EvaluationRunRegistry

from hypothesis.models.entities import EvidenceProvenance


def check_provenance_matches_run(
    evidence_provenance: EvidenceProvenance, run_registry: EvaluationRunRegistry,
) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []

    if evidence_provenance.evaluation_run_id != run_registry.evaluation_run_id:
        errors.append(
            f"evidence_provenance.evaluation_run_id={evidence_provenance.evaluation_run_id!r} does not "
            f"match the supplied run {run_registry.evaluation_run_id!r} (TEST 43)"
        )
    if evidence_provenance.evaluation_engine_version != run_registry.evaluation_engine_version:
        errors.append(
            f"evaluation_engine_version mismatch -- hypothesis claims "
            f"{evidence_provenance.evaluation_engine_version!r}, run used {run_registry.evaluation_engine_version!r} (TEST 43)"
        )
    if evidence_provenance.evaluation_config_version != run_registry.evaluation_config_version:
        errors.append(
            f"evaluation_config_version mismatch -- hypothesis claims "
            f"{evidence_provenance.evaluation_config_version!r}, run used {run_registry.evaluation_config_version!r} (TEST 43)"
        )
    if evidence_provenance.discovery_engine_version != run_registry.discovery_engine_version:
        errors.append(
            f"discovery_engine_version mismatch -- hypothesis claims "
            f"{evidence_provenance.discovery_engine_version!r}, run used {run_registry.discovery_engine_version!r} (TEST 42)"
        )
    if evidence_provenance.discovery_config_version != run_registry.discovery_config_version:
        errors.append(
            f"discovery_config_version mismatch -- hypothesis claims "
            f"{evidence_provenance.discovery_config_version!r}, run used {run_registry.discovery_config_version!r} (TEST 42)"
        )
    if evidence_provenance.signature_set_id != run_registry.signature_set_id:
        errors.append("signature_set_id mismatch between hypothesis provenance and the actual run (TEST 42)")
    if evidence_provenance.timeframe != run_registry.timeframe:
        errors.append("timeframe mismatch between hypothesis provenance and the actual run (TEST 42)")
    # Stage 6 -- Finding 1, decision registry G1: a DECLARED evaluation_mode
    # must equal the REAL run's own `mode` (field-name asymmetry: the run
    # registry calls it `mode`). Checked whenever the evidence declares a
    # mode; an UNDECLARED mode (None, every pre-Stage-6 record) is not a
    # lie about the run and is left to each consumer's own policy --
    # `preregister_hypothesis()` hard-rejects it (G1), so the #004 gate
    # stays fully strict, while Spec #005's existing callers of this
    # function keep their exact pre-Stage-6 behavior on such records.
    if evidence_provenance.evaluation_mode is not None and evidence_provenance.evaluation_mode != run_registry.mode:
        errors.append(
            f"evaluation_mode mismatch -- hypothesis evidence claims "
            f"{evidence_provenance.evaluation_mode!r}, but the actual run's mode is {run_registry.mode!r} "
            f"(Stage 6, decision registry G1 -- a self-declared mode is never trusted on its own)"
        )

    return (not errors, tuple(errors))
