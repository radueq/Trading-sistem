"""TEST 14 -- StageAccessBoundary (Spec #005 v1.0 SS3/SS6, Batch 2).

"Selection must not inspect or hash validation/OOS price content." "A
plan can commit future window boundaries without opening those data."
"LOCKED_OOS: No reads, evaluation or release in #005 V1." Because #001's
PIT gateway has no LOWER as_of bound -- it always returns full history
up to `as_of` -- bounding the single UPPER edge is both necessary and
sufficient.
"""
import pytest

from backtest.models.entities import (
    DEVELOPMENT_VALIDATION,
    FORMATION_SELECTION,
    LOCKED_OOS,
    LockedOOSAccessError,
    OutOfScopeAccessError,
    StageAccessBoundary,
)


def test_formation_selection_boundary_accepts_as_of_within_scope():
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of="2024-01-31")
    boundary.require_as_of_in_scope("2024-01-31")  # must not raise
    boundary.require_as_of_in_scope("2020-01-01")  # arbitrary warm-up before the zone -- also fine


def test_formation_selection_boundary_rejects_as_of_past_max():
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of="2024-01-31")
    with pytest.raises(OutOfScopeAccessError, match="OUT_OF_SCOPE_ACCESS"):
        boundary.require_as_of_in_scope("2024-02-01")


def test_development_validation_boundary_rejects_as_of_past_its_own_max():
    boundary = StageAccessBoundary(zone=DEVELOPMENT_VALIDATION, max_as_of="2024-02-29")
    boundary.require_as_of_in_scope("2024-02-29")  # must not raise
    with pytest.raises(OutOfScopeAccessError, match="OUT_OF_SCOPE_ACCESS"):
        boundary.require_as_of_in_scope("2024-03-01")


def test_locked_oos_boundary_can_never_be_constructed():
    """The literal "access spy forbids OOS queries" guarantee, made
    structural: there is no way to even build an object that would
    permit a Locked OOS read, let alone execute one (SS3: "No reads,
    evaluation or release in #005 V1")."""
    with pytest.raises(LockedOOSAccessError):
        StageAccessBoundary(zone=LOCKED_OOS, max_as_of="2024-03-01")


def test_unknown_zone_is_rejected():
    with pytest.raises(ValueError):
        StageAccessBoundary(zone="SOME_OTHER_ZONE", max_as_of="2024-01-31")


def test_non_iso_max_as_of_is_rejected_at_construction():
    with pytest.raises(ValueError):
        StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of="2024W011")


def test_non_iso_queried_as_of_is_rejected_not_silently_compared():
    boundary = StageAccessBoundary(zone=FORMATION_SELECTION, max_as_of="2024-01-31")
    with pytest.raises(OutOfScopeAccessError):
        boundary.require_as_of_in_scope("2024-01-02junk")
