"""TEST 41 -- #005's own identity cross-check recognizes a REAL v2
`evaluation_run_id` (minimal #003 v2 -> #005 compatibility delta,
joint remediation design 003+004 section 12; decision registry I1;
authorized 2026-10-07).

Previously (Stage 2, as corrected through round 3): `verify_
evaluation_run_identity()` recomputed ONLY the legacy 8-field recipe,
so a genuine v2 run_id always failed -- a KNOWN, FLAGGED, deliberately
NOT-fixed consequence at the time (Spec #005-side code, out of Stage
2's own authorized scope). It now dispatches by the registry's own
`run_id_scheme_version`: `None` -> the unchanged legacy recipe (TEST 1
covers this, untouched); `"v2"` -> the new 14-field v2 recipe; anything
else -> refused outright, with NO fallback to the legacy recipe.

`tests/spec003/test_46_...py` proves the SAME dispatcher against a
REAL `run_evaluation()` output, end to end. This file is #005's own
white-box coverage of the dispatcher's edge cases, mirroring TEST 1's
own style for the legacy recipe.
"""
import dataclasses

from backtest.provenance.evaluation_run import (
    V2_RUN_ID_FIELDS,
    recompute_legacy_evaluation_run_id,
    recompute_v2_evaluation_run_id,
    verify_evaluation_run_identity,
)

from spec005.conftest import build_v2_run_registry


def test_genuine_v2_registry_passes():
    registry = build_v2_run_registry()
    ok, errors = verify_evaluation_run_identity(registry)
    assert ok, errors


def test_recompute_matches_the_registrys_own_v2_id():
    registry = build_v2_run_registry()
    assert recompute_v2_evaluation_run_id(registry) == registry.evaluation_run_id


def test_tampered_security_ids_with_stale_id_is_rejected():
    registry = build_v2_run_registry()
    tampered = dataclasses.replace(registry, security_ids=("SEC_A", "SEC_B", "SEC_C"))
    ok, errors = verify_evaluation_run_identity(tampered)
    assert not ok
    assert any("does not match the recomputed v2 hash" in e for e in errors)


def test_tampered_calendar_id_with_stale_id_is_rejected():
    registry = build_v2_run_registry()
    tampered = dataclasses.replace(registry, calendar_id="cal_a_different_one")
    ok, errors = verify_evaluation_run_identity(tampered)
    assert not ok


def test_only_the_fourteen_v2_fields_affect_the_hash():
    """Changing a field OUTSIDE the 14-field v2 recipe (e.g.
    discovery_engine_version, bootstrap_iterations) must NOT change the
    recomputed id -- proves the recipe really is exactly those 14
    fields, mirroring TEST 1's analogous legacy-recipe check."""
    registry = build_v2_run_registry()
    same_hash_different_metadata = dataclasses.replace(
        registry, discovery_engine_version="v9.9.9", bootstrap_iterations=1,
        comparison_iterations=1, multiple_testing_method="BONFERRONI",
    )
    assert recompute_v2_evaluation_run_id(same_hash_different_metadata) == registry.evaluation_run_id
    ok, errors = verify_evaluation_run_identity(same_hash_different_metadata)
    assert ok, errors


def test_horizons_are_sorted_before_hashing_same_as_the_producer():
    """`evaluation/engine.py`'s `run_evaluation()` sorts `horizons`
    before hashing but retains the registry's own `horizons` field in
    ORIGINAL order -- a registry built from caller-supplied, UNSORTED
    horizons must still verify correctly, and recomputing from the
    raw unsorted field (skipping the sort) must NOT match, proving the
    sort step is load-bearing, not incidental."""
    registry = build_v2_run_registry(horizons=(5, 1, 10, 2, 3))
    assert registry.horizons == (5, 1, 10, 2, 3)  # retained in original, unsorted order
    ok, errors = verify_evaluation_run_identity(registry)
    assert ok, errors

    from evaluation.registry.runs import build_run_id
    fields = {name: getattr(registry, name) for name in V2_RUN_ID_FIELDS}
    naive_unsorted_recompute = build_run_id(**fields)  # horizons left unsorted, deliberately wrong
    assert naive_unsorted_recompute != registry.evaluation_run_id


def test_calendar_id_none_is_a_legitimate_v2_value_not_a_missing_field():
    """A genuine v2 run with no calendar resolved (e.g. EXPLORATORY
    mode without calendar_registry/calendar_id) legitimately carries
    calendar_id=None -- this must verify correctly, never be refused
    as if it were a malformed v2 claim."""
    registry = build_v2_run_registry(calendar_id=None)
    ok, errors = verify_evaluation_run_identity(registry)
    assert ok, errors


def test_v2_claim_with_missing_required_security_ids_is_refused_before_any_hash_check():
    registry = build_v2_run_registry(security_ids=())
    ok, errors = verify_evaluation_run_identity(registry)
    assert not ok
    assert any("required field" in e and "security_ids" in e for e in errors)


def test_v2_claim_with_missing_required_data_as_of_is_refused_before_any_hash_check():
    registry = build_v2_run_registry(data_as_of=None)
    ok, errors = verify_evaluation_run_identity(registry)
    assert not ok
    assert any("required field" in e and "data_as_of" in e for e in errors)


def test_unknown_run_id_scheme_version_is_refused_outright():
    registry = build_v2_run_registry(run_id_scheme_version="v3")
    ok, errors = verify_evaluation_run_identity(registry)
    assert not ok
    assert any("not a recognized scheme" in e for e in errors)


def test_v2_claim_that_fails_its_own_check_never_falls_back_to_the_legacy_recipe():
    """A registry claiming run_id_scheme_version='v2' whose id happens
    to equal what the LEGACY 8-field recipe would produce (not what the
    v2 14-field recipe produces) must still be REFUSED -- proving the
    dispatcher never silently re-tries the legacy recipe for a v2 claim
    that fails its own."""
    registry = build_v2_run_registry()
    legacy_shaped_id = recompute_legacy_evaluation_run_id(registry)
    assert legacy_shaped_id != registry.evaluation_run_id  # sanity: the two recipes genuinely diverge
    masquerading = dataclasses.replace(registry, evaluation_run_id=legacy_shaped_id)

    ok, errors = verify_evaluation_run_identity(masquerading)
    assert not ok, (
        "a v2-scheme registry whose id matches the LEGACY recipe must still be refused -- accepting it "
        "would mean the dispatcher silently fell back to the legacy recipe for a v2 claim"
    )
    assert any("does not match the recomputed v2 hash" in e for e in errors)
