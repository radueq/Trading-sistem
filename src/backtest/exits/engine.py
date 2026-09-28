"""Spec #005 -- Session Engine & Integration: the multi-security session
loop for STOP_MANAGED_INVALIDATION (docs/spec005_exit_amendment_v1.0.md,
ACCEPTED, section 5), composing the already-built per-position step
functions in `backtest.exits.protection`/`backtest.exits.session` into the
full Pas 0 / 1 / 2 / 3' / 5 / 6 order across a universe of securities and a
stage's own session calendar.

**Scope boundary, stated explicitly (mirrors the discipline the whole of
Batch 1-3 already follows, and confirmed acceptable as an explicit staging
point by the Session Engine & Integration review, round 1):** turning
Discovery lane STATES into an actual entry-signal match against an
`EntryDefinition`, and evaluating an `InvalidationCondition` against those
same lane states to produce VALID_HOLD/INVALIDATED/UNKNOWN, are BOTH
separate integration surfaces that do not exist anywhere in this codebase
(confirmed: no function anywhere evaluates an `InvalidationCondition`
against Discovery output). This engine therefore takes WHEN a candidate
entry exists, and what the trend-invalidation observation is, as EXPLICIT
INPUTS (`entry_signals`, `invalidation_observer`). It does NOT, however,
take the entry's own ECONOMIC PARAMETERS (direction, k, r_multiple,
fraction) as free-floating caller input -- those are ALWAYS derived from
the REAL `StrategyVariant` an `EntrySignal` names, resolved through the
SAME `HypothesisRegistry` `run_stage()`'s plan-acceptance gate already
used, and checked against that PLAN's own accepted cohort (round-1 review
finding #5): a signal naming a variant outside the accepted cohort, or
belonging to an exit family this engine has no mechanics for
(TIME_EXIT/SIGNAL_INVALIDATION), is rejected before any price is read --
never silently executed as if it were STOP_MANAGED_INVALIDATION.

`run_stage()` is the one OBLIGATORY entry point: it calls
`backtest.exits.plan_integration.accept_research_plan()` FIRST and refuses
to run the engine at all if the plan is rejected. `SessionEngine` itself
stays callable directly (mirrors every other Batch 3 module -- `session.py`'s
own step functions are unit-tested in isolation too), for tests that want
to exercise the loop against a hand-built registry/cohort without also
constructing a full `ResearchPlan`.
"""
from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from typing import Callable, Mapping, Optional, Sequence

from hypothesis.models.entities import ExitFamily
from hypothesis.registry.hypotheses import HypothesisRegistry

from backtest.data.pit_access import BoundedPITAccess
from backtest.exits.costs import (
    aggregate_position_return,
    apply_entry_slippage,
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
    ENTRY_UNSUPPORTED_EXIT_FAMILY,
    ENTRY_VARIANT_NOT_FOUND,
    ENTRY_VARIANT_NOT_IN_ACCEPTED_COHORT,
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
    mark_session_data_unavailable,
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
    itself. `strategy_variant_id` is the ONLY economic input this carries
    -- direction/k/r_multiple/fraction are ALWAYS derived from the real,
    registry-resolved `StrategyVariant` (round-1 review finding #5), never
    supplied here directly. How the CANDIDATE ITSELF was decided
    (Discovery matching against an `EntryDefinition`) is outside this
    engine's scope -- see the module docstring."""
    security_id: str
    strategy_variant_id: str


@dataclasses.dataclass(frozen=True)
class EntryDisposition:
    """One recorded outcome for one candidate entry -- amendment section 2:
    "Fiecare dispoziție e înregistrată explicit... nu se șterge evidența
    intrării neexecutate." `disposition` is `ENTRY_EXECUTED` or one of the
    rejection constants -- the four amendment section-2 reasons, or one of
    the three variant-resolution reasons checked before them (round-1
    review finding #5)."""
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
    that produce a `StopManagedPosition`.

    `final_closes[security_id]` is the security's own close on the LAST
    session this engine actually ran (`session_dates[-1]`) -- `None` if
    that specific session's own bar/close was unavailable, NEVER a stale
    close carried forward from an earlier session (round-1 review finding
    #3)."""
    positions: tuple[StopManagedPosition, ...]
    entry_dispositions: tuple[EntryDisposition, ...]
    final_closes: Mapping[str, Optional[float]]


class SessionEngine:
    """Amendment section 5's Pas 0/1/2/3'/5/6 order, over `session_dates`
    (the stage's OWN sessions, sorted, no warm-up) and a universe of
    securities. At most one open STOP_MANAGED_INVALIDATION position per
    security_id at a time -- an `entry_signals` entry for a security_id
    that already has an open position is never evaluated as a candidate
    at all (not one of the rejection reasons, which describe something
    else entirely; constructing overlapping signals for one security is a
    caller error to avoid, not a case the amendment disposes of).

    `registry`/`accepted_hypothesis_ids` tie every entry signal to a REAL
    `StrategyVariant` belonging to the PLAN'S OWN accepted cohort
    (round-1 review finding #5) -- `run_stage()` derives
    `accepted_hypothesis_ids` from `plan.hypothesis_cohort_ids` after
    `accept_research_plan()` accepts it; a caller using `SessionEngine`
    directly (no plan at all) passes whatever hypothesis ids it considers
    "accepted" for that call.

    `stage_end_date` (explicit or defaulted to `session_dates[-1]`) is a
    HARD limit, validated at construction (round-1 review finding #4):
    no `session_dates` entry may exceed it, and if `pit` exposes its own
    `.boundary.max_as_of` (a real `BoundedPITAccess`), `stage_end_date`
    may not exceed THAT either -- the engine never even attempts to
    iterate, let alone read PIT for, a session beyond the declared stage."""

    def __init__(
        self,
        pit: BoundedPITAccess,
        session_dates: Sequence[str],
        registry: HypothesisRegistry,
        accepted_hypothesis_ids: frozenset,
        entry_signals: Mapping[tuple[str, str], EntrySignal],
        invalidation_observer: InvalidationObserver,
        cost_assumptions: CostAssumptions,
        same_day_split_evidence: SameDayEvidenceProvider = _default_same_day_evidence,
        volatility_config: Optional[dict] = None,
        stage_end_date: Optional[str] = None,
    ):
        if not session_dates:
            raise ValueError("session_dates must be non-empty -- there is no session order to run")
        self.pit = pit
        self.session_dates = tuple(session_dates)
        self.registry = registry
        self.accepted_hypothesis_ids = frozenset(accepted_hypothesis_ids)
        self.entry_signals = entry_signals
        self.invalidation_observer = invalidation_observer
        self.cost_assumptions = cost_assumptions
        self.same_day_split_evidence = same_day_split_evidence
        self.volatility_config = volatility_config or _DEFAULT_VOLATILITY_CONFIG
        # Defaults to the last session actually run -- a caller may
        # override only to test a stage boundary narrower than the full
        # session_dates list it supplies.
        self.stage_end_date = stage_end_date or self.session_dates[-1]

        beyond_stage = [d for d in self.session_dates if d > self.stage_end_date]
        if beyond_stage:
            raise ValueError(
                f"session_dates contains {len(beyond_stage)} date(s) beyond stage_end_date="
                f"{self.stage_end_date!r} (e.g. {beyond_stage[0]!r}) -- the engine never runs, or reads "
                f"PIT for, a session past the declared stage limit (round-1 review finding #4)"
            )
        pit_boundary = getattr(pit, "boundary", None)
        pit_max_as_of = getattr(pit_boundary, "max_as_of", None)
        if pit_max_as_of is not None and self.stage_end_date > pit_max_as_of:
            raise ValueError(
                f"stage_end_date={self.stage_end_date!r} exceeds this pit's own authorized boundary "
                f"max_as_of={pit_max_as_of!r} -- the engine and the PIT facade it reads through must "
                f"agree on the stage limit (round-1 review finding #4)"
            )

        self._open_positions: dict[str, StopManagedPosition] = {}
        self._all_positions: list[StopManagedPosition] = []
        self._dispositions: list[EntryDisposition] = []
        # (close_price, session_date) per security -- the date is what
        # lets finalization tell a genuine final-session close apart from
        # a stale one carried forward from an earlier session.
        self._last_close_observation: dict[str, tuple[float, str]] = {}

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
            # Runs BEFORE Pas 2/3' -- a position closed here never reaches
            # either this session, taking priority over any stop/target
            # level that today's own price action would otherwise trigger.
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
                    self._evaluate_pending_entry(security_id, signal, signal_date, today, bars_for)

            # Pas 3': intrabar resolution for every position active today,
            # including one opened at Pas 2 above.
            for security_id, pos in list(self._open_positions.items()):
                bar = _find_bar(bars_for(security_id), today)
                if bar is None or bar.split_adjusted_open is None or bar.split_adjusted_high is None or bar.split_adjusted_low is None:
                    self._open_positions[security_id] = mark_session_data_unavailable(pos)
                    continue
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
                    self._last_close_observation[security_id] = (close_price, today)
                else:
                    pos = mark_session_data_unavailable(pos)

                observation_status = self.invalidation_observer(pos, today)
                pos = check_trend_invalidation(pos, today, observation_status)

                if not pos.closed and pos.remaining_quantity > 0 and close_price is not None:
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

        final_closes: dict[str, Optional[float]] = {}
        for security_id, pos in self._open_positions.items():
            self._all_positions.append(pos)
            observation = self._last_close_observation.get(security_id)
            # Round-1 review finding #3: only a close dated EXACTLY the
            # last session this engine ran counts as the final mark --
            # never a stale one from an earlier session silently reused.
            final_closes[security_id] = observation[0] if observation is not None and observation[1] == last_signal_date else None

        return SessionEngineResult(
            positions=tuple(self._all_positions),
            entry_dispositions=tuple(self._dispositions),
            final_closes=final_closes,
        )

    def _retire(self, security_id: str, position: StopManagedPosition) -> None:
        self._all_positions.append(position)
        del self._open_positions[security_id]

    def _resolve_variant_parameters(self, signal: EntrySignal):
        """Round-1 review finding #5. Returns (direction, k, r_multiple,
        fraction, rejection) -- `rejection` is one of the three
        `ENTRY_VARIANT_*`/`ENTRY_UNSUPPORTED_EXIT_FAMILY` constants, or
        `None` on success. Never reads PIT -- this check happens strictly
        before any price is touched."""
        variant = self.registry.get_variant(signal.strategy_variant_id)
        if variant is None:
            return None, None, None, None, ENTRY_VARIANT_NOT_FOUND
        if variant.parent_hypothesis_id not in self.accepted_hypothesis_ids:
            return None, None, None, None, ENTRY_VARIANT_NOT_IN_ACCEPTED_COHORT
        if variant.exit_hypothesis.exit_family != ExitFamily.STOP_MANAGED_INVALIDATION.value:
            return None, None, None, None, ENTRY_UNSUPPORTED_EXIT_FAMILY
        parent = self.registry.get(variant.parent_hypothesis_id)
        if parent is None:
            return None, None, None, None, ENTRY_VARIANT_NOT_IN_ACCEPTED_COHORT
        k = variant.exit_hypothesis.stop_loss.atr_multiple
        partial = variant.exit_hypothesis.partial_profit
        r_multiple = partial.r_multiple if partial is not None else None
        fraction = partial.fraction if partial is not None else None
        return parent.direction, k, r_multiple, fraction, None

    def _evaluate_pending_entry(self, security_id: str, signal: EntrySignal, signal_date: str, entry_date: str, bars_for) -> None:
        direction, k, r_multiple, fraction, rejection = self._resolve_variant_parameters(signal)
        if rejection is not None:
            self._dispositions.append(EntryDisposition(security_id, signal_date, entry_date, rejection))
            return

        bar = _find_bar(bars_for(security_id), entry_date)
        raw_open = bar.split_adjusted_open if bar is not None else None
        entry_fill_price = None
        if raw_open is not None:
            slippage_entry_rate = slippage_rate_from_bps(self.cost_assumptions.slippage_entry_bps)
            entry_fill_price = apply_entry_slippage(direction, raw_open, slippage_entry_rate)

        evidence = self.same_day_split_evidence(security_id, entry_date)
        position, entry_rejection = open_stop_managed_position(
            self.pit, security_id, direction, signal_date, entry_date, entry_fill_price,
            k, r_multiple, fraction, evidence, self.volatility_config,
        )
        if entry_rejection is not None:
            assert entry_rejection in (ENTRY_NO_ENTRY_BAR, ENTRY_NO_VALID_STOP_BASIS, ENTRY_INVALID_PROTECTIVE_LEVELS)
            self._dispositions.append(EntryDisposition(security_id, signal_date, entry_date, entry_rejection))
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
    per position in `positions`). Raises if a position is marked
    EVALUABLE/CENSORED but `final_closes` has no mark for it -- that is
    only possible if the caller derived `outcomes` from a DIFFERENT
    `final_closes` mapping than the one passed here (round-1 review
    finding #3: `classify_position()`'s own `final_mark_available` must
    always be computed from THIS SAME mapping)."""
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
            if mark_final is None:
                raise ValueError(
                    f"position {position.security_id!r} was classified {outcome.evaluability} but has no "
                    f"final mark in final_closes -- outcomes must be derived from THIS SAME final_closes "
                    f"mapping (final_mark_available=final_closes.get(security_id) is not None)"
                )
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
    without ever constructing a `SessionEngine` if the plan is rejected.
    Once accepted, `plan.hypothesis_cohort_ids` becomes the
    `SessionEngine`'s own `accepted_hypothesis_ids` -- every entry signal
    is resolved against THIS SAME cohort (round-1 review finding #5), so
    an accepted plan's own cost assumptions (`plan.cost_assumptions`) are
    what `SessionEngine` actually simulates with, never a caller-supplied
    substitute disconnected from the accepted plan."""
    accepted, errors = accept_research_plan(plan, registry, stop_managed_profile)
    if not accepted:
        raise PlanNotAcceptedError(f"ResearchPlan {plan.research_plan_id!r} rejected by accept_research_plan(): {errors}")
    engine = SessionEngine(
        pit, session_dates, registry, frozenset(plan.hypothesis_cohort_ids), entry_signals, invalidation_observer,
        plan.cost_assumptions, same_day_split_evidence, volatility_config, stage_end_date,
    )
    return engine.run()
