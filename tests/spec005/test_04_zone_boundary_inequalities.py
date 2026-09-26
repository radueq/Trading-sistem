"""TEST 4 -- zone-boundary inequalities (Spec #005 v1.0 SS3, Batch 1):

    formation_start <= formation_end < validation_start <= validation_end < locked_oos_start
    each_evidence_run.development_end <= formation_end
    each_evidence_run.development_end < validation_start

The second/third lines are the actual methodological fix from Radu's
architecture correction: a period #003/#004 already used to FORM a
hypothesis can never also be independent validation."""
from backtest.zones.boundaries import verify_evidence_development_ends, verify_zone_boundaries, verify_zone_ordering

FORMATION_START, FORMATION_END = "2020-01-01", "2024-01-01"
VALIDATION_START, VALIDATION_END = "2024-02-01", "2024-12-31"
LOCKED_OOS_START = "2025-01-01"


def test_valid_ordering_with_no_evidence_runs_passes():
    ok, errors = verify_zone_boundaries(FORMATION_START, FORMATION_END, VALIDATION_START, VALIDATION_END, LOCKED_OOS_START, ())
    assert ok, errors


def test_formation_end_not_before_validation_start_is_rejected():
    ok, errors = verify_zone_ordering(FORMATION_START, VALIDATION_START, FORMATION_END, VALIDATION_END, LOCKED_OOS_START)
    assert not ok
    assert any("zone ordering violated" in e for e in errors)


def test_validation_end_not_before_locked_oos_start_is_rejected():
    ok, errors = verify_zone_ordering(FORMATION_START, FORMATION_END, VALIDATION_START, LOCKED_OOS_START, VALIDATION_END)
    assert not ok


def test_development_end_equal_to_formation_end_is_allowed():
    ok, errors = verify_evidence_development_ends(FORMATION_END, VALIDATION_START, (FORMATION_END,))
    assert ok, errors


def test_development_end_after_formation_end_is_rejected():
    ok, errors = verify_evidence_development_ends(FORMATION_END, VALIDATION_START, ("2024-06-01",))
    assert not ok
    assert any("exceeds formation_end" in e for e in errors)


def test_development_end_equal_to_validation_start_is_rejected():
    """Strict inequality required -- equal is NOT allowed, per SS3's
    `development_end < validation_start` (not <=)."""
    ok, errors = verify_evidence_development_ends(FORMATION_END, VALIDATION_START, (VALIDATION_START,))
    assert not ok
    assert any("does not precede validation_start" in e for e in errors)


def test_development_end_just_inside_both_bounds_passes():
    """A formation_end adjacent to validation_start, with development_end
    landing exactly on it -- satisfies BOTH `<= formation_end` and
    `< validation_start` simultaneously (unlike the module-level
    FORMATION_END/VALIDATION_START pair, which are far apart)."""
    ok, errors = verify_evidence_development_ends("2024-01-31", "2024-02-01", ("2024-01-31",))
    assert ok, errors


def test_none_development_end_is_rejected():
    ok, errors = verify_evidence_development_ends(FORMATION_END, VALIDATION_START, (None,))
    assert not ok
    assert any("development_end is None" in e for e in errors)


def test_multiple_evidence_runs_all_checked_independently():
    # "2024-01-15" trips ONLY the formation_end bound (> formation_end,
    # but still < validation_start); None trips its own separate check;
    # "2023-01-01" is fine.
    ok, errors = verify_evidence_development_ends(FORMATION_END, VALIDATION_START, ("2023-01-01", "2024-01-15", None))
    assert not ok
    assert len(errors) == 2
