"""Spec #005 v1.0 test fixtures (Batch 1: contracts, provenance, calendar).

No PIT/ingestion/database is needed here -- Batch 1 tests exercise pure
functions over hand-built #003/#004-shaped objects, mirroring the
established convention in tests/spec003 and tests/spec004.
"""
from __future__ import annotations

import pytest

from evaluation.models.entities import EvaluationRunRegistry
from evaluation.registry.runs import build_run_id
from hypothesis.models.entities import EvidenceProvenance

SIGNATURE_ID = "VOL_COMPRESSION_RS_HIGH"
SIGNATURE_SET_ID = "sigset_x"
DISCOVERY_CONFIG_VERSION = "cfg_disc"
EVALUATION_CONFIG_VERSION = "cfg_eval"
TIMEFRAME = "1D"
BENCHMARK_SECURITY_ID = "SBENCH"
DEVELOPMENT_START = "2020-01-01"
DEVELOPMENT_END = "2024-01-01"
VALIDATION_START = "2024-02-01"
VALIDATION_END = "2024-12-31"
LOCKED_OOS_START = "2025-01-01"

_LEGACY_HASH_DEFAULTS = dict(
    development_start=DEVELOPMENT_START, development_end=DEVELOPMENT_END, timeframe=TIMEFRAME,
    signature_set_id=SIGNATURE_SET_ID, discovery_config_version=DISCOVERY_CONFIG_VERSION,
    evaluation_config_version=EVALUATION_CONFIG_VERSION, bootstrap_seed=1, comparison_seed=2,
)


def build_run_registry(**overrides) -> EvaluationRunRegistry:
    """A genuinely self-consistent EvaluationRunRegistry: `evaluation_run_id`
    is always the REAL `build_run_id()` output for the 8 legacy-hash
    fields actually stored on the object (after `overrides` are
    applied) -- never a hand-typed string. Pass `evaluation_run_id=...`
    explicitly to deliberately construct a TAMPERED object (id no longer
    matching its own fields) for a negative test."""
    hash_fields = dict(_LEGACY_HASH_DEFAULTS)
    hash_fields.update({k: v for k, v in overrides.items() if k in hash_fields})
    run_id = overrides.get("evaluation_run_id") or build_run_id(**hash_fields)
    return EvaluationRunRegistry(
        evaluation_run_id=run_id,
        created_at=overrides.get("created_at", "2026-09-26T00:00:00Z"),
        mode=overrides.get("mode", "FORMAL_DEVELOPMENT"),
        development_start=hash_fields["development_start"], development_end=hash_fields["development_end"],
        timeframe=hash_fields["timeframe"], horizons=overrides.get("horizons", (1, 2, 3, 5, 10)),
        benchmark_security_id=overrides.get("benchmark_security_id", BENCHMARK_SECURITY_ID),
        discovery_engine_version=overrides.get("discovery_engine_version", "v1.0.0"),
        discovery_config_version=hash_fields["discovery_config_version"],
        evaluation_engine_version=overrides.get("evaluation_engine_version", "v1.0.0"),
        evaluation_config_version=hash_fields["evaluation_config_version"],
        signature_set_id=hash_fields["signature_set_id"],
        bootstrap_seed=hash_fields["bootstrap_seed"], bootstrap_iterations=overrides.get("bootstrap_iterations", 200),
        comparison_seed=hash_fields["comparison_seed"], comparison_iterations=overrides.get("comparison_iterations", 200),
        multiple_testing_method=overrides.get("multiple_testing_method", "BH"),
    )


def build_evidence_provenance(run_registry: EvaluationRunRegistry, **overrides) -> EvidenceProvenance:
    return EvidenceProvenance(
        evaluation_run_id=overrides.get("evaluation_run_id", run_registry.evaluation_run_id),
        evaluation_engine_version=overrides.get("evaluation_engine_version", run_registry.evaluation_engine_version),
        evaluation_config_version=overrides.get("evaluation_config_version", run_registry.evaluation_config_version),
        signature_id=overrides.get("signature_id", SIGNATURE_ID),
        signature_set_id=overrides.get("signature_set_id", run_registry.signature_set_id),
        discovery_engine_version=overrides.get("discovery_engine_version", run_registry.discovery_engine_version),
        discovery_config_version=overrides.get("discovery_config_version", run_registry.discovery_config_version),
        timeframe=overrides.get("timeframe", run_registry.timeframe),
    )


@pytest.fixture
def run_registry() -> EvaluationRunRegistry:
    return build_run_registry()


@pytest.fixture
def evidence_provenance(run_registry) -> EvidenceProvenance:
    return build_evidence_provenance(run_registry)
