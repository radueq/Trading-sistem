"""Spec #005 -- Discovery Integration & Legacy Exits: turns Discovery's own
output (Spec #002 `DiscoveryObservation`) into the two vocabularies Spec
#004 already freezes but nothing before this delivery ever evaluated --
`EntryDefinition` matching and `InvalidationCondition` evaluation. Closes
`docs/spec005_known_limitations.md`'s first two outstanding obligations:
"turning Discovery lane STATES into an actual match against a variant's
EntryDefinition is a separate integration surface nothing... builds" and
"evaluating an InvalidationCondition against real Discovery lane output
does not exist anywhere in this codebase either."

Both read ONLY `state_signature`/`reason_codes` off a `DiscoveryObservation`
-- mirroring `evaluation.observations.signatures.matches()`'s own
established pattern for the structurally distinct #003
`EvaluationSignatureDefinition` vocabulary (Spec #004's own module
docstring: "deliberately OWN types... so a signature-matching condition
used to compute Evidence can never be silently confused with a
hypothesis's own runtime entry/exit vocabulary") -- never a new indicator,
never anything computed from raw/normalized feature values directly.

Scope boundary, stated explicitly: `matches_entry_definition()`/
`evaluate_invalidation_conditions()` and the two builders below all
consume a CALLER-SUPPLIED `observations_by_session` mapping (session_date
-> security_id -> `DiscoveryObservation`) -- `observations_by_session_
from_caches()` is a thin, purely-reshaping adapter over
`backtest.models.entities.HistoricalObservationCache` entries (Batch 2's
own already-accepted contract for exactly this data, produced by
`backtest.data.context.StageReadContext.get_or_compute_observations()`),
so a caller who wants LIVE, PIT-safe Discovery computation has a real,
tested path to it. `engine.run_stage()` itself still does not invoke this
module or `StageReadContext` internally -- it keeps taking `entry_signals`/
`invalidation_observer` exactly as before (Session Engine & Integration's
own accepted contract, never reopened here); a caller/test builds those
two values with the functions below, then passes them to `run_stage()`
unchanged. Deciding a canonical universe/benchmark/config-version policy
for `run_stage()` to resolve entirely on its own remains a further,
separate integration step -- `ResearchPlan` carries `benchmark_security_id`
but no canonical non-benchmark universe declaration yet.
"""
from __future__ import annotations

from typing import Mapping, Optional, Sequence

from discovery.models.entities import DiscoveryObservation

from hypothesis.models.entities import (
    EntryDefinition,
    InvalidationCondition,
    LaneStateCondition,
    ReasonCodeCondition,
)
from hypothesis.registry.hypotheses import HypothesisRegistry

from backtest.exits.engine import EntrySignal
from backtest.models.entities import HistoricalObservationCache

VALID_HOLD = "VALID_HOLD"
INVALIDATED = "INVALIDATED"
UNKNOWN = "UNKNOWN"
# Must equal `session.check_trend_invalidation()`'s own inline string
# literals exactly -- that already-accepted function is never touched
# here; these constants exist only so THIS module's own callers/tests
# never re-type the three strings by hand.

ObservationsBySession = Mapping[str, Mapping[str, DiscoveryObservation]]


def _entry_condition_matches(observation: DiscoveryObservation, condition) -> bool:
    if isinstance(condition, LaneStateCondition):
        result = observation.state_signature.get(condition.lane) == condition.label
    elif isinstance(condition, ReasonCodeCondition):
        result = condition.reason_code in observation.reason_codes
    else:
        raise TypeError(f"unsupported entry condition type {type(condition)!r}")
    return (not result) if condition.negate else result


def matches_entry_definition(observation: Optional[DiscoveryObservation], entry: EntryDefinition) -> bool:
    """Spec #004 SS11-13: AND over `core_conditions` PLUS
    `confirmation_conditions` -- both are a required-AND layer (see
    `EntryDefinition`'s own docstring), so there is no semantic difference
    in how the two are combined here, only in how they are budget-counted
    at proposal-validation time (`hypothesis.proposals.validator`, not this
    module's concern). `False` outright when no observation exists for
    this security at this session -- an ineligible/unobserved security can
    never satisfy an entry thesis (Spec #002's own eligibility gate already
    decided this security produced nothing to evaluate)."""
    if observation is None:
        return False
    conditions = tuple(entry.core_conditions) + tuple(entry.confirmation_conditions)
    return all(_entry_condition_matches(observation, c) for c in conditions)


def _reason_code_condition_triggered(
    current: DiscoveryObservation, entry: DiscoveryObservation, condition: InvalidationCondition,
) -> bool:
    present_now = condition.reason_code in current.reason_codes
    present_at_entry = condition.reason_code in entry.reason_codes
    if condition.triggers_on_presence:
        return present_now and not present_at_entry
    return present_at_entry and not present_now


def evaluate_invalidation_conditions(
    current_observation: Optional[DiscoveryObservation],
    entry_observation: Optional[DiscoveryObservation],
    conditions: Sequence[InvalidationCondition],
) -> str:
    """Spec #004's own vocabulary for BOTH families that carry
    `invalidation_conditions` (SIGNAL_INVALIDATION and
    STOP_MANAGED_INVALIDATION alike -- the field is shared on
    `ExitHypothesis`, never family-specific): lane-based
    (`InvalidationCondition.lane` set) invalidates when the CURRENT
    observed lane label is not one of `holds_labels`; reason-code-based
    (`InvalidationCondition.reason_code` set) invalidates when that reason
    code's presence FLIPS relative to `entry_observation` -- both exactly
    as `InvalidationCondition`'s own docstring specifies.

    Combining MULTIPLE conditions in `conditions` as an OR (any one
    triggering invalidates the whole position) is EXPLICIT contract text,
    not this function's own inference (an earlier version of this
    docstring wrongly called it one -- corrected in the Batch 3 closure
    verification): `docs/spec005_exit_amendment_v1.0.md` section 8 states
    "Combinare OR intre conditii multiple (regula sectiunea 10 existenta)"
    -- OR combination between multiple conditions is the EXISTING (base
    spec) section 10 rule, reused unchanged for the new family. It also
    happens to read as the conservative, risk-side choice (any one broken
    thesis condition is enough to invalidate), consistent with
    `advance_intrabar()`'s own stop-before-target tie-break precedent (the
    protective/risk-side signal always wins) -- but that consistency is a
    happy coincidence here, not the source of the rule.

    Returns `UNKNOWN` (never a false negative) when `current_observation`
    is missing entirely, when the tracked LANE ITSELF is absent from
    `current_observation.state_signature` (GPT review finding #1: a lane
    a security's own feature computation could not produce -- e.g.
    insufficient history for that lane's percentile window -- is a DATA
    GAP, structurally identical to a missing observation altogether, never
    evidence that the label left `holds_labels`), or when a reason-code
    condition cannot be evaluated for lack of `entry_observation` -- but an
    INVALIDATED result from any OTHER, evaluable condition is still
    reported: a definite invalidation is never suppressed by an unrelated
    data gap."""
    if current_observation is None:
        return UNKNOWN
    saw_unknown = False
    for condition in conditions:
        if condition.lane is not None:
            if condition.lane not in current_observation.state_signature:
                saw_unknown = True
                continue
            if current_observation.state_signature[condition.lane] not in (condition.holds_labels or ()):
                return INVALIDATED
        else:
            if entry_observation is None:
                saw_unknown = True
                continue
            if _reason_code_condition_triggered(current_observation, entry_observation, condition):
                return INVALIDATED
    return UNKNOWN if saw_unknown else VALID_HOLD


def _validate_observations_by_session(observations_by_session: ObservationsBySession) -> None:
    """GPT review finding #2: neither builder below checked that an
    observation filed under `observations_by_session[as_of][security_id]`
    actually IS that exact `(security_id, as_of)` pair's own observation.
    Inconsistent input -- an observation carrying a DIFFERENT `as_of` or
    `security_id` than the key it is filed under, however it got there --
    could otherwise silently produce a signal or an invalidation verdict
    grounded in the wrong day or the wrong instrument (repro: key
    `(SEC, 2024-01-01)` holding an observation actually dated
    `2024-06-01`). Checked eagerly, over the WHOLE mapping, before either
    builder does any matching/evaluation at all -- mirrors `SessionEngine.
    __init__()`'s own entry_signals identity-mismatch discipline (Session
    Engine & Integration review, round-2 follow-up), applied here to
    observations instead of signals."""
    for as_of, observations_by_security in observations_by_session.items():
        for security_id, observation in observations_by_security.items():
            if observation.security_id != security_id or observation.as_of != as_of:
                raise ValueError(
                    f"observations_by_session[{as_of!r}][{security_id!r}] holds a DiscoveryObservation "
                    f"for (security_id={observation.security_id!r}, as_of={observation.as_of!r}) instead "
                    f"-- every observation must match the exact (security_id, session_date) key it is "
                    f"filed under, rejected before any matching or invalidation evaluation ever runs"
                )


def observations_by_session_from_caches(caches: Mapping[str, HistoricalObservationCache]) -> dict[str, dict[str, DiscoveryObservation]]:
    """Thin reshaping adapter over Batch 2's already-accepted
    `HistoricalObservationCache` (produced by `backtest.data.context.
    StageReadContext.get_or_compute_observations()`, one call per session
    date) into the `ObservationsBySession` shape the two functions below
    consume -- the caller loops `session_dates` itself and supplies one
    cache entry per date; this function does no PIT access, no caching,
    and no Discovery computation of its own.

    GPT review finding #2: the ORIGINAL version checked only `cache.as_of`
    against its own dict key -- never each individual observation INSIDE
    `cache.observations` against that same `as_of`, and never rejected two
    observations for the SAME `security_id` inside one cache entry (a
    dict comprehension keyed by `security_id` would silently let the LAST
    one win). Both are checked here now, before the reshaped mapping is
    ever returned."""
    result: dict[str, dict[str, DiscoveryObservation]] = {}
    for as_of, cache in caches.items():
        if cache.as_of != as_of:
            raise ValueError(
                f"caches key {as_of!r} does not match its own HistoricalObservationCache.as_of={cache.as_of!r} "
                f"-- caches must be keyed by the exact as_of each entry was computed for"
            )
        by_security: dict[str, DiscoveryObservation] = {}
        for observation in cache.observations:
            if observation.as_of != as_of:
                raise ValueError(
                    f"HistoricalObservationCache for as_of={as_of!r} contains an observation dated "
                    f"{observation.as_of!r} (security_id={observation.security_id!r}) -- every observation "
                    f"inside a cache entry must match that entry's own as_of"
                )
            if observation.security_id in by_security:
                raise ValueError(
                    f"HistoricalObservationCache for as_of={as_of!r} contains two observations for "
                    f"security_id={observation.security_id!r} -- duplicate observations for the same "
                    f"instrument/session are rejected outright, never silently overwritten"
                )
            by_security[observation.security_id] = observation
        result[as_of] = by_security
    return result


def build_entry_signals_from_observations(
    observations_by_session: ObservationsBySession,
    registry: HypothesisRegistry,
    accepted_hypothesis_ids: frozenset,
) -> dict[tuple[str, str, str], EntrySignal]:
    """For every session date in `observations_by_session`, for every
    ACCEPTED hypothesis (never one outside `accepted_hypothesis_ids`, the
    exact same cohort restriction `SessionEngine`/`LegacySessionEngine`
    already enforce at entry-resolution time), for every observed security
    whose observation matches that hypothesis's OWN `entry_definition`
    (the family-level, shared-by-every-variant condition -- Spec #004
    SS110-D: "a different direction or different entry_definition is
    always a DIFFERENT StrategyHypothesis, never a variant of this one"):
    emits one `EntrySignal`, keyed at `(security_id, strategy_variant_id,
    session_date)`, for EVERY variant of that hypothesis -- materializing
    the entry in parallel across every exit strategy the hypothesis
    considered (mirrors `materialize_variants()`'s own "every candidate
    value already exists, #005 only ever selects among them" discipline).
    `run_stage()`'s own family-partitioning then routes each signal to
    whichever engine (`SessionEngine` or `LegacySessionEngine`) actually
    implements that variant's exit family -- this function does not need
    to know or care which.

    Validates `observations_by_session`'s own (security_id, as_of,
    observation) identity FIRST (GPT review finding #2), before any
    matching runs."""
    _validate_observations_by_session(observations_by_session)
    signals: dict[tuple[str, str, str], EntrySignal] = {}
    for session_date, observations_by_security in observations_by_session.items():
        for hypothesis_id in accepted_hypothesis_ids:
            hypothesis = registry.get(hypothesis_id)
            if hypothesis is None:
                continue
            variants = registry.variants_for(hypothesis_id)
            if not variants:
                continue
            for security_id, observation in observations_by_security.items():
                if not matches_entry_definition(observation, hypothesis.entry_definition):
                    continue
                for variant in variants:
                    key = (security_id, variant.strategy_variant_id, session_date)
                    signals[key] = EntrySignal(security_id=security_id, strategy_variant_id=variant.strategy_variant_id)
    return signals


def build_invalidation_observer(
    observations_by_session: ObservationsBySession,
    registry: HypothesisRegistry,
):
    """Returns a closure satisfying BOTH `engine.InvalidationObserver` and
    `legacy.LegacyInvalidationObserver`'s identical duck-typed contract
    (`Callable[[position, session_date], str]`, needing only `.security_id`
    and `.strategy_variant_id` off `position` -- both `StopManagedPosition`
    and `LegacyPosition` carry them): resolves `position.strategy_
    variant_id`'s OWN `invalidation_conditions` via `registry` (the SAME
    field, shared across STOP_MANAGED_INVALIDATION and SIGNAL_INVALIDATION
    alike -- see `evaluate_invalidation_conditions()`'s own docstring), and
    evaluates them against `observations_by_session[session_date]`/
    `observations_by_session[position.entry_date]`. A position whose
    variant cannot be resolved (should never happen for a position this
    engine itself opened, since opening already required a resolvable,
    in-cohort variant) is treated as `UNKNOWN` rather than raising --
    an invalidation OBSERVER's job is to report what it can see, never to
    re-litigate an entry decision that already happened.

    Validates `observations_by_session`'s own (security_id, as_of,
    observation) identity FIRST (GPT review finding #2), at closure-
    BUILD time -- before the closure is ever handed to an engine, let
    alone called -- never lazily on the first call."""
    _validate_observations_by_session(observations_by_session)

    def observer(position, session_date: str) -> str:
        variant = registry.get_variant(position.strategy_variant_id)
        if variant is None:
            return UNKNOWN
        conditions = variant.exit_hypothesis.invalidation_conditions
        current = observations_by_session.get(session_date, {}).get(position.security_id)
        entry_obs = observations_by_session.get(position.entry_date, {}).get(position.security_id)
        return evaluate_invalidation_conditions(current, entry_obs, conditions)
    return observer
