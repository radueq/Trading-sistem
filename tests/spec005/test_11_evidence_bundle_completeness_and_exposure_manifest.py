"""TEST 11 -- EvidenceInputBundle completeness and ExposureManifest
required declaration (Spec #005 v1.0 SS3/SS4, Batch 1 patch).

GPT Batch 1 review, round 1 (P1 finding #3): `EvidenceInputBundle.all_ok`
used `all(r.ok for r in self.cross_check_results)`, which is vacuously
True over an empty tuple -- `EvidenceInputBundle(('hyp_a',), (), ()).all_ok`
returned True despite covering ZERO hypotheses. Round 1's fix required
completeness against `hypothesis_ids` but still ignored `run_registries`
entirely and used set-based comparisons that silently collapse
duplicates.

GPT Batch 1 review, round 2 (P1 finding, still open): a cross-check
result marked `ok=True` for a hypothesis whose referenced
`evaluation_run_id` was never actually archived in `run_registries`
(`run_registries=()`) still produced `all_ok=True`. And a duplicate
entry in the DECLARED `hypothesis_ids` cohort itself (not just in
`cross_check_results`) was invisible to the old set-based comparison.
The current implementation requires: no duplicate declared
`hypothesis_ids`, no duplicate archived `run_registries` (by
`evaluation_run_id`), exactly one cross-check result per declared
hypothesis, and every result's `evaluation_run_id` actually present in
`run_registries` -- WITHOUT imposing a one-to-one relationship between
hypotheses and registries (several hypotheses may legitimately share
one archived run).

GPT Batch 1 review, round 1 (P1 finding #4): `ExposureManifest()` with
zero args silently defaulted `declared_unseen=True`, contradicting its
own docstring's explicit-declaration claim. `declared_unseen` is now a
required field with no default.
"""
import pytest

from backtest.models.entities import EvaluationRunCrossCheckResult, EvidenceInputBundle, ExposureManifest, validate_exposure_manifest

from spec005.conftest import build_run_registry


def _result(hypothesis_id: str, run_registry, ok: bool = True) -> EvaluationRunCrossCheckResult:
    return EvaluationRunCrossCheckResult(
        hypothesis_id=hypothesis_id, evaluation_run_id=run_registry.evaluation_run_id,
        hash_consistent=ok, linkage_ok=ok, mode_ok=ok, benchmark_ok=ok,
    )


def test_empty_cross_check_results_is_never_vacuously_ok():
    """The exact case GPT's round-1 review reproduced:
    EvidenceInputBundle(('hyp_a',), (), ()).all_ok must be False, not
    the vacuous-truth True that `all()` over an empty iterable gives."""
    bundle = EvidenceInputBundle(hypothesis_ids=("hyp_a",), run_registries=(), cross_check_results=())
    assert bundle.all_ok is False


def test_no_declared_hypothesis_ids_is_never_vacuously_ok():
    bundle = EvidenceInputBundle(hypothesis_ids=(), run_registries=(), cross_check_results=())
    assert bundle.all_ok is False


def test_complete_matching_all_ok_results_is_ok():
    registry_a = build_run_registry()
    registry_b = build_run_registry(development_start="2019-01-01")  # distinct hash fields -> distinct run id
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a", "hyp_b"), run_registries=(registry_a, registry_b),
        cross_check_results=(_result("hyp_a", registry_a), _result("hyp_b", registry_b)),
    )
    assert bundle.all_ok is True


def test_missing_a_hypothesis_id_is_rejected():
    registry_a = build_run_registry()
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a", "hyp_b"), run_registries=(registry_a,),
        cross_check_results=(_result("hyp_a", registry_a),),
    )
    assert bundle.all_ok is False


def test_extra_untracked_hypothesis_id_is_rejected():
    registry_a = build_run_registry()
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a",), run_registries=(registry_a,),
        cross_check_results=(_result("hyp_a", registry_a), _result("hyp_b", registry_a)),
    )
    assert bundle.all_ok is False


def test_duplicate_cross_check_result_for_the_same_hypothesis_is_rejected():
    """hyp_a appears twice (masking that hyp_b was never actually
    checked) -- must be rejected, not accepted because the count happens
    to be non-empty."""
    registry_a = build_run_registry()
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a", "hyp_b"), run_registries=(registry_a,),
        cross_check_results=(_result("hyp_a", registry_a), _result("hyp_a", registry_a)),
    )
    assert bundle.all_ok is False


def test_one_failing_cross_check_result_among_complete_coverage_is_rejected():
    registry_a = build_run_registry()
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a", "hyp_b"), run_registries=(registry_a,),
        cross_check_results=(_result("hyp_a", registry_a, ok=True), _result("hyp_b", registry_a, ok=False)),
    )
    assert bundle.all_ok is False


def test_referenced_run_registry_missing_from_archive_is_rejected():
    """GPT round-2 review: a cross-check result marked ok=True but whose
    evaluation_run_id was never actually archived in run_registries must
    not be all_ok -- the archive is incomplete, however clean the
    cross-check result itself looks."""
    registry_a = build_run_registry()
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a",), run_registries=(),
        cross_check_results=(_result("hyp_a", registry_a, ok=True),),
    )
    assert bundle.all_ok is False


def test_duplicate_declared_hypothesis_id_is_rejected():
    """GPT round-2 review: the declared cohort itself (hypothesis_ids)
    must not contain the same hypothesis twice -- the old set-based
    comparison silently collapsed ("hyp_a", "hyp_a") into {"hyp_a"} and
    let a single cross-check result "cover" both slots."""
    registry_a = build_run_registry()
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a", "hyp_a"), run_registries=(registry_a,),
        cross_check_results=(_result("hyp_a", registry_a),),
    )
    assert bundle.all_ok is False


def test_duplicate_archived_registries_for_the_same_run_id_is_rejected():
    """Two different archived objects claiming the same evaluation_run_id
    is ambiguous -- never valid, regardless of whether they happen to be
    the identical object."""
    registry_a = build_run_registry()
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a",), run_registries=(registry_a, registry_a),
        cross_check_results=(_result("hyp_a", registry_a),),
    )
    assert bundle.all_ok is False


def test_multiple_hypotheses_legitimately_sharing_one_archived_run_is_ok():
    """GPT round-2 review, explicit instruction: no one-to-one
    relationship is imposed between hypotheses and run_registries -- two
    hypotheses can legitimately reference the SAME archived run."""
    registry_a = build_run_registry()
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a", "hyp_b"), run_registries=(registry_a,),
        cross_check_results=(_result("hyp_a", registry_a), _result("hyp_b", registry_a)),
    )
    assert bundle.all_ok is True


def test_declared_unseen_is_a_required_field_with_no_default():
    with pytest.raises(TypeError):
        ExposureManifest()  # type: ignore[call-arg]


def test_explicit_declared_unseen_true_with_no_disclosures_passes():
    ok, errors = validate_exposure_manifest(ExposureManifest(declared_unseen=True))
    assert ok, errors


def test_declared_unseen_true_with_disclosures_is_still_rejected():
    manifest = ExposureManifest(declared_unseen=True, prior_validation_disclosures=("a prior peek",))
    ok, errors = validate_exposure_manifest(manifest)
    assert not ok
    assert any("invalidates an UNSEEN claim" in e for e in errors)
