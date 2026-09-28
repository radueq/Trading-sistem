"""TEST 31 -- numeric validation hardening (GPT review round 2, finding
#6): `update_trailing_stop_at_close()` must flag `trailing_path_
incomplete` for ANY non-usable ATR (not just `None`), and
`compute_initial_protection()` must reject non-finite computed levels,
not just backwards-ordered ones."""
import math

import pytest

from backtest.exits.entities import ENTRY_INVALID_PROTECTIVE_LEVELS, StopManagedPosition
from backtest.exits.protection import compute_initial_protection
from backtest.exits.session import update_trailing_stop_at_close


def _base_position(**overrides) -> StopManagedPosition:
    fields = dict(
        security_id="SEC_X", direction="LONG", entry_date="2024-01-11", signal_date="2024-01-10",
        entry_fill_price=100.0, k=2.0, r_multiple=2.0, fraction=0.5,
        active_stop=90.0, initial_risk=10.0, target_price=120.0,
    )
    fields.update(overrides)
    return StopManagedPosition(**fields)


# --------------------------------------------------------------------------
# update_trailing_stop_at_close
# --------------------------------------------------------------------------

def test_none_atr_marks_trailing_path_incomplete():
    pos = _base_position()
    new_pos = update_trailing_stop_at_close(pos, close_price=105.0, atr_today=None)
    assert new_pos.trailing_path_incomplete is True
    assert new_pos.active_stop == pos.active_stop  # never relaxed


def test_zero_atr_marks_trailing_path_incomplete():
    pos = _base_position()
    new_pos = update_trailing_stop_at_close(pos, close_price=105.0, atr_today=0.0)
    assert new_pos.trailing_path_incomplete is True
    assert new_pos.active_stop == pos.active_stop


def test_negative_atr_marks_trailing_path_incomplete():
    pos = _base_position()
    new_pos = update_trailing_stop_at_close(pos, close_price=105.0, atr_today=-3.0)
    assert new_pos.trailing_path_incomplete is True
    assert new_pos.active_stop == pos.active_stop


def test_non_finite_atr_marks_trailing_path_incomplete():
    pos = _base_position()
    for bad in (math.inf, -math.inf, math.nan):
        new_pos = update_trailing_stop_at_close(pos, close_price=105.0, atr_today=bad)
        assert new_pos.trailing_path_incomplete is True
        assert new_pos.active_stop == pos.active_stop


def test_non_finite_close_price_marks_trailing_path_incomplete():
    pos = _base_position()
    new_pos = update_trailing_stop_at_close(pos, close_price=math.nan, atr_today=3.0)
    assert new_pos.trailing_path_incomplete is True
    assert new_pos.active_stop == pos.active_stop


def test_valid_positive_finite_atr_updates_normally():
    pos = _base_position()
    new_pos = update_trailing_stop_at_close(pos, close_price=105.0, atr_today=3.0)
    assert new_pos.trailing_path_incomplete is False
    assert new_pos.active_stop == pytest.approx(max(90.0, 105.0 - 2.0 * 3.0))  # = max(90, 99) = 99


def test_closed_position_is_never_touched():
    pos = _base_position(closed=True, remaining_quantity=0.0)
    new_pos = update_trailing_stop_at_close(pos, close_price=105.0, atr_today=None)
    assert new_pos == pos
    assert new_pos.trailing_path_incomplete is False


# --------------------------------------------------------------------------
# compute_initial_protection
# --------------------------------------------------------------------------

def test_non_finite_atr_reexpressed_rejected():
    for bad in (math.inf, -math.inf, math.nan):
        stop, risk, target, rejection = compute_initial_protection("LONG", 100.0, atr_reexpressed=bad, k=2.0, r_multiple=None)
        assert rejection == ENTRY_INVALID_PROTECTIVE_LEVELS, bad
        assert stop is None and risk is None and target is None


def test_non_finite_k_rejected():
    stop, risk, target, rejection = compute_initial_protection("LONG", 100.0, atr_reexpressed=5.0, k=math.inf, r_multiple=None)
    assert rejection == ENTRY_INVALID_PROTECTIVE_LEVELS


def test_non_finite_target_from_infinite_r_multiple_rejected():
    stop, risk, target, rejection = compute_initial_protection("LONG", 100.0, atr_reexpressed=5.0, k=2.0, r_multiple=math.inf)
    assert rejection == ENTRY_INVALID_PROTECTIVE_LEVELS
