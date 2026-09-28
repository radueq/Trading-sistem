"""Spec #005 -- Session Engine & Integration: the multi-security session
loop for STOP_MANAGED_INVALIDATION (docs/spec005_exit_amendment_v1.0.md,
ACCEPTED, section 5), composing the already-built per-position step
functions in `backtest.exits.protection`/`backtest.exits.session` into the
full Pas 0 / 1 / 2 / 3' / 5 / 6 order across a universe of securities and a
stage's own session calendar.

**Scope boundary, stated explicitly (mirrors the discipline the whole of
Batch 1-3 already follows):** turning Discovery lane STATES into an actual
entry-signal match against an `EntryDefinition`, and evaluating an
`InvalidationCondition` against those same lane states to produce
VALID_HOLD/INVALIDATED/UNKNOWN, are BOTH separate integration surfaces
that do not exist anywhere in this codebase (confirmed: no function
anywhere evaluates an `InvalidationCondition` against Discovery output;
Batch 1/2's own known-limitations already establish that no entry-signal
matching exists for any exit family). Building either now would be a
second, much larger deliverable than "the session loop" -- this engine
therefore takes both as EXPLICIT, TYPED INPUTS (`entry_signals`,
`invalidation_observer`), the same kind of interface boundary Batch 1/2
drew around PIT access itself. What this module DOES implement, fully and
testably, is the thing that was actually missing: the SESSION ORDER
(section 5) and per-security bookkeeping (open positions, pending
invalidations, entry dispositions, stage-end classification) around
those already-accepted per-position mechanics.

`run_stage()` is the one OBLIGATORY entry point (Spec #005 Exit Amendment
review, "Session Engine & Integration" round, obligation #2): it calls
`backtest.exits.plan_integration.accept_research_plan()` FIRST and refuses
to run the engine at all if the plan is rejected -- unlike the previous
round, where that gate existed but was reachable only from tests.
`SessionEngine` itself stays callable directly (mirrors every other
Batch 3 module -- `session.py`'s own step functions are unit-tested in
isolation too), for tests that want to exercise the loop without also
constructing a full `ResearchPlan`/`HypothesisRegistry`.
"""
from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from typing import Callable, Mapping, Optional, Sequence

from hypothesis.registry.hypotheses import HypothesisRegistry

from backtest.data.pit_access import BoundedPITAccess
from backtest.exits.costs import (
    aggregate_position_return,
    compute_w,
    net_return_for_tranche_with_slippage,
    open_remainder_net_return,
    slippage_rate_from_bps,
)
from backtest.exits.entities import (
    ENTRY_NO_ENTRY_BAR,
    ENTRY_NO_VALID_STOP_BASIS,
    ENTRY_INVALID_PROTECTIVE_LEVELS,
    ENTRY_SUPPRESSED_STAGE_BOUNDARY,
    EVALUABILITY_EVALUABLE,
    PositionOutcome,
    StopManagedExecutionSemanticsProfile,
    StopManagedPosition,
)
from backtest.exits.plan_integration import accept_research_plan
from backtest.exits.protection import _find_bar, compute_atr_from_bars, open_stop_managed_position
from backtest.exits.session import (
    advance_intrabar,
    check_trend_invalidation,
    execute_scheduled_invalidation,
    reconcile_split_for_open_position,
    update_trailing_stop_at_close,
)
from backtest.models.entities import CostAssumptions, ResearchPlan

ENTRY_EXECUTED = "EXECUTED"

# The default volatility config `protection.py` itself falls back to when
# a caller passes none -- reused here so the engine's own default matches
# every per-position function's default, never a silently different one.
_DEFAULT_VOLATILITY_CONFIG = {
    "atr_window": 14, "bb_window": 20, "bb_num_std": 2.0, "realized_vol_window": 20,
}


@dataclasses.dataclass(frozen=True)
class EntrySignal:
    """A caller-decided candidate entry, keyed externally by
    `(security_id, signal_date)` -- `signal_date` is the session whose
    CLOSE produced this signal (section 3's `s`); the engine executes it
    at the NEXT session's open (section 5, Pas 2), never on `signal_date`
    itself. How this signal was decided (Discovery candidate matching
    against an `EntryDefinition`) is outside this engine's scope -- see
    the module docstring."""
    security_id: str
    direction: str  # "LONG" | "SHORT"
    k: float
    r_multiple: Optional[float] = None
    fraction: Optional[float] = None


@dataclasses.dataclass(frozen=True)
class EntryDisposition:
    """One recorded outcome for one candidate entry -- amendment section 2:
    "Fiecare dispoziție e înregistrată explicit... nu se șterge evidența
    intrării neexecutate." `disposition` is `ENTRY_EXECUTED` or one of the
    four `ENTRY_*` rejection constants, checked in the amendment's own
    order."""
    security_id: str
    signal_date: str
    entry_date: str
    disposition: str


InvalidationObserver = Callable[[StopManagedPosition, str], str]
SameDayEvidenceProvider = Callable[[str, str], frozenset]


def _default_same_day_evidence(_security_id: str, _session_date: str) -> frozenset:
    return frozenset()


@dataclasses.dataclass(frozen=True)
class SessionEngineResult:
    """Every position this run ever opened, in its FINAL state (closed,
    still active/censored, or exit_failed), plus every entry disposition
    (executed or rejected) recorded along the way. Classification/return
    computation is a SEPARATE step (`evaluate_stage_results()` below) --
    this result carries raw simulation state only, mirroring
    `taxonomy.classify_position()`'s own separation from the mechanics
    that produce a `StopManagedPosition`."""
    positions: tuple[StopManagedPosition, ...]
    entry_dispositions: tuple[EntryDisposition, ...]
    final_closes: Mapping[str, Optional[float]]  # security_id -> last observed close in the stage


class SessionEngine:
    """Amendment section 5's Pas 0/1/2/3'/5/6 order, over `session_dates`
    (the stage's OWN sessions, sorted, no warm-up) and a universe of
    securities. At most one open STOP_MANAGED_INVALIDATION position per
    security_id at a time -- an `entry_signals` entry for a security_id
    that already has an open position is never evaluated as a candidate
    at all (not one of the four rejection reasons, which describe
    something else entirely; constructing overlapping signals for one
    security is a caller error to avoid, not a case the amendment
    disposes of)."""

    def __init__(
        self,
        pit: BoundedPITAccess,
        session_dates: Sequence[str],
        entry_signals: Mapping[tuple[str, str], EntrySignal],
        invalidation_observer: InvalidationObserver,
        same_day_split_evidence: SameDayEvidenceProvider = _default_same_day_evidence,
        volatility_config: Optional[dict] = None,
        stage_end_date: Optional[str] = None,
    ):
        if not session_dates:
            raise ValueError("session_dates must be non-empty -- there is no session order to run")
        self.pit = pit
        self.session_dates = tuple(session_dates)
        self.entry_signals = entry_signals
        self.invalidation_observer = invalidation_observer
        self.same_day_split_evidence = same_day_split_evidence
        self.volatility_config = volatility_config or _DEFAULT_VOLATILITY_CONFIG
        # Defaults to the last session actually run -- a caller may
        # override only to test a stage boundary narrower than the full
        # session_dates list it supplies.
        self.stage_end_date = stage_end_date or self.session_dates[-1]

        self._open_positions: dict[str, StopManagedPosition] = {}
        self._all_positions: list[StopManagedPosition] = []
        self._dispositions: list[EntryDisposition] = []
        self._last_close: dict[str, Optional[float]] = {}

    def run(self) -> SessionEngineResult:
        for i, today in enumerate(self.session_dates):
            bars_today: dict[str, list] = {}

            def bars_for(security_id: str) -> list:
                if security_id not in bars_today:
                    bars_today[security_id] = self.pit.get_price_series_as_of(security_id, today)
                return bars_today[security_id]

            # Pas 0: reconcile splits for positions opened in a STRICTLY
            # PRIOR session -- never one opened today (section 5: a
            # position opened today starts DIRECTLY on the entry basis).
            for security_id, pos in list(self._open_positions.items()):
                if pos.entry_date < today:
                    evidence = self.same_day_split_evidence(security_id, today)
                    self._open_positions[security_id] = reconcile_split_for_open_position(self.pit, pos, today, evidence)

            # Pas 1: execute any exit scheduled at THIS session's open --
            # a pending invalidation detected at a PRIOR session's close.
            for security_id, pos in list(self._open_positions.items()):
                if pos.pending_invalidation_detected_date is None:
                    continue
                bar = _find_bar(bars_for(security_id), today)
                open_price = bar.split_adjusted_open if bar is not None else None
                new_pos = execute_scheduled_invalidation(pos, today, open_price, self.stage_end_date)
                self._open_positions[security_id] = new_pos
                if new_pos.closed or new_pos.exit_failed:
                    self._retire(security_id, new_pos)

            # Pas 2: execute pending entries -- signals recorded at the
            # PREVIOUS session's close (section 3's `s`), entering at
            # THIS session's open (section 5). The first session in the
            # loop has no prior in-stage session to have produced one.
            if i > 0:
                signal_date = self.session_dates[i - 1]
                for (security_id, sig_date), signal in self.entry_signals.items():
                    if sig_date != signal_date:
                        continue
                    if security_id in self._open_positions:
                        continue  # already open -- not a candidate at all, see class docstring.
                    self._execute_pending_entry(security_id, signal, signal_date, today, bars_for)

            # Pas 3': intrabar resolution for every position active today,
            # including one opened at Pas 2 above.
            for security_id, pos in list(self._open_positions.items()):
                bar = _find_bar(bars_for(security_id), today)
                if bar is None or bar.split_adjusted_open is None or bar.split_adjusted_high is None or bar.split_adjusted_low is None:
                    continue  # no usable bar this session -- position carries over unchanged (see module docstring).
                new_pos, _tranches = advance_intrabar(pos, today, bar.split_adjusted_open, bar.split_adjusted_high, bar.split_adjusted_low)
                self._open_positions[security_id] = new_pos
                if new_pos.closed:
                    self._retire(security_id, new_pos)

            # Pas 5 (trend invalidation at close) + close(t)'s S_next
            # recompute -- both operate on whatever is STILL active after
            # Pas 3'; a position closed above never reaches either.
            for security_id, pos in list(self._open_positions.items()):
                bar = _find_bar(bars_for(security_id), today)
                close_price = bar.split_adjusted_close if bar is not None else None
                if close_price is not None:
                    self._last_close[security_id] = close_price

                observation_status = self.invalidation_observer(pos, today)
                pos = check_trend_invalidation(pos, today, observation_status)

                if not pos.closed and pos.remaining_quantity > 0 and bar is not None:
                    # Matches `compute_atr_basis_reconciliation()`'s own
                    # convention exactly: the FULL history up to and
                    # including today, never clipped to the last
                    # `atr_window` bars -- Wilder's recursive smoothing is
                    # not equivalent to re-seeding from a truncated window.
                    window = [b for b in bars_for(security_id) if b.date <= today]
                    atr_today = compute_atr_from_bars(window, self.volatility_config) if len(window) >= self.volatility_config["atr_window"] else None
                    pos = update_trailing_stop_at_close(pos, close_price, atr_today)

                self._open_positions[security_id] = pos

            # Pas 6 ("intrări noi pentru t+1"): nothing to do here by
            # construction -- a signal recorded at THIS session's close
            # (signal_date == today) is simply looked up again as Pas 2's
            # `signal_date` on the NEXT iteration.

        # Stage boundary reached: the last session's own signals, if any,
        # would enter beyond the authorized stage -- SUPPRESSED_STAGE_
        # BOUNDARY, no price ever read for them (section 2, item 1).
        last_signal_date = self.session_dates[-1]
        for (security_id, sig_date), _signal in self.entry_signals.items():
            if sig_date == last_signal_date:
                self._dispositions.append(EntryDisposition(
                    security_id=security_id, signal_date=sig_date, entry_date="<beyond authorized stage>",
                    disposition=ENTRY_SUPPRESSED_STAGE_BOUNDARY,
                ))

        # Any position still carrying a pending invalidation at the very
        # end of the loop was detected at the stage's OWN last close --
        # its scheduled fill falls in the next stage (section 10's central
        # CENSORED_AT_HORIZON case, regression #9). `execute_scheduled_
        # invalidation()`'s own `next_session_date > stage_end_date`
        # branch records the note; the synthetic date below is never read
        # for pricing (that branch returns before ever looking at price)
        # -- it exists only to satisfy that comparison and the note text.
        synthetic_next_stage_date = (date.fromisoformat(self.stage_end_date) + timedelta(days=1)).isoformat()
        for security_id, pos in list(self._open_positions.items()):
            if pos.pending_invalidation_detected_date is not None:
                self._open_positions[security_id] = execute_scheduled_invalidation(
                    pos, synthetic_next_stage_date, None, self.stage_end_date,
                )

        for security_id, pos in self._open_positions.items():
            self._all_positions.append(pos)
            self._last_close.setdefault(security_id, None)

        return SessionEngineResult(
            positions=tuple(self._all_positions),
            entry_dispositions=tuple(self._dispositions),
            final_closes=dict(self._last_close),
        )

    def _retire(self, security_id: str, position: StopManagedPosition) -> None:
        self._all_positions.append(position)
        del self._open_positions[security_id]

    def _execute_pending_entry(self, security_id: str, signal: EntrySignal, signal_date: str, entry_date: str, bars_for) -> None:
        bar = _find_bar(bars_for(security_id), entry_date)
        entry_fill_price = bar.split_adjusted_open if bar is not None else None
        evidence = self.same_day_split_evidence(security_id, entry_date)
        position, rejection = open_stop_managed_position(
            self.pit, security_id, signal.direction, signal_date, entry_date, entry_fill_price,
            signal.k, signal.r_multiple, signal.fraction, evidence, self.volatility_config,
        )
        if rejection is not None:
            assert rejection in (ENTRY_NO_ENTRY_BAR, ENTRY_NO_VALID_STOP_BASIS, ENTRY_INVALID_PROTECTIVE_LEVELS)
            self._dispositions.append(EntryDisposition(security_id, signal_date, entry_date, rejection))
            return
        self._open_positions[security_id] = position
        self._dispositions.append(EntryDisposition(security_id, signal_date, entry_date, ENTRY_EXECUTED))


def evaluate_stage_results(
    positions: Sequence[StopManagedPosition], outcomes: Sequence[PositionOutcome],
    cost_assumptions: CostAssumptions, stage_end_date: str, final_closes: Mapping[str, Optional[float]],
) -> tuple[Optional[float], ...]:
    """Amendment section 9's aggregation, run per position: `None` when
    `outcomes[i].evaluability != EVALUABLE` (never a number for an
    UNEVALUABLE or EXIT_FAILED position -- section 10's explicit rule).
    `positions`/`outcomes` must be the SAME length, index-aligned (as
    `taxonomy.classify_position()` naturally produces when called once
    per position in `positions`)."""
    if len(positions) != len(outcomes):
        raise ValueError(f"positions and outcomes must be index-aligned and the same length, got {len(positions)} and {len(outcomes)}")
    slippage_exit_rate = slippage_rate_from_bps(cost_assumptions.slippage_exit_bps)
    results: list[Optional[float]] = []
    for position, outcome in zip(positions, outcomes):
        if outcome.evaluability != EVALUABILITY_EVALUABLE:
            results.append(None)
            continue
        w = compute_w(position)
        partial_return = None
        if w != 0.0:
            partial_return = net_return_for_tranche_with_slippage(
                position.partial_tranche, position.direction,
                cost_assumptions.commission_entry_rate, cost_assumptions.commission_exit_rate,
                cost_assumptions.borrow_annual_rate, slippage_exit_rate,
            )
        if position.closed:
            rest_return = net_return_for_tranche_with_slippage(
                position.close_tranche, position.direction,
                cost_assumptions.commission_entry_rate, cost_assumptions.commission_exit_rate,
                cost_assumptions.borrow_annual_rate, slippage_exit_rate,
            )
        else:
            mark_final = final_closes.get(position.security_id)
            holding_days = (date.fromisoformat(stage_end_date) - date.fromisoformat(position.entry_date)).days
            rest_return = open_remainder_net_return(
                position.direction, position.entry_fill_price, mark_final,
                cost_assumptions.commission_entry_rate, cost_assumptions.borrow_annual_rate, holding_days,
            )
        results.append(aggregate_position_return(w, partial_return, rest_return))
    return tuple(results)


class PlanNotAcceptedError(ValueError):
    """Raised by `run_stage()` when `accept_research_plan()` rejects the
    supplied plan -- the engine never runs a single session for a plan
    that fails the obligatory acceptance gate."""
    pass


def run_stage(
    plan: ResearchPlan, registry: HypothesisRegistry, pit: BoundedPITAccess, session_dates: Sequence[str],
    entry_signals: Mapping[tuple[str, str], EntrySignal], invalidation_observer: InvalidationObserver,
    stop_managed_profile: Optional[StopManagedExecutionSemanticsProfile] = None,
    same_day_split_evidence: SameDayEvidenceProvider = _default_same_day_evidence,
    volatility_config: Optional[dict] = None, stage_end_date: Optional[str] = None,
) -> SessionEngineResult:
    """THE obligatory entry point for running a stage: calls
    `accept_research_plan()` first and raises `PlanNotAcceptedError`
    without ever constructing a `SessionEngine` if the plan is rejected --
    unlike the previous round's gate, which existed but was reachable only
    from tests. `SessionEngine` itself remains directly callable for tests
    that want to exercise the session loop in isolation, the same way
    `session.py`'s own step functions are unit-tested individually."""
    accepted, errors = accept_research_plan(plan, registry, stop_managed_profile)
    if not accepted:
        raise PlanNotAcceptedError(f"ResearchPlan {plan.research_plan_id!r} rejected by accept_research_plan(): {errors}")
    engine = SessionEngine(
        pit, session_dates, entry_signals, invalidation_observer, same_day_split_evidence, volatility_config, stage_end_date,
    )
    return engine.run()
