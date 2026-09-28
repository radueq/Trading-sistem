"""TEST 28 -- per-tranche MAE/MFE with the partial-exit-day exclusion
rule (docs/spec005_exit_amendment_v1.0.md, ACCEPTED, section 12)."""
import pytest

from backtest.exits.mae_mfe import COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED, DailyRange, compute_tranche_mae_mfe


def test_intraday_exit_day_excludes_high_low_uses_open_and_fill():
    bars = [
        DailyRange("d1", open=100.0, high=102.0, low=98.0),
        DailyRange("d2", open=101.0, high=108.0, low=95.0),
        DailyRange("d3", open=101.0, high=115.0, low=90.0),  # exit day -- high/low must be excluded
    ]
    result = compute_tranche_mae_mfe("LONG", entry_fill=100.0, bars=bars, exit_date="d3", exit_fill=110.0)
    assert result.coverage == COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
    assert result.mfe == pytest.approx(0.10)  # from the exit fill itself, not d3's high of 115
    assert result.mae == pytest.approx(-0.05)  # from d2's low, not d3's low of 90


def test_no_matching_exit_day_in_bars_is_marked_partial_not_full():
    """GPT review round 2, finding #6b: absence of the exit day's own bar
    proves nothing about coverage completeness -- it can never be
    reported FULL. The exit fill itself is still always included as an
    observation."""
    bars = [
        DailyRange("d1", open=100.0, high=102.0, low=98.0),
        DailyRange("d2", open=101.0, high=108.0, low=95.0),
    ]
    result = compute_tranche_mae_mfe("LONG", entry_fill=100.0, bars=bars, exit_date="d3", exit_fill=110.0)
    assert result.coverage == COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
    assert result.mfe == pytest.approx(0.10)  # the exit fill (110) beats d2's high (108)
    assert result.mae == pytest.approx(-0.05)


def test_short_direction_sign_convention():
    bars = [DailyRange("d1", open=100.0, high=105.0, low=95.0)]
    result = compute_tranche_mae_mfe("SHORT", entry_fill=100.0, bars=bars, exit_date="d2", exit_fill=90.0)
    # SHORT: a price rise (high=105) is adverse (-0.05); a price drop
    # (low=95, +0.05) and the exit fill (90, +0.10) are both favorable --
    # the exit fill is now always included and is the most favorable here.
    assert result.mae == pytest.approx(-0.05)
    assert result.mfe == pytest.approx(0.10)


def test_stop_intraday_exit_day_also_gets_the_exclusion():
    """Section 12: the exclusion applies uniformly to BOTH stop and
    target intraday exits, not just stop."""
    bars = [DailyRange("d1", open=100.0, high=105.0, low=88.0)]  # exit day itself
    result = compute_tranche_mae_mfe("LONG", entry_fill=100.0, bars=bars, exit_date="d1", exit_fill=90.0)
    assert result.coverage == COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
    # Only open (0.0) and the stop fill (-0.10) are valid -- not the day's low of 88 (-0.12).
    assert result.mae == pytest.approx(-0.10)
    assert result.mfe == pytest.approx(0.0)


def test_empty_bars_still_includes_the_known_zero_excursion_at_entry():
    """GPT review round 3, finding #4: the excursion AT ENTRY is always
    known to be exactly 0.0 (price == entry_fill at that moment), included
    unconditionally regardless of `bars`. A favorable exit (100 -> 110)
    with no bars at all must report MAE=0%/MFE=+10% -- NOT both +10%,
    which would falsely claim the position was never below entry by less
    than its final gain (0% is the true worst point actually observed:
    the entry moment itself)."""
    result = compute_tranche_mae_mfe("LONG", 100.0, [], exit_date="d1", exit_fill=110.0)
    assert result.mae == pytest.approx(0.0)
    assert result.mfe == pytest.approx(0.10)
    assert result.coverage == COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED


def test_empty_bars_pure_loss_never_reports_a_positive_mfe():
    """Symmetric case: a pure loss (100 -> 90) with no bars must report
    MFE=0% (the entry moment), never a positive MFE fabricated from
    nothing -- the position was never observed above its own entry."""
    result = compute_tranche_mae_mfe("LONG", 100.0, [], exit_date="d1", exit_fill=90.0)
    assert result.mae == pytest.approx(-0.10)
    assert result.mfe == pytest.approx(0.0)
