"""TEST 29 -- StopManagedExecutionSemanticsProfile v1 (docs/spec005_exit_
amendment_v1.0.md, ACCEPTED, section 7): a wholly separate, independently
versioned structure from `backtest.models.entities.ExecutionSemanticsProfile`."""
import dataclasses

from backtest.exits.entities import (
    PARTIAL_PROFIT_FILL_V1,
    STOP_LOSS_DETECTION_V1,
    STOP_LOSS_FILL_V1,
    build_stop_managed_execution_semantics_profile_v1,
    verify_stop_managed_execution_semantics_profile_v1,
)
from backtest.models.entities import build_execution_semantics_profile_v1, execution_semantics_fingerprint


def test_v1_profile_has_the_three_frozen_fields():
    profile = build_stop_managed_execution_semantics_profile_v1()
    assert profile.stop_loss_detection == STOP_LOSS_DETECTION_V1 == "INTRA_BAR_LOW_HIGH_BREACH"
    assert profile.stop_loss_fill == STOP_LOSS_FILL_V1 == "SAME_BAR_AT_LEVEL_OR_WORSE_OPEN"
    assert profile.partial_profit_fill == PARTIAL_PROFIT_FILL_V1 == "SAME_BAR_AT_TARGET_OR_BETTER_OPEN"
    assert profile.profile_id.startswith("smxp_")


def test_verification_passes_for_the_real_v1_profile():
    ok, errors = verify_stop_managed_execution_semantics_profile_v1(build_stop_managed_execution_semantics_profile_v1())
    assert ok, errors


def test_tampered_field_fails_content_address_verification():
    profile = build_stop_managed_execution_semantics_profile_v1()
    tampered = dataclasses.replace(profile, stop_loss_fill="SOMETHING_ELSE")
    ok, errors = verify_stop_managed_execution_semantics_profile_v1(tampered)
    assert not ok
    assert any("stop_loss_fill" in e for e in errors)


def test_deterministic_construction():
    a = build_stop_managed_execution_semantics_profile_v1()
    b = build_stop_managed_execution_semantics_profile_v1()
    assert a == b


def test_old_execution_semantics_profile_is_completely_unaffected():
    """Section 7: `ExecutionSemanticsProfile`/`execution_semantics_
    fingerprint()` get zero lines changed -- the old profile_id/hash is
    identical to what it always was, unaffected by the new structure
    existing alongside it."""
    old_profile = build_execution_semantics_profile_v1()
    fp = execution_semantics_fingerprint(
        old_profile.entry_fill, old_profile.invalidation_detection, old_profile.invalidation_fill,
        old_profile.time_exit_fill, old_profile.cap_fill, old_profile.cap_is_hard,
    )
    assert fp == execution_semantics_fingerprint(
        "NEXT_SESSION_OPEN", "COMPLETED_BAR_CLOSE", "NEXT_SESSION_OPEN_AFTER_DETECTION",
        "SCHEDULED_HOLDING_BAR_CLOSE", "SCHEDULED_MAX_HOLDING_BAR_CLOSE", True,
    )
    # The new profile has no cap_is_hard field at all -- structurally
    # inapplicable, never implicitly inherited.
    new_profile = build_stop_managed_execution_semantics_profile_v1()
    assert not hasattr(new_profile, "cap_is_hard")
