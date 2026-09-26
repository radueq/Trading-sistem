"""TEST 4 -- zone-boundary inequalities (Spec #005 v1.0 SS3, Batch 1):

    formation_start <= formation_end < validation_start <= validation_end < locked_oos_start
    each_evidence_run.development_end <= formation_end
    each_evidence_run.development_end < validation_start

The second/third lines are the actual methodological fix from Radu's
architecture correction: a period #003/#004 already used to FORM a
hypothesis can never also be independent validation.

GPT Batch 1 review (P1 finding #3): the original
`verify_evidence_development_ends()` only ever received `development_end`
values, never `development_start` -- it could not catch a missing/absent
start date or a start-after-end ordering bug. `EvidencePeriod`/
`verify_evidence_periods()` replace it, checking BOTH ends of each
evidence run's period.
"""
from backtest.zones.boundaries import EvidencePeriod, verify_evidence_periods, verify_zone_boundaries, verify_zone_ordering

FORMATION_START, FORMATION_END = "2020-01-01", "2024-01-01"
VALIDATION_START, VALIDATION_END = "2024-02-01", "2024-12-31"
LOCKED_OOS_START = "2025-01-01"


def _period(hypothesis_id="hyp_a", development_start=None, development_end=None) -> EvidencePeriod:
    return EvidencePeriod(hypothesis_id=hypothesis_id, development_start=development_start, development_end=development_end)


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


def test_non_iso_date_string_is_rejected_before_any_lexicographic_comparison():
    """GPT Batch 1 review (P2 finding): pure lexicographic comparison of
    non-date strings like ('a','b','c','d','e') would otherwise silently
    "pass" -- every real ISO date string happens to compare consistently,
    but nothing enforced these were dates at all."""
    ok, errors = verify_zone_ordering("a", "b", "c", "d", "e")
    assert not ok
    assert any("not a valid ISO date" in e for e in errors)


def test_development_end_equal_to_formation_end_is_allowed():
    ok, errors = verify_evidence_periods(FORMATION_END, VALIDATION_START, (_period(development_start=FORMATION_START, development_end=FORMATION_END),))
    assert ok, errors


def test_development_end_after_formation_end_is_rejected():
    ok, errors = verify_evidence_periods(FORMATION_END, VALIDATION_START, (_period(development_start=FORMATION_START, development_end="2024-06-01"),))
    assert not ok
    assert any("exceeds formation_end" in e for e in errors)


def test_development_end_equal_to_validation_start_is_rejected():
    """Strict inequality required -- equal is NOT allowed, per SS3's
    `development_end < validation_start` (not <=)."""
    ok, errors = verify_evidence_periods(FORMATION_END, VALIDATION_START, (_period(development_start=FORMATION_START, development_end=VALIDATION_START),))
    assert not ok
    assert any("does not precede validation_start" in e for e in errors)


def test_development_end_just_inside_both_bounds_passes():
    """A formation_end adjacent to validation_start, with development_end
    landing exactly on it -- satisfies BOTH `<= formation_end` and
    `< validation_start` simultaneously (unlike the module-level
    FORMATION_END/VALIDATION_START pair, which are far apart)."""
    ok, errors = verify_evidence_periods("2024-01-31", "2024-02-01", (_period(development_start="2020-01-01", development_end="2024-01-31"),))
    assert ok, errors


def test_none_development_end_is_rejected():
    ok, errors = verify_evidence_periods(FORMATION_END, VALIDATION_START, (_period(development_start=FORMATION_START, development_end=None),))
    assert not ok
    assert any("development_end is None" in e for e in errors)


def test_none_development_start_is_rejected():
    """GPT Batch 1 review (P1 finding #3): a missing `development_start`
    must be caught too, not just a missing `development_end`."""
    ok, errors = verify_evidence_periods(FORMATION_END, VALIDATION_START, (_period(development_start=None, development_end=FORMATION_END),))
    assert not ok
    assert any("development_start is None" in e for e in errors)


def test_development_start_after_development_end_is_rejected():
    """A start-after-end ordering bug within a single evidence run's own
    period -- the exact case the old development_end-only check could
    never catch."""
    ok, errors = verify_evidence_periods(
        FORMATION_END, VALIDATION_START, (_period(development_start="2023-06-01", development_end="2023-01-01"),),
    )
    assert not ok
    assert any("is after development_end" in e for e in errors)


def test_non_iso_development_dates_are_rejected():
    ok, errors = verify_evidence_periods(FORMATION_END, VALIDATION_START, (_period(development_start="not-a-date", development_end="also-not-a-date"),))
    assert not ok
    assert any("not a valid ISO date" in e for e in errors)


def test_multiple_evidence_runs_all_checked_independently():
    # "2024-01-15" trips ONLY the formation_end bound (> formation_end,
    # but still < validation_start); None (development_end) trips its
    # own separate check; "2023-01-01" is fine.
    periods = (
        _period("hyp_a", development_start="2019-01-01", development_end="2023-01-01"),
        _period("hyp_b", development_start="2023-06-01", development_end="2024-01-15"),
        _period("hyp_c", development_start="2019-01-01", development_end=None),
    )
    ok, errors = verify_evidence_periods(FORMATION_END, VALIDATION_START, periods)
    assert not ok
    assert len(errors) == 2
