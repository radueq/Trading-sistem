"""Spec #005 v1.0 SS4 -- evidence-provenance preflight guard (Batch 1).

Three independent checks compose the full guard for one (hypothesis,
EvaluationRunRegistry) pair:

1. Content-address consistency: recompute `evaluation.registry.runs.
   build_run_id()` and compare to the supplied registry's own
   `evaluation_run_id` -- dispatched by the registry's own `run_id_
   scheme_version` (minimal #003 v2 -> #005 compatibility delta,
   joint remediation design 003+004 section 12, decision registry I1,
   authorized 2026-10-07):
   - `None` (every registry predating Spec #003's S2 fingerprint
     change): the ORIGINAL 8-field legacy recipe (confirmed at commit
     cfa0809, engine.py:370-376), UNCHANGED by this delta -- every
     historical identity verifies exactly as before.
   - `"v2"` (registry I1's own field set): the 14-field v2 recipe --
     the 8 legacy fields PLUS `security_ids`, `benchmark_security_id`,
     `data_as_of`, `horizons`, `calendar_id`, `run_id_scheme_version`,
     reconstructed EXACTLY as `evaluation/engine.py`'s `run_evaluation()`
     itself feeds `build_run_id()`. A registry claiming `"v2"` with a
     required v2 field still left at its pre-Stage-2 backward-compat
     default (`security_ids=()`, `data_as_of=None`) is refused BEFORE
     any hash comparison -- it was never produced by a genuine v2 run.
   - anything else: refused outright, with NO fallback to the legacy
     recipe -- an unrecognized scheme is never silently treated as if
     it were historical, and a v2 claim that fails its own v2 check is
     never re-tried against the legacy one either.
   SS4 is explicit about what this does and does NOT prove, under
   EITHER recipe: "Hash recomputation verifies only that the supplied
   fields produce the supplied ID. It does not authenticate the
   object, prove that a historical run occurred, establish that data
   were unseen, or detect coordinated replacement of both fields and
   ID. It is not an anti-forgery certificate."
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
# computed (Spec #005 SS4). UNCHANGED by the v2 delta below -- every
# historical (pre-Stage-2) identity recomputes exactly as it always
# did.
LEGACY_RUN_ID_FIELDS = (
    "development_start", "development_end", "timeframe", "signature_set_id",
    "discovery_config_version", "evaluation_config_version", "bootstrap_seed", "comparison_seed",
)

# The EXACT 14 keyword arguments evaluation/engine.py's run_evaluation()
# passes to build_run_id() once `run_id_scheme_version == "v2"`
# (engine.py:518-528, registry I1's own S2 field set) -- the 8 legacy
# fields above PLUS these 6.
_V2_ADDITIONAL_RUN_ID_FIELDS = (
    "security_ids", "benchmark_security_id", "data_as_of", "horizons", "calendar_id", "run_id_scheme_version",
)
V2_RUN_ID_FIELDS = LEGACY_RUN_ID_FIELDS + _V2_ADDITIONAL_RUN_ID_FIELDS

# Fields a GENUINE v2 run_evaluation() output always carries, never
# left at their pre-Stage-2 backward-compat default. `calendar_id` is
# deliberately EXCLUDED: a real v2 run legitimately carries
# `calendar_id=None` whenever no calendar was resolved (e.g.
# EXPLORATORY mode without calendar_registry/calendar_id), so its
# absence is never evidence of a malformed v2 claim.
_V2_REQUIRED_FIELDS = ("security_ids", "benchmark_security_id", "data_as_of")

KNOWN_RUN_ID_SCHEME_VERSIONS = (None, "v2")


def recompute_legacy_evaluation_run_id(run_registry: EvaluationRunRegistry) -> str:
    fields = {name: getattr(run_registry, name) for name in LEGACY_RUN_ID_FIELDS}
    return build_run_id(**fields)


def recompute_v2_evaluation_run_id(run_registry: EvaluationRunRegistry) -> str:
    """Reconstructs the v2 fingerprint from EXACTLY the fields
    `run_evaluation()` feeds `build_run_id()` under `run_id_scheme_
    version == "v2"` -- including the producer's own `horizons=tuple(
    sorted(horizons))` normalization (engine.py:525), which
    `EvaluationRunRegistry.horizons` itself retains in the run's
    ORIGINAL (possibly unsorted) input order (engine.py:570). Recomputing
    from the registry's raw, unsorted `horizons` would silently produce
    the WRONG hash for any run whose caller passed horizons out of
    sorted order -- sorting again here is what makes this a genuine
    reconstruction of what the producer actually hashed, not an
    approximation of it."""
    fields = {name: getattr(run_registry, name) for name in V2_RUN_ID_FIELDS}
    fields["horizons"] = tuple(sorted(fields["horizons"]))
    return build_run_id(**fields)


def verify_evaluation_run_identity(run_registry: EvaluationRunRegistry) -> tuple[bool, tuple[str, ...]]:
    """See module docstring, point 1 -- dispatches by `run_registry.
    run_id_scheme_version`; this remains a CONSISTENCY check, never an
    authenticity or historical-execution proof (Spec #005 SS4), under
    either recipe."""
    scheme = run_registry.run_id_scheme_version

    if scheme is None:
        recomputed = recompute_legacy_evaluation_run_id(run_registry)
        if recomputed != run_registry.evaluation_run_id:
            return False, (
                f"evaluation_run_id={run_registry.evaluation_run_id!r} does not match the recomputed "
                f"legacy hash {recomputed!r} for the supplied 8-field recipe -- this EvaluationRunRegistry "
                f"was not produced by evaluation.engine.run_evaluation() with these exact field values "
                f"(Spec #005 SS4)",
            )
        return True, ()

    if scheme == "v2":
        missing = tuple(name for name in _V2_REQUIRED_FIELDS if not getattr(run_registry, name))
        if missing:
            return False, (
                f"run_id_scheme_version='v2' but required field(s) {missing!r} are still at their "
                f"pre-Stage-2 backward-compat default -- this EvaluationRunRegistry was never produced "
                f"by a genuine v2 run_evaluation() output (Spec #005 SS4)",
            )
        recomputed = recompute_v2_evaluation_run_id(run_registry)
        if recomputed != run_registry.evaluation_run_id:
            return False, (
                f"evaluation_run_id={run_registry.evaluation_run_id!r} does not match the recomputed "
                f"v2 hash {recomputed!r} for the supplied 14-field recipe -- this EvaluationRunRegistry "
                f"was not produced by evaluation.engine.run_evaluation() with these exact field values "
                f"(Spec #005 SS4)",
            )
        return True, ()

    # Unrecognized scheme -- refused outright, NEVER falls back to the
    # legacy recipe (a v2-shaped claim that fails its own check is not
    # re-tried against the 8-field one either, since that branch above
    # already returned).
    return False, (
        f"run_id_scheme_version={scheme!r} is not a recognized scheme {KNOWN_RUN_ID_SCHEME_VERSIONS!r} -- "
        f"refusing to verify under any scheme, never falling back to the legacy recipe for an "
        f"unrecognized one (Spec #005 SS4)",
    )


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
