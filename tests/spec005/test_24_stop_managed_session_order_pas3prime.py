"""TEST 24 -- Pas 3' intrabar stop/target resolution (docs/spec005_exit_
amendment_v1.0.md, ACCEPTED, section 5), including the explicit
non-ambiguous "target at open, then stop intraday on the remainder, same
session" case (section 13 regression #6) and the genuine same-bar
ambiguity branch (stop-first, counted as AMBIGUOUS_INTRABAR_CONFLICT)."""
from backtest.exits.entities import EXIT_REASON_STOP, EXIT_REASON_TARGET, StopManagedPosition
from backtest.exits.session import advance_intrabar


def _long_partial_position(**overrides) -> StopManagedPosition:
    fields = dict(
        security_id="SEC_X", direction="LONG", entry_date="2024-01-11", signal_date="2024-01-10",
        entry_fill_price=100.0, k=2.0, r_multiple=2.0, fraction=0.5,
        active_stop=90.0, initial_risk=10.0, target_price=120.0,
    )
    fields.update(overrides)
    return StopManagedPosition(**fields)


def test_stop_hit_at_open_closes_the_whole_position():
    pos = _long_partial_position()
    new_pos, executed = advance_intrabar(pos, "2024-01-12", open_price=85.0, high=86.0, low=84.0)
    assert new_pos.closed is True
    assert new_pos.remaining_quantity == 0.0
    assert len(executed) == 1
    assert executed[0].exit_reason == EXIT_REASON_STOP
    assert executed[0].exit_fill_price == 85.0  # fill = open(t), not the stop level
    assert executed[0].fraction_of_original == 1.0  # target never consumed


def test_only_stop_hit_intraday_fills_at_exact_stop_level():
    pos = _long_partial_position()
    new_pos, executed = advance_intrabar(pos, "2024-01-12", open_price=100.0, high=115.0, low=85.0)
    assert new_pos.closed is True
    assert len(executed) == 1
    assert executed[0].exit_reason == EXIT_REASON_STOP
    assert executed[0].exit_fill_price == 90.0  # exact stop level, not the day's low
    assert executed[0].fraction_of_original == 1.0
    assert new_pos.ambiguous_intrabar_conflicts == 0


def test_only_target_hit_intraday_fills_at_exact_target_level_position_stays_open():
    pos = _long_partial_position()
    new_pos, executed = advance_intrabar(pos, "2024-01-12", open_price=100.0, high=125.0, low=95.0)
    assert new_pos.closed is False
    assert new_pos.target_consumed is True
    assert len(executed) == 1
    assert executed[0].exit_reason == EXIT_REASON_TARGET
    assert executed[0].exit_fill_price == 120.0  # exact target level, not the day's high
    assert executed[0].fraction_of_original == 0.5
    assert new_pos.remaining_quantity == 0.5


def test_target_at_open_then_stop_intraday_same_session_is_not_ambiguous():
    """Section 13 regression #6: the explicit non-ambiguous case."""
    pos = _long_partial_position()
    new_pos, executed = advance_intrabar(pos, "2024-01-12", open_price=125.0, high=130.0, low=85.0)
    assert len(executed) == 2
    partial, remainder = executed
    assert partial.exit_reason == EXIT_REASON_TARGET and partial.exit_fill_price == 125.0 and partial.fraction_of_original == 0.5
    assert remainder.exit_reason == EXIT_REASON_STOP and remainder.exit_fill_price == 90.0 and remainder.fraction_of_original == 0.5
    assert new_pos.closed is True
    assert new_pos.remaining_quantity == 0.0
    assert new_pos.ambiguous_intrabar_conflicts == 0  # NOT counted as ambiguous


def test_genuine_same_bar_conflict_is_stop_first_and_counted():
    """Both thresholds hit intraday, neither resolved by the open's own
    position -- real ambiguity, stop-first, counted."""
    pos = _long_partial_position()
    new_pos, executed = advance_intrabar(pos, "2024-01-12", open_price=100.0, high=125.0, low=85.0)
    assert len(executed) == 1
    assert executed[0].exit_reason == EXIT_REASON_STOP
    assert executed[0].exit_fill_price == 90.0
    assert executed[0].fraction_of_original == 1.0  # target was never actually consumed
    assert new_pos.closed is True
    assert new_pos.ambiguous_intrabar_conflicts == 1


def test_control_variant_has_no_target_only_stop_applies():
    pos = _long_partial_position(fraction=None, target_price=None, r_multiple=None)
    new_pos, executed = advance_intrabar(pos, "2024-01-12", open_price=100.0, high=125.0, low=85.0)
    assert len(executed) == 1
    assert executed[0].exit_reason == EXIT_REASON_STOP
    assert executed[0].fraction_of_original == 1.0
    assert new_pos.closed is True


def test_short_direction_mirrors_long():
    pos = StopManagedPosition(
        security_id="SEC_X", direction="SHORT", entry_date="2024-01-11", signal_date="2024-01-10",
        entry_fill_price=100.0, k=2.0, r_multiple=2.0, fraction=0.5,
        active_stop=110.0, initial_risk=10.0, target_price=80.0,
    )
    # SHORT: stop breached by price rising above 110; target by price falling to/below 80.
    new_pos, executed = advance_intrabar(pos, "2024-01-12", open_price=100.0, high=112.0, low=95.0)
    assert len(executed) == 1
    assert executed[0].exit_reason == EXIT_REASON_STOP
    assert executed[0].exit_fill_price == 110.0
    assert new_pos.closed is True


def test_a_closed_position_is_left_untouched():
    pos = _long_partial_position(closed=True, remaining_quantity=0.0)
    new_pos, executed = advance_intrabar(pos, "2024-01-12", open_price=1.0, high=1.0, low=1.0)
    assert new_pos == pos
    assert executed == ()
