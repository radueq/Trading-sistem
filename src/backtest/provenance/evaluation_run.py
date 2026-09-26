"""Spec #005 v1.0 SS4 -- evidence-provenance preflight guard (Batch 1).

Three independent checks compose the full guard for one (hypothesis,
EvaluationRunRegistry) pair:

1. Legacy content-address consistency: recompute `evaluation.registry.
   runs.build_run_id()` from EXACTLY the 8 fields `evaluation/engine.py`
   itself uses (confirmed at commit cfa0809, engine.py:370-376) and
   compare to the supplied registry's own `evaluation_run_id`. SS4 is
   explicit about what this does and does NOT prove: "Hash recomputation
   verifies only that the supplied fields produce the supplied ID. It
   does not authenticate the object, prove that a historical run
   occurred, establish that data were unseen, or detect coordinated
   replacement of both fields and ID. It is not an anti-forgery
   certificate."
2. Cross-object linkage: reuse `hypothesis.validation.provenance.
   check_provenance_matches_run()` UNCHANGED -- it already compares
   `evaluation_run_id`, `evaluation_engine_version`,
   `evaluation_config_version`, `discovery_engine_version`,
   `discovery_config_version`, `signature_set_id`, `timeframe` between a
   hypothesis's own `EvidenceProvenance` and the actual
   `EvaluationRunRegistry` supplied. `signature_set_id`/`timeframe`
   overlap with the 8-field hash on purpose (SS4: "internal identity
   consistency and cross-object agreement are different checks").
3. Two checks NEITHER of the above establishes (SS4): `mode ==
   "FORMAL_DEVELOPMENT"` (the pre-registration hard-errors in
   `run_evaluation()` only fire under that mode -- an EXPLORATORY run's
   `development_end` carries no such rigor guarantee) and
   `benchmark_security_id` matching the ResearchPlan's own declared
   benchmark.

Nothing here mutates or re-derives #003/#004 state; every function is a
pure read over caller-supplied objects.
"""
from __future__ import annotations

from evaluation.models.entities import EvaluationRunRegistry
from evaluation.registry.runs import build_run_id
from hypothesis.models.entities import EvidenceProvenance
from hypothesis.validation.provenance import check_provenance_matches_run

from backtest.models.entities import EvaluationRunCrossCheckResult

# The EXACT 8 keyword arguments evaluation/engine.py:370-376 passes to
# build_run_id() -- never all 15 EvaluationRunRegistry fields, which
# would silently produce a DIFFERENT identity than the one #003 itself
# computed (Spec #005 SS4).
LEGACY_RUN_ID_FIELDS = (
    "development_start", "development_end", "timeframe", "signature_set_id",
    "discovery_config_version", "evaluation_config_version", "bootstrap_seed", "comparison_seed",
)


def recompute_legacy_evaluation_run_id(run_registry: EvaluationRunRegistry) -> str:
    fields = {name: getattr(run_registry, name) for name in LEGACY_RUN_ID_FIELDS}
    return build_run_id(**fields)


def verify_evaluation_run_identity(run_registry: EvaluationRunRegistry) -> tuple[bool, tuple[str, ...]]:
    """See module docstring, point 1 -- this is a CONSISTENCY check, not
    an authenticity or historical-execution proof (Spec #005 SS4)."""
    recomputed = recompute_legacy_evaluation_run_id(run_registry)
    if recomputed != run_registry.evaluation_run_id:
        return False, (
            f"evaluation_run_id={run_registry.evaluation_run_id!r} does not match the recomputed "
            f"legacy hash {recomputed!r} for the supplied 8-field recipe -- this EvaluationRunRegistry "
            f"was not produced by evaluation.engine.run_evaluation() with these exact field values "
            f"(Spec #005 SS4)",
        )
    return True, ()


def verify_mode_is_formal_development(run_registry: EvaluationRunRegistry) -> tuple[bool, tuple[str, ...]]:
    if run_registry.mode != "FORMAL_DEVELOPMENT":
        return False, (
            f"run_registry.mode={run_registry.mode!r}, required 'FORMAL_DEVELOPMENT' -- only under that "
            f"mode does run_evaluation() hard-enforce the PRE_REGISTERED/created_before_outcome_evaluation "
            f"signature guards (Spec #005 SS4); an EXPLORATORY run's development_end carries no such "
            f"rigor guarantee",
        )
    return True, ()


def verify_benchmark_matches(run_registry: EvaluationRunRegistry, expected_benchmark_security_id: str) -> tuple[bool, tuple[str, ...]]:
    if run_registry.benchmark_security_id != expected_benchmark_security_id:
        return False, (
            f"run_registry.benchmark_security_id={run_registry.benchmark_security_id!r} does not match "
            f"the ResearchPlan's declared benchmark {expected_benchmark_security_id!r} (Spec #005 SS4)",
        )
    return True, ()


def cross_check_evaluation_run(
    hypothesis_id: str, evidence_provenance: EvidenceProvenance, run_registry: EvaluationRunRegistry,
    expected_benchmark_security_id: str,
) -> EvaluationRunCrossCheckResult:
    """The full Batch 1 provenance guard for one hypothesis's evidence
    lineage. Composes all three checks; never short-circuits, so a
    caller sees every failing reason at once."""
    errors: list[str] = []

    hash_ok, hash_errors = verify_evaluation_run_identity(run_registry)
    errors.extend(hash_errors)

    linkage_ok, linkage_errors = check_provenance_matches_run(evidence_provenance, run_registry)
    errors.extend(linkage_errors)

    mode_ok, mode_errors = verify_mode_is_formal_development(run_registry)
    errors.extend(mode_errors)

    benchmark_ok, benchmark_errors = verify_benchmark_matches(run_registry, expected_benchmark_security_id)
    errors.extend(benchmark_errors)

    return EvaluationRunCrossCheckResult(
        hypothesis_id=hypothesis_id, evaluation_run_id=run_registry.evaluation_run_id,
        hash_consistent=hash_ok, linkage_ok=linkage_ok, mode_ok=mode_ok, benchmark_ok=benchmark_ok,
        errors=tuple(errors),
    )
