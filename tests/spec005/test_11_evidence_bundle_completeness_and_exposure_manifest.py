"""TEST 11 -- EvidenceInputBundle completeness and ExposureManifest
required declaration (Spec #005 v1.0 SS3/SS4, Batch 1 patch).

GPT Batch 1 review (P1 finding #3): `EvidenceInputBundle.all_ok` used
`all(r.ok for r in self.cross_check_results)`, which is vacuously True
over an empty tuple -- `EvidenceInputBundle(('hyp_a',), (), ()).all_ok`
returned True despite covering ZERO hypotheses. It must instead verify
completeness: exactly one cross-check result per declared
`hypothesis_id`, no missing, no extra, no duplicate.

GPT Batch 1 review (P1 finding #4): `ExposureManifest()` with zero args
silently defaulted `declared_unseen=True`, contradicting its own
docstring's explicit-declaration claim. `declared_unseen` is now a
required field with no default.
"""
import pytest

from backtest.models.entities import EvaluationRunCrossCheckResult, EvidenceInputBundle, ExposureManifest, validate_exposure_manifest


def _result(hypothesis_id: str, ok: bool = True) -> EvaluationRunCrossCheckResult:
    return EvaluationRunCrossCheckResult(
        hypothesis_id=hypothesis_id, evaluation_run_id="run_x",
        hash_consistent=ok, linkage_ok=ok, mode_ok=ok, benchmark_ok=ok,
    )


def test_empty_cross_check_results_is_never_vacuously_ok():
    """The exact case GPT's review reproduced:
    EvidenceInputBundle(('hyp_a',), (), ()).all_ok must be False, not
    the vacuous-truth True that `all()` over an empty iterable gives."""
    bundle = EvidenceInputBundle(hypothesis_ids=("hyp_a",), run_registries=(), cross_check_results=())
    assert bundle.all_ok is False


def test_no_declared_hypothesis_ids_is_never_vacuously_ok():
    bundle = EvidenceInputBundle(hypothesis_ids=(), run_registries=(), cross_check_results=())
    assert bundle.all_ok is False


def test_complete_matching_all_ok_results_is_ok():
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a", "hyp_b"), run_registries=(),
        cross_check_results=(_result("hyp_a"), _result("hyp_b")),
    )
    assert bundle.all_ok is True


def test_missing_a_hypothesis_id_is_rejected():
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a", "hyp_b"), run_registries=(),
        cross_check_results=(_result("hyp_a"),),
    )
    assert bundle.all_ok is False


def test_extra_untracked_hypothesis_id_is_rejected():
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a",), run_registries=(),
        cross_check_results=(_result("hyp_a"), _result("hyp_b")),
    )
    assert bundle.all_ok is False


def test_duplicate_cross_check_result_for_the_same_hypothesis_is_rejected():
    """hyp_a appears twice (masking that hyp_b was never actually
    checked) -- must be rejected, not accepted because the count happens
    to be non-empty."""
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a", "hyp_b"), run_registries=(),
        cross_check_results=(_result("hyp_a"), _result("hyp_a")),
    )
    assert bundle.all_ok is False


def test_one_failing_cross_check_result_among_complete_coverage_is_rejected():
    bundle = EvidenceInputBundle(
        hypothesis_ids=("hyp_a", "hyp_b"), run_registries=(),
        cross_check_results=(_result("hyp_a", ok=True), _result("hyp_b", ok=False)),
    )
    assert bundle.all_ok is False


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
