"""Spec #005 Batch 3 -- typed contracts for the STOP_MANAGED_INVALIDATION
position engine (docs/spec005_exit_amendment_v1.0.md, ACCEPTED).

Frozen dataclasses updated only via `dataclasses.replace()`-returning pure
functions in `backtest.exits.protection`/`session` -- same discipline as
every other #004/#005 entity (never mutated in place).

Spec #005 -- Discovery Integration & Legacy Exits (additive): also carries
`LegacyPosition`, the equivalent typed contract for the two OLDER exit
families (TIME_EXIT/SIGNAL_INVALIDATION), updated only via
`dataclasses.replace()`-returning functions in `backtest.exits.legacy` --
same discipline, same module, no `StopManagedPosition` field or behavior
touched.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional

from backtest.models.entities import canonical_json

# --------------------------------------------------------------------------
# Facets (amendment section 10)
# --------------------------------------------------------------------------

# Facet 1 -- lifecycle state (exclusive, exhaustive).
LIFECYCLE_CLOSED = "CLOSED"
LIFECYCLE_CENSORED_AT_HORIZON = "CENSORED_AT_HORIZON"
LIFECYCLE_EXIT_FAILED = "EXIT_FAILED"

# Facet 2 -- evaluability.
EVALUABILITY_EVALUABLE = "EVALUABLE"
EVALUABILITY_UNEVALUABLE = "UNEVALUABLE"

# Facet 3 -- reason (None allowed for a clean evaluation).
REASON_NO_EXIT_BAR = "NO_EXIT_BAR"
REASON_TRAILING_PATH_INCOMPLETE = "TRAILING_PATH_INCOMPLETE"
REASON_INVALIDATION_PATH_INCOMPLETE = "INVALIDATION_PATH_INCOMPLETE"
REASON_SPLIT_RECONCILIATION_INCOMPLETE = "SPLIT_RECONCILIATION_INCOMPLETE"
REASON_CENSORED_MARK_UNAVAILABLE = "CENSORED_MARK_UNAVAILABLE"
REASON_UNKNOWN_ADJUSTMENT_BASIS = "UNKNOWN_ADJUSTMENT_BASIS"

# Entry-time rejection reasons (amendment section 2, checked in this exact
# order -- each disposition is recorded explicitly, never a silent drop).
ENTRY_SUPPRESSED_STAGE_BOUNDARY = "SUPPRESSED_STAGE_BOUNDARY"
ENTRY_NO_ENTRY_BAR = "NO_ENTRY_BAR"
ENTRY_NO_VALID_STOP_BASIS = "NO_VALID_STOP_BASIS"
ENTRY_INVALID_PROTECTIVE_LEVELS = "INVALID_PROTECTIVE_LEVELS"

# Session Engine & Integration review round 1, finding #5: an entry
# signal must resolve to a REAL variant, belonging to the PLAN'S OWN
# accepted cohort, whose exit_family this engine actually implements --
# checked BEFORE any price is read, exactly like the four reasons above.
ENTRY_VARIANT_NOT_FOUND = "VARIANT_NOT_FOUND"
ENTRY_VARIANT_NOT_IN_ACCEPTED_COHORT = "VARIANT_NOT_IN_ACCEPTED_COHORT"
ENTRY_UNSUPPORTED_EXIT_FAMILY = "UNSUPPORTED_EXIT_FAMILY"

# Exit reasons for a single tranche.
EXIT_REASON_TARGET = "TARGET"
EXIT_REASON_STOP = "STOP"
EXIT_REASON_INVALIDATION = "INVALIDATION"

# Spec #005 -- Discovery Integration & Legacy Exits: exit reasons for a
# LegacyPosition's single closing tranche (TIME_EXIT/SIGNAL_INVALIDATION
# never have a partial-profit tranche at all -- exactly one tranche, ever,
# for the whole original quantity). None of these equal EXIT_REASON_TARGET,
# so `costs.apply_exit_slippage()` already applies its adverse-slippage
# branch to every one of them unmodified -- a legacy exit is always a
# market order, never the STOP_MANAGED family's own no-slippage limit fill.
EXIT_REASON_TIME_EXIT = "TIME_EXIT"
EXIT_REASON_SIGNAL_INVALIDATION = "SIGNAL_INVALIDATION"
EXIT_REASON_MAX_HOLDING_BARS_FORCED_EXIT = "MAX_HOLDING_BARS_FORCED_EXIT"

AMBIGUOUS_INTRABAR_CONFLICT = "AMBIGUOUS_INTRABAR_CONFLICT"


@dataclass(frozen=True)
class Tranche:
    """One executed sale out of a STOP_MANAGED_INVALIDATION position
    (amendment section 4/9/12): either the partial-profit tranche (target
    hit) or the closing tranche for whatever quantity was still active
    when the position finally closed. `fraction_of_original` is the
    ORIGINAL nominal quantity's share this tranche represents -- an
    adimensional fraction, never rescaled by a later split (section 6:
    "Ponderea e o fracție din cantitatea ORIGINALĂ... neafectată de
    split"). `holding_days` is THIS tranche's own calendar days (entry to
    its own exit), used unweighted inside its own borrow_drag term
    (section 9).

    `entry_fill_price_reference` (GPT review, round 2, finding #5) is a
    SNAPSHOT of `position.entry_fill_price` taken at the exact moment
    this tranche was created -- never the position's CURRENT (possibly
    later-rescaled-by-a-subsequent-split) `entry_fill_price`. Section 6 is
    explicit that reconciliation must never modify "valoarea economică...
    a unei tranșe deja vândute -- fapte istorice fixate la momentul lor";
    without this snapshot, a split occurring AFTER this tranche closed
    would silently corrupt its return (the historical `exit_fill_price`
    combined with a since-rescaled entry price). Every cost/return
    computation for this tranche MUST use this field, never `position.
    entry_fill_price` directly."""
    kind: str  # "PARTIAL_PROFIT" | "REMAINDER"
    exit_reason: str  # EXIT_REASON_* constant
    fraction_of_original: float
    exit_date: str
    exit_fill_price: float  # F_x
    holding_days: int
    entry_fill_price_reference: float  # F_e, as it stood when THIS tranche closed


@dataclass(frozen=True)
class StopManagedPosition:
    """Live simulation state for one STOP_MANAGED_INVALIDATION position.
    Updated only via `dataclasses.replace()` inside
    `backtest.exits.protection`/`backtest.exits.session` -- callers never
    mutate a field directly. `remaining_quantity` is a fraction of the
    ORIGINAL nominal quantity (1.0 at entry), rescaled by a split ratio at
    Pas 0 (section 6) but otherwise only ever decreased by an executed
    sale."""
    security_id: str
    direction: str  # "LONG" | "SHORT"
    entry_date: str
    signal_date: str  # s, for audit/re-reconciliation reference only
    entry_fill_price: float  # F_e (current basis, rescaled by Pas 0 like everything else)
    k: float
    r_multiple: Optional[float]
    fraction: Optional[float]

    active_stop: float  # S_activ
    initial_risk: float  # risc_inițial (fixed at entry, rescaled only by split ratio)
    target_price: Optional[float]  # țintă (None if no partial_profit)

    remaining_quantity: float = 1.0
    applied_factor: float = 1.0
    processed_split_action_ids: tuple[str, ...] = field(default_factory=tuple)

    target_consumed: bool = False
    partial_tranche: Optional[Tranche] = None

    closed: bool = False
    close_tranche: Optional[Tranche] = None

    ambiguous_intrabar_conflicts: int = 0
    trailing_path_incomplete: bool = False
    invalidation_path_incomplete: bool = False
    split_reconciliation_incomplete: bool = False
    exit_failed: bool = False
    exit_failed_reason: Optional[str] = None

    # Set by `session.check_trend_invalidation()` when INVALIDATED is
    # detected at a session's close; consumed by
    # `session.execute_scheduled_invalidation()` at the scheduled
    # NEXT_SESSION_OPEN -- amendment section 10's "an invalidation
    # detected at the stage's last close, with fill due next stage,
    # stays CENSORED_AT_HORIZON, never EXIT_FAILED."
    pending_invalidation_detected_date: Optional[str] = None

    # Session Engine & Integration review, round 2, finding #3: additive,
    # optional (never populated by `protection.py`/`session.py` -- every
    # existing hand-built `StopManagedPosition(...)` in this package's own
    # unit tests stays valid, unchanged). `backtest.exits.engine.
    # SessionEngine` stamps this immediately after opening a position, so
    # two DIFFERENT variants trading the SAME security_id concurrently
    # produce two distinguishable positions in a result set -- never one
    # silently shadowing the other.
    strategy_variant_id: Optional[str] = None
    pending_exit_note: Optional[str] = None


@dataclass(frozen=True)
class LegacyPosition:
    """Spec #005 -- Discovery Integration & Legacy Exits: live simulation
    state for one TIME_EXIT or SIGNAL_INVALIDATION position -- structurally
    simpler than `StopManagedPosition` because neither older family has a
    stop, a target, or a partial-profit tranche. `exit_execution_policy`
    IS fixed `BAR_CLOSE` for both (Spec #004 HYPOTHESIS_ENGINE_VERSION
    contract), and `TIME_EXIT`/the `max_holding_bars` cap DO close at that
    same scheduled bar's own close, immediately (`TIME_EXIT_FILL_V1`/
    `CAP_FILL_V1` = `SCHEDULED_..._BAR_CLOSE`, `backtest.models.entities`).

    Closure verification finding (post-`9feb4a5`): an EARLIER version of
    this module wrongly assumed `SIGNAL_INVALIDATION` shared that same
    immediate-close behavior too. It does not. `ExecutionSemanticsProfile`
    v1 (Spec #005 SS9, `backtest.models.entities` -- the ONE base profile
    every exit family shares, not something `StopManagedPosition` added on
    its own) separates `invalidation_detection = COMPLETED_BAR_CLOSE` from
    `invalidation_fill = NEXT_SESSION_OPEN_AFTER_DETECTION`: a detected
    invalidation is scheduled, filling at the FOLLOWING session's open,
    exactly the same "detected at close(t), executed at t+1's open" shape
    `StopManagedPosition.pending_invalidation_detected_date` already
    tracks for its own family. `pending_invalidation_detected_date` below
    is that same state, reused for this family -- consumed by
    `backtest.exits.legacy.execute_scheduled_legacy_invalidation()`. The
    hard `max_holding_bars` cap is unaffected: it still closes at ITS OWN
    scheduled close, even in the same session an invalidation is also
    detected -- there is nothing left to schedule a fill against once the
    cap has already closed the position.

    `entry_session_index` is this position's own index into the stage's
    `session_dates` sequence at entry -- TIME_EXIT's holding-bar count
    (Spec #004: "holding bar 1 = entry bar itself; holding bar N = entry
    bar index + (N-1)") is defined against the CALENDAR's own session
    order, not against how many bars this particular security happened to
    have a price for, so the count is `session_index - entry_session_index
    + 1` at any later session, never a separately-incremented counter that
    could drift out of sync with the loop's own position.

    `entry_fill_price`/`applied_factor`/`processed_split_action_ids` exist
    for exactly the same reason they do on `StopManagedPosition`: a split
    between entry and a later as-of query re-expresses historical bars on a
    DIFFERENT basis than the one `entry_fill_price` was frozen under at
    entry time (amendment section 6's staleness problem applies to ANY
    frozen entry-time price, not only a STOP_MANAGED one) -- see
    `backtest.exits.legacy.reconcile_split_for_legacy_position()`, an
    independent reimplementation (never a refactor of the already-accepted
    `session.reconcile_split_for_open_position()`) of the same
    authorization/lateness logic, narrowed to the one field a
    `LegacyPosition` actually has to rescale."""
    security_id: str
    strategy_variant_id: str
    exit_family: str  # ExitFamily.TIME_EXIT.value | ExitFamily.SIGNAL_INVALIDATION.value
    direction: str  # "LONG" | "SHORT"
    signal_date: str
    entry_date: str
    entry_session_index: int
    entry_fill_price: float  # F_e (current basis, rescaled by split reconciliation like StopManagedPosition)

    time_exit_bars: Optional[int] = None  # set iff exit_family == TIME_EXIT
    max_holding_bars: Optional[int] = None  # set iff exit_family == SIGNAL_INVALIDATION

    applied_factor: float = 1.0
    processed_split_action_ids: tuple[str, ...] = field(default_factory=tuple)

    closed: bool = False
    close_tranche: Optional[Tranche] = None

    exit_failed: bool = False
    exit_failed_reason: Optional[str] = None

    invalidation_path_incomplete: bool = False
    split_reconciliation_incomplete: bool = False

    # Closure verification fix (post-9feb4a5): set by
    # `legacy.advance_legacy_position_at_close()` when SIGNAL_INVALIDATION
    # detects INVALIDATED at this session's close; consumed by
    # `legacy.execute_scheduled_legacy_invalidation()` at the scheduled
    # NEXT_SESSION_OPEN_AFTER_DETECTION -- the same shape
    # `StopManagedPosition.pending_invalidation_detected_date` already has.
    pending_invalidation_detected_date: Optional[str] = None
    pending_exit_note: Optional[str] = None


@dataclass(frozen=True)
class PositionOutcome:
    """The three-facet classification (amendment section 10) for one
    position at the point it stops evolving (closed, or the stage ends).
    `net_return` is populated only when `evaluability == EVALUABLE`."""
    lifecycle: str  # LIFECYCLE_* constant
    evaluability: str  # EVALUABILITY_* constant
    reason: Optional[str]  # REASON_* constant, or None
    net_return: Optional[float] = None


# --------------------------------------------------------------------------
# StopManagedExecutionSemanticsProfile (amendment section 7) -- a wholly
# separate structure from backtest.models.entities.ExecutionSemanticsProfile,
# independently versioned/fingerprinted, never touching that type's own
# fields or fingerprint function.
# --------------------------------------------------------------------------

STOP_LOSS_DETECTION_V1 = "INTRA_BAR_LOW_HIGH_BREACH"
STOP_LOSS_FILL_V1 = "SAME_BAR_AT_LEVEL_OR_WORSE_OPEN"
PARTIAL_PROFIT_FILL_V1 = "SAME_BAR_AT_TARGET_OR_BETTER_OPEN"


@dataclass(frozen=True)
class StopManagedExecutionSemanticsProfile:
    """Amendment section 7: frozen fill-timing rules for the
    STOP_MANAGED_INVALIDATION family. Trend invalidation on the remaining
    quantity reuses the EXISTING `ExecutionSemanticsProfile`'s
    `invalidation_detection`/`invalidation_fill` values unchanged (no
    field for them here -- see the profile's own module docstring in
    `backtest.models.entities`). `cap_is_hard` has no counterpart here at
    all: structurally inapplicable, never implicitly inherited from the
    old profile."""
    profile_id: str
    profile_hash: str

    stop_loss_detection: str
    stop_loss_fill: str
    partial_profit_fill: str


def stop_managed_execution_semantics_fingerprint(
    stop_loss_detection: str, stop_loss_fill: str, partial_profit_fill: str,
) -> str:
    payload = {
        "stop_loss_detection": stop_loss_detection,
        "stop_loss_fill": stop_loss_fill,
        "partial_profit_fill": partial_profit_fill,
    }
    return canonical_json(payload)


def build_stop_managed_execution_semantics_profile_id(fingerprint: str) -> tuple[str, str]:
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    return f"smxp_{digest}", digest


def build_stop_managed_execution_semantics_profile_v1() -> StopManagedExecutionSemanticsProfile:
    """The ONE profile V1 defines -- not a free parameter. Mirrors
    `backtest.models.entities.build_execution_semantics_profile_v1()`'s
    own pattern exactly, on this wholly separate structure."""
    fp = stop_managed_execution_semantics_fingerprint(
        STOP_LOSS_DETECTION_V1, STOP_LOSS_FILL_V1, PARTIAL_PROFIT_FILL_V1,
    )
    profile_id, digest = build_stop_managed_execution_semantics_profile_id(fp)
    return StopManagedExecutionSemanticsProfile(
        profile_id=profile_id, profile_hash=digest,
        stop_loss_detection=STOP_LOSS_DETECTION_V1, stop_loss_fill=STOP_LOSS_FILL_V1,
        partial_profit_fill=PARTIAL_PROFIT_FILL_V1,
    )


def verify_stop_managed_execution_semantics_profile_v1(
    profile: StopManagedExecutionSemanticsProfile,
) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    for name, actual, expected in (
        ("stop_loss_detection", profile.stop_loss_detection, STOP_LOSS_DETECTION_V1),
        ("stop_loss_fill", profile.stop_loss_fill, STOP_LOSS_FILL_V1),
        ("partial_profit_fill", profile.partial_profit_fill, PARTIAL_PROFIT_FILL_V1),
    ):
        if actual != expected:
            errors.append(f"{name} must be {expected!r} in V1, got {actual!r}")
    fp = stop_managed_execution_semantics_fingerprint(
        profile.stop_loss_detection, profile.stop_loss_fill, profile.partial_profit_fill,
    )
    expected_id, expected_hash = build_stop_managed_execution_semantics_profile_id(fp)
    if profile.profile_id != expected_id or profile.profile_hash != expected_hash:
        errors.append(
            f"profile content-address mismatch: stored profile_id={profile.profile_id!r}/"
            f"profile_hash={profile.profile_hash!r} does not match the id/hash recomputed from "
            f"the profile's own fields ({expected_id!r}/{expected_hash!r})"
        )
    return (not errors, tuple(errors))
