"""TEST 28 -- per-tranche MAE/MFE with the partial-exit-day exclusion
rule (docs/spec005_exit_amendment_v1.0.md, ACCEPTED, section 12), and the
base contract's own open/intraday/close/censored distinction (docs/
Spec_005_Backtesting_Exit_Evaluation_v1.0.md, section 17/23), reconciled
in the closure-verdict MAE/MFE delta on top of `8287ebb`."""
import math

import pytest

from backtest.exits.mae_mfe import (
    COVERAGE_MISSING_SESSION_DATA,
    COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED,
    FILL_MODE_INTRADAY,
    FILL_MODE_OPEN,
    DailyRange,
    compute_tranche_mae_mfe,
)


def test_intraday_exit_day_excludes_high_low_uses_open_and_fill():
    bars = [
        DailyRange("d1", open=100.0, high=102.0, low=98.0),
        DailyRange("d2", open=101.0, high=108.0, low=95.0),
        DailyRange("d3", open=101.0, high=115.0, low=90.0),  # exit day -- high/low must be excluded
    ]
    result = compute_tranche_mae_mfe(
        "LONG", entry_fill=100.0, bars=bars, exit_date="d3", exit_fill=110.0,
        fill_mode=FILL_MODE_INTRADAY, expected_session_dates=("d1", "d2", "d3"),
    )
    assert result.coverage == COVERAGE_PARTIAL_EXIT_DAY_EXCLUDED
    assert result.mfe == pytest.approx(0.10)  # from the exit fill itself, not d3's high of 115
    assert result.mae == pytest.approx(-0.05)  # from d2's low, not d3's low of 90


def test_no_matching_exit_day_in_bars_is_marked_missing_session_data():
    """A session the calendar expected (it is in `expected_session_dates`,
    and a real exit happened on it) but for which `bars` has nothing at
    all is a genuine DATA gap -- closure-verdict fix, post-`8287ebb`:
    this is `COVERAGE_MISSING_SESSION_DATA`, not the routine `PARTIAL_
    EXIT_DAY_EXCLUDED` label reserved for the BY-DESIGN exclusion of an
    open/intraday exit day's own high/low. The exit fill itself is still
    always included as an observation."""
    bars = [
        DailyRange("d1", open=100.0, high=102.0, low=98.0),
        DailyRange("d2", open=101.0, high=108.0, low=95.0),
    ]
    result = compute_tranche_mae_mfe(
        "LONG", entry_fill=100.0, bars=bars, exit_date="d3", exit_fill=110.0,
        fill_mode=FILL_MODE_INTRADAY, expected_session_dates=("d1", "d2", "d3"),
    )
    assert result.coverage == COVERAGE_MISSING_SESSION_DATA
    assert result.mfe == pytest.approx(0.10)  # the exit fill (110) beats d2's high (108)
    assert result.mae == pytest.approx(-0.05)


def test_short_direction_sign_convention():
    bars = [DailyRange("d1", open=100.0, high=105.0, low=95.0)]
    result = compute_tranche_mae_mfe(
        "SHORT", entry_fill=100.0, bars=bars, exit_date="d2", exit_fill=90.0,
        fill_mode=FILL_MODE_INTRADAY, expected_session_dates=("d1", "d2"),
    )
    # SHORT: a price rise (high=105) is adverse (-0.05); a price drop
    # (low=95, +0.05) and the exit fill (90, +0.10) are both favorable --
    # the exit fill is now always included and is the most favorable here.
    assert result.mae == pytest.approx(-0.05)
    assert result.mfe == pytest.approx(0.10)


def test_stop_intraday_exit_day_also_gets_the_exclusion():
    """Section 12: the exclusion applies uniformly to BOTH stop and
    target intraday exits, not just stop."""
    bars = [DailyRange("d1", open=100.0, high=105.0, low=88.0)]  # exit day itself
    result = compute_tranche_mae_mfe(
        "LONG", entry_fill=100.0, bars=bars, exit_date="d1", exit_fill=90.0,
        fill_mode=FILL_MODE_INTRADAY, expected_session_dates=("d1",),
    )
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
    the entry moment itself). No bars at all for the exit day's own
    expected session is a data gap (closure-verdict fix, post-`8287ebb`):
    `COVERAGE_MISSING_SESSION_DATA`, not `PARTIAL_EXIT_DAY_EXCLUDED`."""
    result = compute_tranche_mae_mfe(
        "LONG", 100.0, [], exit_date="d1", exit_fill=110.0,
        fill_mode=FILL_MODE_OPEN, expected_session_dates=("d1",),
    )
    assert result.mae == pytest.approx(0.0)
    assert result.mfe == pytest.approx(0.10)
    assert result.coverage == COVERAGE_MISSING_SESSION_DATA


def test_empty_bars_pure_loss_never_reports_a_positive_mfe():
    """Symmetric case: a pure loss (100 -> 90) with no bars must report
    MFE=0% (the entry moment), never a positive MFE fabricated from
    nothing -- the position was never observed above its own entry."""
    result = compute_tranche_mae_mfe(
        "LONG", 100.0, [], exit_date="d1", exit_fill=90.0,
        fill_mode=FILL_MODE_OPEN, expected_session_dates=("d1",),
    )
    assert result.mae == pytest.approx(-0.10)
    assert result.mfe == pytest.approx(0.0)
    assert result.coverage == COVERAGE_MISSING_SESSION_DATA


def test_exit_date_not_in_expected_session_dates_is_rejected():
    """A real exit always happens ON an authorized session -- `exit_date`
    absent from `expected_session_dates` entirely is a caller error, not
    a silently-tolerated shape."""
    with pytest.raises(ValueError, match="expected_session_dates"):
        compute_tranche_mae_mfe(
            "LONG", 100.0, [], exit_date="d5", exit_fill=110.0,
            fill_mode=FILL_MODE_OPEN, expected_session_dates=("d1", "d2"),
        )


def test_non_finite_entry_or_exit_fill_is_rejected():
    with pytest.raises(ValueError, match="entry_fill/exit_fill"):
        compute_tranche_mae_mfe(
            "LONG", float("nan"), [], exit_date="d1", exit_fill=110.0,
            fill_mode=FILL_MODE_OPEN, expected_session_dates=("d1",),
        )
    with pytest.raises(ValueError, match="entry_fill/exit_fill"):
        compute_tranche_mae_mfe(
            "LONG", 100.0, [], exit_date="d1", exit_fill=float("inf"),
            fill_mode=FILL_MODE_OPEN, expected_session_dates=("d1",),
        )
    with pytest.raises(ValueError, match="entry_fill/exit_fill"):
        compute_tranche_mae_mfe(
            "LONG", -5.0, [], exit_date="d1", exit_fill=110.0,
            fill_mode=FILL_MODE_OPEN, expected_session_dates=("d1",),
        )


def test_non_finite_high_or_low_inside_the_window_is_missing_session_data():
    """A recorded bar with a NaN/infinite high or low is exactly as
    unusable as a missing bar -- never silently included as if it were a
    real, finite observation (which would otherwise contaminate MAE/MFE
    with NaN and could leave coverage reading FULL)."""
    bars = [
        DailyRange("d1", open=100.0, high=float("nan"), low=98.0),  # NOT the exit day -- its high/low are never skipped by fill_mode
        DailyRange("d2", open=101.0, high=104.0, low=99.0),
    ]
    result = compute_tranche_mae_mfe(
        "LONG", 100.0, bars, exit_date="d2", exit_fill=103.0,
        fill_mode=FILL_MODE_INTRADAY, expected_session_dates=("d1", "d2"),
    )
    assert result.coverage == COVERAGE_MISSING_SESSION_DATA
    assert math.isfinite(result.mae) and math.isfinite(result.mfe)
