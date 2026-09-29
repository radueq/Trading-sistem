"""Spec #005 -- Discovery Integration & Legacy Exits: per-position mechanics
and the multi-security session loop for the TWO OLDER exit families,
TIME_EXIT and SIGNAL_INVALIDATION (Spec #004 SS24/SS110-B) -- the
obligation named explicitly in `docs/spec005_known_limitations.md`:
"`SessionEngine` only ever constructs/advances `StopManagedPosition`
objects... `SessionEngine` itself has nothing to run for that cohort's
old-family variants."

This is a SEPARATE engine (`LegacySessionEngine`), not an extension of
`backtest.exits.engine.SessionEngine` -- deliberately, so the
already-accepted STOP_MANAGED_INVALIDATION loop in `engine.py` is never
touched: `engine.run_stage()` constructs and runs BOTH engines against the
SAME `session_dates`/cohort and merges their results (see its own
docstring for exactly how signals are partitioned between them).

Both older families use a FIXED `exit_execution_policy=BAR_CLOSE` (Spec
#004 HYPOTHESIS_ENGINE_VERSION contract) -- unlike STOP_MANAGED_
INVALIDATION's own, separately-versioned execution-semantics profile
(amendment section 7), neither ever defers a decided exit to a LATER
session's open: the closing tranche always fills at the SAME session's
close that decided the exit. This makes the per-session mechanics here
structurally simpler than `protection.py`/`session.py`'s own: no
intrabar open/high/low check, no stop/target levels, no partial-profit
tranche, no "pending, scheduled for next open" position state at all.

TIME_EXIT (Spec #004 HORIZON_REFERENCE_POINT/`ExitHypothesis.
time_exit_bars`): "entry at the open of the entry bar: holding bar 1 =
entry bar itself; holding bar N = entry bar index + (N-1); exit at the
CLOSE of holding bar N." Pure bar-counting -- no invalidation vocabulary
applies to it at all (Spec #004's own proposal validator never populates
`invalidation_conditions` for this family).

SIGNAL_INVALIDATION (Spec #004 SS110-B): "EXIT on signal invalidation OR
mandatory max_holding_bars, whichever occurs first." Both triggers are
checked every session at close; if BOTH fire on the exact same session,
this module's own, explicitly stated tie-break (never given verbatim by
any spec text for this exact simultaneity) prefers the INVALIDATION
reason -- the same "the more specific, risk-side signal wins an exact
tie" convention `session.advance_intrabar()` already uses for a
same-bar stop-vs-target conflict (stop, the protective/risk-side event,
wins over target, the opportunistic one); `max_holding_bars` is a
backstop cap, not itself a signal about the position's own thesis.

Neither family needs Pas 1 (STOP_MANAGED_INVALIDATION's own "execute a
previously-scheduled exit" step) -- BAR_CLOSE execution means there is
never anything scheduled to execute later. Pas 0 (split reconciliation)
still applies: see `reconcile_split_for_legacy_position()`'s own docstring
for why a LegacyPosition has exactly the same entry-price staleness
problem `StopManagedPosition` does.
"""
from __future__ import annotations

import dataclasses
from datetime import date
from typing import Callable, Mapping, Optional, Sequence

from data_foundation.model.adjustment_engine import compute_factors
from data_foundation.model.entities import ActionType, CorporateAction
from data_foundation.pit.access import _is_action_known_for_adjustment

from hypothesis.models.entities import ExitFamily
from hypothesis.registry.hypotheses import HypothesisRegistry

from backtest.data.pit_access import BoundedPITAccess
from backtest.exits.costs import apply_entry_slippage, net_return_for_tranche_with_slippage, open_remainder_net_return, slippage_rate_from_bps
from backtest.exits.engine import ENTRY_EXECUTED, EntryDisposition, EntrySignal
from backtest.exits.entities import (
    ENTRY_NO_ENTRY_BAR,
    ENTRY_SUPPRESSED_STAGE_BOUNDARY,
    ENTRY_UNSUPPORTED_EXIT_FAMILY,
    ENTRY_VARIANT_NOT_FOUND,
    ENTRY_VARIANT_NOT_IN_ACCEPTED_COHORT,
    EVALUABILITY_EVALUABLE,
    EVALUABILITY_UNEVALUABLE,
    EXIT_REASON_MAX_HOLDING_BARS_FORCED_EXIT,
    EXIT_REASON_SIGNAL_INVALIDATION,
    EXIT_REASON_TIME_EXIT,
    LIFECYCLE_CENSORED_AT_HORIZON,
    LIFECYCLE_CLOSED,
    LIFECYCLE_EXIT_FAILED,
    REASON_CENSORED_MARK_UNAVAILABLE,
    REASON_INVALIDATION_PATH_INCOMPLETE,
    REASON_NO_EXIT_BAR,
    REASON_SPLIT_RECONCILIATION_INCOMPLETE,
    LegacyPosition,
    PositionOutcome,
    Tranche,
)
from backtest.exits.protection import _find_bar, is_authorized_at_open, knowledge_date
from backtest.models.entities import CostAssumptions

PositionKey = tuple[str, str]  # (security_id, strategy_variant_id)

LegacyInvalidationObserver = Callable[[LegacyPosition, str], str]
SameDayEvidenceProvider = Callable[[str, str], frozenset]

_LEGACY_FAMILIES = (ExitFamily.TIME_EXIT.value, ExitFamily.SIGNAL_INVALIDATION.value)


def _default_same_day_evidence(_security_id: str, _session_date: str) -> frozenset:
    return frozenset()


def _calendar_days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def reconcile_split_for_legacy_position(
    pit: BoundedPITAccess, position: LegacyPosition, session_date: str,
    same_day_evidence: frozenset = frozenset(),
) -> LegacyPosition:
    """Pas-0 equivalent for TIME_EXIT/SIGNAL_INVALIDATION positions --
    independently implemented, never a refactor of the already-accepted
    `session.reconcile_split_for_open_position()` (which is
    StopManagedPosition-specific and stays byte-for-byte untouched here).
    A `LegacyPosition.entry_fill_price` has exactly the same staleness
    problem `StopManagedPosition.entry_fill_price` does (amendment section
    6's underlying principle, not specific to that one family): a LATER
    `get_price_series_as_of()` query, run as of a date after an
    intervening SPLIT/REVERSE_SPLIT, re-expresses the SAME entry-date bar
    on a DIFFERENT historical basis than the query that originally
    produced `entry_fill_price` did -- comparing that frozen, pre-split
    value against a later close computed under the new basis would be
    wrong by exactly the split ratio. There is no active_stop/target_
    price/initial_risk/remaining_quantity here to rescale (a
    LegacyPosition never has them, and never holds a partial-profit
    tranche) -- only `entry_fill_price` itself."""
    if position.closed or position.exit_failed:
        return position

    actions = pit.get_corporate_actions_as_of(position.security_id, session_date)
    pos = position
    became_incomplete = False
    known_split_actions: list[CorporateAction] = []
    newly_authorized: list[CorporateAction] = []

    for pca in actions:
        a = pca.action
        if a.action_type not in (ActionType.SPLIT.value, ActionType.REVERSE_SPLIT.value):
            continue
        if a.effective_date <= pos.entry_date:
            continue  # already fully reflected in the position's own opening basis.
        if not _is_action_known_for_adjustment(a, session_date):
            continue
        known_split_actions.append(a)
        if a.action_id in pos.processed_split_action_ids:
            continue
        if not is_authorized_at_open(knowledge_date(a), session_date, a.action_id in same_day_evidence):
            became_incomplete = True
            continue
        newly_authorized.append(a)

    if not newly_authorized:
        if became_incomplete:
            pos = dataclasses.replace(pos, split_reconciliation_incomplete=True)
        return pos

    already_processed = {a.action_id for a in known_split_actions if a.action_id in pos.processed_split_action_ids}
    authorized_actions = [a for a in known_split_actions if a.action_id in already_processed] + newly_authorized

    bars = pit.get_price_series_as_of(pos.security_id, session_date)
    entry_bar = _find_bar(bars, pos.entry_date)
    if entry_bar is None or not entry_bar.raw_close:
        return dataclasses.replace(pos, split_reconciliation_incomplete=True)

    factors = compute_factors([pos.entry_date], {pos.entry_date: entry_bar.raw_close}, authorized_actions, [])
    current_factor, _total_return_factor = factors[pos.entry_date]

    newly_authorized_ids = tuple(a.action_id for a in newly_authorized)
    late = any(a.effective_date < session_date for a in newly_authorized)

    if current_factor != pos.applied_factor:
        ratio = current_factor / pos.applied_factor
        pos = dataclasses.replace(
            pos, entry_fill_price=pos.entry_fill_price * ratio,
            applied_factor=current_factor, processed_split_action_ids=pos.processed_split_action_ids + newly_authorized_ids,
        )
    else:
        pos = dataclasses.replace(pos, processed_split_action_ids=pos.processed_split_action_ids + newly_authorized_ids)

    if became_incomplete or late:
        pos = dataclasses.replace(pos, split_reconciliation_incomplete=True)
    return pos


def advance_legacy_position_at_close(
    position: LegacyPosition, session_date: str, session_index: int,
    close_price: Optional[float], invalidation_status: Optional[str],
) -> LegacyPosition:
    """One per-session step at close(t) -- see module docstring for why
    BAR_CLOSE execution needs no separate intrabar/scheduled-fill step at
    all. `invalidation_status` is `None` for TIME_EXIT (no invalidation
    vocabulary applies); for SIGNAL_INVALIDATION it is one of
    VALID_HOLD/INVALIDATED/UNKNOWN, the exact same contract
    `session.check_trend_invalidation()` already uses. `UNKNOWN` taints
    `invalidation_path_incomplete` PERMANENTLY, mirroring that same
    persistent-incompleteness rule (section 5/10 of the amendment) for the
    identical underlying reason: the holding condition's own forward path
    is not fully demonstrated, whatever the root cause."""
    if position.closed or position.exit_failed:
        return position

    holding_bar_number = session_index - position.entry_session_index + 1
    pos = position
    invalidated_now = False

    if pos.exit_family == ExitFamily.SIGNAL_INVALIDATION.value:
        if invalidation_status == "UNKNOWN":
            pos = dataclasses.replace(pos, invalidation_path_incomplete=True)
        invalidated_now = invalidation_status == "INVALIDATED"

    time_cap_reached = (
        (pos.time_exit_bars is not None and holding_bar_number >= pos.time_exit_bars)
        or (pos.max_holding_bars is not None and holding_bar_number >= pos.max_holding_bars)
    )

    if not (invalidated_now or time_cap_reached):
        return pos

    if close_price is None:
        return dataclasses.replace(pos, exit_failed=True, exit_failed_reason=REASON_NO_EXIT_BAR)

    reason = (
        EXIT_REASON_SIGNAL_INVALIDATION if invalidated_now
        else (EXIT_REASON_TIME_EXIT if pos.exit_family == ExitFamily.TIME_EXIT.value else EXIT_REASON_MAX_HOLDING_BARS_FORCED_EXIT)
    )
    holding_days = _calendar_days(pos.entry_date, session_date)
    tranche = Tranche(
        kind="REMAINDER", exit_reason=reason, fraction_of_original=1.0,
        exit_date=session_date, exit_fill_price=close_price, holding_days=holding_days,
        entry_fill_price_reference=pos.entry_fill_price,
    )
    return dataclasses.replace(pos, closed=True, close_tranche=tranche)


def classify_legacy_position(
    position: LegacyPosition, stage_end_reached: bool, final_mark_available: bool = True,
) -> PositionOutcome:
    """The same three-facet taxonomy `taxonomy.classify_position()`
    implements for `StopManagedPosition` -- an independent, narrower
    reimplementation (never a refactor of that already-accepted function)
    since `LegacyPosition` has no `trailing_path_incomplete` concept at
    all (no ATR/trailing stop for either older family). Priority when both
    `split_reconciliation_incomplete` and `invalidation_path_incomplete`
    are set mirrors `taxonomy._persistent_incompleteness_reason()`'s own
    order (split first) -- both make the position UNEVALUABLE either way;
    the order only decides which single reason is reported."""
    if position.exit_failed:
        return PositionOutcome(LIFECYCLE_EXIT_FAILED, EVALUABILITY_UNEVALUABLE, REASON_NO_EXIT_BAR)

    if position.closed:
        if position.split_reconciliation_incomplete:
            return PositionOutcome(LIFECYCLE_CLOSED, EVALUABILITY_UNEVALUABLE, REASON_SPLIT_RECONCILIATION_INCOMPLETE)
        if position.invalidation_path_incomplete:
            return PositionOutcome(LIFECYCLE_CLOSED, EVALUABILITY_UNEVALUABLE, REASON_INVALIDATION_PATH_INCOMPLETE)
        return PositionOutcome(LIFECYCLE_CLOSED, EVALUABILITY_EVALUABLE, None)

    if not stage_end_reached:
        raise ValueError(
            "classify_legacy_position(): position is neither closed nor EXIT_FAILED, and "
            "stage_end_reached=False -- it is not yet classifiable (still actively simulating)"
        )

    if position.split_reconciliation_incomplete:
        return PositionOutcome(LIFECYCLE_CENSORED_AT_HORIZON, EVALUABILITY_UNEVALUABLE, REASON_SPLIT_RECONCILIATION_INCOMPLETE)
    if position.invalidation_path_incomplete:
        return PositionOutcome(LIFECYCLE_CENSORED_AT_HORIZON, EVALUABILITY_UNEVALUABLE, REASON_INVALIDATION_PATH_INCOMPLETE)
    if not final_mark_available:
        return PositionOutcome(LIFECYCLE_CENSORED_AT_HORIZON, EVALUABILITY_UNEVALUABLE, REASON_CENSORED_MARK_UNAVAILABLE)
    return PositionOutcome(LIFECYCLE_CENSORED_AT_HORIZON, EVALUABILITY_EVALUABLE, None)


def evaluate_legacy_stage_results(
    positions: Sequence[LegacyPosition], outcomes: Sequence[PositionOutcome],
    cost_assumptions: CostAssumptions, stage_end_date: str, final_closes: Mapping[str, Optional[float]],
) -> tuple[Optional[float], ...]:
    """The section-9 aggregation, narrowed to a `LegacyPosition`'s own
    shape: neither older family ever has a partial-profit tranche, so
    `w` is always 0 and `costs.compute_w()`/`aggregate_position_return()`
    (both `StopManagedPosition`-shaped) are not needed at all -- the
    position's own single tranche return (or the still-open remainder's
    return) IS the position's return."""
    if len(positions) != len(outcomes):
        raise ValueError(f"positions and outcomes must be index-aligned and the same length, got {len(positions)} and {len(outcomes)}")
    slippage_exit_rate = slippage_rate_from_bps(cost_assumptions.slippage_exit_bps)
    results: list[Optional[float]] = []
    for position, outcome in zip(positions, outcomes):
        if outcome.evaluability != EVALUABILITY_EVALUABLE:
            results.append(None)
            continue
        if position.closed:
            results.append(net_return_for_tranche_with_slippage(
                position.close_tranche, position.direction,
                cost_assumptions.commission_entry_rate, cost_assumptions.commission_exit_rate,
                cost_assumptions.borrow_annual_rate, slippage_exit_rate,
            ))
            continue
        mark_final = final_closes.get(position.security_id)
        if mark_final is None:
            raise ValueError(
                f"position {position.security_id!r} was classified {outcome.evaluability} but has no "
                f"final mark in final_closes -- outcomes must be derived from THIS SAME final_closes mapping"
            )
        holding_days = (date.fromisoformat(stage_end_date) - date.fromisoformat(position.entry_date)).days
        results.append(open_remainder_net_return(
            position.direction, position.entry_fill_price, mark_final,
            cost_assumptions.commission_entry_rate, cost_assumptions.borrow_annual_rate, holding_days,
        ))
    return tuple(results)


@dataclasses.dataclass(frozen=True)
class LegacyEngineResult:
    positions: tuple[LegacyPosition, ...]
    entry_dispositions: tuple[EntryDisposition, ...]
    final_closes: Mapping[str, Optional[float]]


class LegacySessionEngine:
    """The TIME_EXIT/SIGNAL_INVALIDATION counterpart of
    `backtest.exits.engine.SessionEngine` -- same `session_dates`/
    variant-keyed bookkeeping/`entry_signals` identity-validation
    discipline, independently implemented so `SessionEngine` itself is
    never touched. See module docstring for why there is no Pas 1 here."""

    def __init__(
        self,
        pit: BoundedPITAccess,
        session_dates: Sequence[str],
        registry: HypothesisRegistry,
        accepted_hypothesis_ids: frozenset,
        entry_signals: Mapping[tuple[str, str, str], EntrySignal],
        invalidation_observer: LegacyInvalidationObserver,
        cost_assumptions: CostAssumptions,
        same_day_split_evidence: SameDayEvidenceProvider = _default_same_day_evidence,
        stage_end_date: Optional[str] = None,
    ):
        if not session_dates:
            raise ValueError("session_dates must be non-empty -- there is no session order to run")
        self.pit = pit
        self.session_dates = tuple(session_dates)
        self.registry = registry
        self.accepted_hypothesis_ids = frozenset(accepted_hypothesis_ids)
        self.entry_signals = entry_signals
        for (key_security_id, key_variant_id, sig_date), signal in entry_signals.items():
            if signal.security_id != key_security_id or signal.strategy_variant_id != key_variant_id:
                raise ValueError(
                    f"entry_signals key {(key_security_id, key_variant_id, sig_date)!r} does not match "
                    f"its own EntrySignal's identity (security_id={signal.security_id!r}, "
                    f"strategy_variant_id={signal.strategy_variant_id!r}) -- mirrors SessionEngine's own "
                    f"identity-mismatch guard (Session Engine & Integration review, round-2 follow-up)"
                )
        self.invalidation_observer = invalidation_observer
        self.cost_assumptions = cost_assumptions
        self.same_day_split_evidence = same_day_split_evidence
        self.stage_end_date = stage_end_date or self.session_dates[-1]

        for i in range(len(self.session_dates) - 1):
            if self.session_dates[i] >= self.session_dates[i + 1]:
                raise ValueError(
                    f"session_dates must be strictly increasing with no duplicates -- found "
                    f"{self.session_dates[i]!r} at or after {self.session_dates[i + 1]!r} (index {i})"
                )
        beyond_stage = [d for d in self.session_dates if d > self.stage_end_date]
        if beyond_stage:
            raise ValueError(
                f"session_dates contains {len(beyond_stage)} date(s) beyond stage_end_date="
                f"{self.stage_end_date!r} (e.g. {beyond_stage[0]!r})"
            )
        pit_boundary = getattr(pit, "boundary", None)
        pit_max_as_of = getattr(pit_boundary, "max_as_of", None)
        if pit_max_as_of is not None and self.stage_end_date > pit_max_as_of:
            raise ValueError(
                f"stage_end_date={self.stage_end_date!r} exceeds this pit's own authorized boundary "
                f"max_as_of={pit_max_as_of!r}"
            )

        self._open_positions: dict[PositionKey, LegacyPosition] = {}
        self._all_positions: list[LegacyPosition] = []
        self._dispositions: list[EntryDisposition] = []
        self._last_close_observation: dict[str, tuple[float, str]] = {}

    def run(self) -> LegacyEngineResult:
        for i, today in enumerate(self.session_dates):
            bars_today: dict[str, list] = {}

            def bars_for(security_id: str) -> list:
                if security_id not in bars_today:
                    bars_today[security_id] = self.pit.get_price_series_as_of(security_id, today)
                return bars_today[security_id]

            # Pas 0: split reconciliation, positions opened strictly before
            # today only -- mirrors SessionEngine's own Pas 0 exactly.
            for key, pos in list(self._open_positions.items()):
                security_id, _variant_id = key
                if pos.entry_date < today:
                    evidence = self.same_day_split_evidence(security_id, today)
                    self._open_positions[key] = reconcile_split_for_legacy_position(self.pit, pos, today, evidence)

            # Pas 2: pending entries -- signals recorded at the PREVIOUS
            # session's close.
            if i > 0:
                signal_date = self.session_dates[i - 1]
                for (security_id, variant_id, sig_date), signal in self.entry_signals.items():
                    if sig_date != signal_date:
                        continue
                    if (security_id, variant_id) in self._open_positions:
                        continue
                    self._evaluate_pending_entry(security_id, signal, signal_date, today, i, bars_for)

            # Pas 3'/5 combined (BAR_CLOSE only -- see module docstring):
            # invalidation (SIGNAL_INVALIDATION only) + time cap, exit at
            # this SAME close if either triggers.
            for key, pos in list(self._open_positions.items()):
                security_id, _variant_id = key
                bar = _find_bar(bars_for(security_id), today)
                close_price = bar.split_adjusted_close if bar is not None else None
                if close_price is not None:
                    self._last_close_observation[security_id] = (close_price, today)

                invalidation_status = None
                if pos.exit_family == ExitFamily.SIGNAL_INVALIDATION.value:
                    invalidation_status = self.invalidation_observer(pos, today)

                new_pos = advance_legacy_position_at_close(pos, today, i, close_price, invalidation_status)
                self._open_positions[key] = new_pos
                if new_pos.closed or new_pos.exit_failed:
                    self._retire(key, new_pos)

        last_signal_date = self.session_dates[-1]
        for (security_id, variant_id, sig_date), _signal in self.entry_signals.items():
            if sig_date == last_signal_date:
                self._dispositions.append(EntryDisposition(
                    security_id=security_id, strategy_variant_id=variant_id, signal_date=sig_date,
                    entry_date="<beyond authorized stage>", disposition=ENTRY_SUPPRESSED_STAGE_BOUNDARY,
                ))

        final_closes: dict[str, Optional[float]] = {}
        for (security_id, _variant_id), pos in self._open_positions.items():
            self._all_positions.append(pos)
            observation = self._last_close_observation.get(security_id)
            final_closes[security_id] = observation[0] if observation is not None and observation[1] == last_signal_date else None

        return LegacyEngineResult(
            positions=tuple(self._all_positions),
            entry_dispositions=tuple(self._dispositions),
            final_closes=final_closes,
        )

    def _retire(self, key: PositionKey, position: LegacyPosition) -> None:
        self._all_positions.append(position)
        del self._open_positions[key]

    def _resolve_variant_parameters(self, signal: EntrySignal):
        """Returns (direction, exit_family, exit_hypothesis, rejection).
        Mirrors `SessionEngine._resolve_variant_parameters()`'s own
        VARIANT_NOT_FOUND/NOT_IN_ACCEPTED_COHORT ordering, with the family
        check narrowed to the two families THIS engine has mechanics for."""
        variant = self.registry.get_variant(signal.strategy_variant_id)
        if variant is None:
            return None, None, None, ENTRY_VARIANT_NOT_FOUND
        if variant.parent_hypothesis_id not in self.accepted_hypothesis_ids:
            return None, None, None, ENTRY_VARIANT_NOT_IN_ACCEPTED_COHORT
        if variant.exit_hypothesis.exit_family not in _LEGACY_FAMILIES:
            return None, None, None, ENTRY_UNSUPPORTED_EXIT_FAMILY
        parent = self.registry.get(variant.parent_hypothesis_id)
        if parent is None:
            return None, None, None, ENTRY_VARIANT_NOT_IN_ACCEPTED_COHORT
        return parent.direction, variant.exit_hypothesis.exit_family, variant.exit_hypothesis, None

    def _evaluate_pending_entry(
        self, security_id: str, signal: EntrySignal, signal_date: str, entry_date: str,
        entry_session_index: int, bars_for,
    ) -> None:
        direction, family, exit_hyp, rejection = self._resolve_variant_parameters(signal)
        if rejection is not None:
            self._dispositions.append(EntryDisposition(security_id, signal.strategy_variant_id, signal_date, entry_date, rejection))
            return

        bar = _find_bar(bars_for(security_id), entry_date)
        raw_open = bar.split_adjusted_open if bar is not None else None
        if raw_open is None:
            self._dispositions.append(EntryDisposition(security_id, signal.strategy_variant_id, signal_date, entry_date, ENTRY_NO_ENTRY_BAR))
            return

        slippage_entry_rate = slippage_rate_from_bps(self.cost_assumptions.slippage_entry_bps)
        entry_fill_price = apply_entry_slippage(direction, raw_open, slippage_entry_rate)

        position = LegacyPosition(
            security_id=security_id, strategy_variant_id=signal.strategy_variant_id, exit_family=family,
            direction=direction, signal_date=signal_date, entry_date=entry_date,
            entry_session_index=entry_session_index, entry_fill_price=entry_fill_price,
            time_exit_bars=exit_hyp.time_exit_bars if family == ExitFamily.TIME_EXIT.value else None,
            max_holding_bars=exit_hyp.max_holding_bars if family == ExitFamily.SIGNAL_INVALIDATION.value else None,
        )
        self._open_positions[(security_id, signal.strategy_variant_id)] = position
        self._dispositions.append(EntryDisposition(security_id, signal.strategy_variant_id, signal_date, entry_date, ENTRY_EXECUTED))
