"""TEST 8 -- ExecutionSemanticsProfile v1 is immutable and its hash is
content-sensitive (Spec #005 v1.0 SS9, Batch 1). "The profile hash
enters run and selection identities. It is common to all compared
variants and cannot be tuned after results.\""""
from backtest.models.entities import (
    CAP_FILL_V1,
    CAP_IS_HARD_V1,
    ENTRY_FILL_V1,
    INVALIDATION_DETECTION_V1,
    INVALIDATION_FILL_V1,
    TIME_EXIT_FILL_V1,
    build_execution_semantics_profile_v1,
    execution_semantics_fingerprint,
)


def test_v1_profile_has_exactly_the_six_frozen_values():
    profile = build_execution_semantics_profile_v1()
    assert profile.entry_fill == ENTRY_FILL_V1 == "NEXT_SESSION_OPEN"
    assert profile.invalidation_detection == INVALIDATION_DETECTION_V1 == "COMPLETED_BAR_CLOSE"
    assert profile.invalidation_fill == INVALIDATION_FILL_V1 == "NEXT_SESSION_OPEN_AFTER_DETECTION"
    assert profile.time_exit_fill == TIME_EXIT_FILL_V1 == "SCHEDULED_HOLDING_BAR_CLOSE"
    assert profile.cap_fill == CAP_FILL_V1 == "SCHEDULED_MAX_HOLDING_BAR_CLOSE"
    assert profile.cap_is_hard == CAP_IS_HARD_V1 is True


def test_repeated_builds_produce_the_identical_id():
    a = build_execution_semantics_profile_v1()
    b = build_execution_semantics_profile_v1()
    assert a.profile_id == b.profile_id
    assert a.profile_hash == b.profile_hash


def test_a_different_invalidation_fill_produces_a_different_hash():
    """Fingerprint sensitivity check: the hash is not a constant string
    independent of content -- changing one field changes it."""
    v1_fp = execution_semantics_fingerprint(
        ENTRY_FILL_V1, INVALIDATION_DETECTION_V1, INVALIDATION_FILL_V1, TIME_EXIT_FILL_V1, CAP_FILL_V1, CAP_IS_HARD_V1,
    )
    tampered_fp = execution_semantics_fingerprint(
        ENTRY_FILL_V1, INVALIDATION_DETECTION_V1, "SAME_CLOSE_AS_DETECTION", TIME_EXIT_FILL_V1, CAP_FILL_V1, CAP_IS_HARD_V1,
    )
    assert v1_fp != tampered_fp


def test_cap_is_hard_toggle_changes_the_hash():
    v1_fp = execution_semantics_fingerprint(
        ENTRY_FILL_V1, INVALIDATION_DETECTION_V1, INVALIDATION_FILL_V1, TIME_EXIT_FILL_V1, CAP_FILL_V1, True,
    )
    toggled_fp = execution_semantics_fingerprint(
        ENTRY_FILL_V1, INVALIDATION_DETECTION_V1, INVALIDATION_FILL_V1, TIME_EXIT_FILL_V1, CAP_FILL_V1, False,
    )
    assert v1_fp != toggled_fp
