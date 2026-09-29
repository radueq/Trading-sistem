"""Shared helpers for building REAL, registered TIME_EXIT and
SIGNAL_INVALIDATION `StrategyHypothesis`/`StrategyVariant` pairs -- the
`backtest.exits.legacy` counterpart of `stop_managed_variants.py`'s own
`build_registered_stop_managed_hypothesis()`, used by the legacy-engine
and mixed-family tests so neither engine's tests need a caller-typed
direction/exit-parameters dict floating free of any actual hypothesis.
"""
from __future__ import annotations

import dataclasses
from typing import Optional

from hypothesis.models.entities import (
    Direction,
    EntryDefinition,
    EvidenceProvenance,
    ExitFamily,
    ExitHypothesis,
    HorizonCandidateSet,
    HypothesisComplexitySnapshot,
    HypothesisProvenance,
    HypothesisResearchMode,
    HypothesisStatus,
    InvalidationCondition,
    LaneStateCondition,
    ParameterSource,
    StrategyHypothesis,
)
from hypothesis.registry.hypotheses import HypothesisRegistry, build_hypothesis_id, hypothesis_fingerprint, materialize_variants

_EVIDENCE = dict(
    evaluation_run_id="run_x", evaluation_engine_version="v1.0.0", evaluation_config_version="cfg_eval",
    signature_id="SIG_X", signature_set_id="sigset_x", discovery_engine_version="v1.0.0",
    discovery_config_version="cfg_disc", timeframe="1D",
)

_DEFAULT_ENTRY = EntryDefinition(core_conditions=(LaneStateCondition("volatility", "COMPRESSION"),))


def _register_hypothesis_with_variants(
    registry: HypothesisRegistry, direction: str, signature_id: str, horizon_values: tuple[int, ...],
    signal_invalidation_exits: tuple[ExitHypothesis, ...], entry: EntryDefinition,
) -> StrategyHypothesis:
    horizons = HorizonCandidateSet(unit="BARS", values=horizon_values, selection_basis="x", parameter_source=ParameterSource.PRE_SPECIFIED.value)
    ev = EvidenceProvenance(**{**_EVIDENCE, "signature_id": signature_id})
    fp = hypothesis_fingerprint(signature_id, direction, entry, "NEXT_BAR_OPEN", horizons, ev, "cfg_hyp_x")
    hid, dh = build_hypothesis_id(fp)
    comp = HypothesisComplexitySnapshot(3, 1, "cfg_hyp_x")
    prov = HypothesisProvenance("HUMAN:radu", None, None, "radu", "t")
    hyp = StrategyHypothesis(
        hypothesis_id=hid, hypothesis_version=1, definition_hash=dh, status=HypothesisStatus.PREREGISTERED.value,
        research_mode=HypothesisResearchMode.PREREGISTERED_STRATEGY.value, parent_signature_id=signature_id,
        signature_set_id="sigset_x", direction=direction, direction_basis="EVIDENCE_SIGN",
        entry_definition=entry, entry_execution_policy="NEXT_BAR_OPEN", horizon_candidate_set=horizons,
        variant_ids=(), evidence_provenance=ev, hypothesis_provenance=prov, constraints=comp,
        created_at="t", created_by="radu", strategy_config_version="cfg_hyp_x",
    )
    variants = materialize_variants(hyp, signal_invalidation_exits=signal_invalidation_exits, created_at="t")
    hyp = dataclasses.replace(hyp, variant_ids=tuple(v.strategy_variant_id for v in variants))
    registry._force_register(hyp)
    for v in variants:
        registry.register_variant(v)
    return hyp


def build_registered_time_exit_hypothesis(
    registry: HypothesisRegistry, direction: str = Direction.LONG.value, time_exit_bars: int = 3,
    signature_id: str = "SIG_TIME_EXIT", entry: Optional[EntryDefinition] = None,
) -> tuple[str, str]:
    """Registers a hypothesis whose ONLY variant (no extra
    `signal_invalidation_exits` supplied) is a single, auto-materialized
    TIME_EXIT variant with `time_exit_bars`. Returns (hypothesis_id,
    strategy_variant_id)."""
    hyp = _register_hypothesis_with_variants(
        registry, direction, signature_id, (time_exit_bars,), (), entry or _DEFAULT_ENTRY,
    )
    (variant,) = registry.variants_for(hyp.hypothesis_id)
    return hyp.hypothesis_id, variant.strategy_variant_id


def build_signal_invalidation_exit_hypothesis(
    max_holding_bars: int = 5,
    invalidation_conditions: tuple[InvalidationCondition, ...] = (
        InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),
    ),
) -> ExitHypothesis:
    return ExitHypothesis(
        exit_family=ExitFamily.SIGNAL_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=invalidation_conditions, max_holding_bars=max_holding_bars,
    )


def build_registered_signal_invalidation_hypothesis(
    registry: HypothesisRegistry, direction: str = Direction.LONG.value, max_holding_bars: int = 5,
    invalidation_conditions: tuple[InvalidationCondition, ...] = (
        InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),
    ),
    signature_id: str = "SIG_SIGNAL_INVALIDATION", entry: Optional[EntryDefinition] = None,
    include_time_exit_horizon: Optional[int] = None,
) -> tuple[str, str]:
    """Registers a hypothesis with exactly one SIGNAL_INVALIDATION
    variant, plus an auto-materialized TIME_EXIT variant too IFF
    `include_time_exit_horizon` is given (mirrors `stop_managed_variants.
    py`'s own always-present horizon_candidate_set -- kept OPTIONAL here,
    defaulting to a single-value horizon set of `[1]` only when a caller
    genuinely needs a second, TIME_EXIT variant alongside; a caller
    testing SIGNAL_INVALIDATION in isolation gets exactly one variant, no
    incidental TIME_EXIT sibling to filter out). Returns (hypothesis_id,
    strategy_variant_id) for the SIGNAL_INVALIDATION variant."""
    exit_h = build_signal_invalidation_exit_hypothesis(max_holding_bars, invalidation_conditions)
    # HorizonCandidateSet.values cannot be empty, so a TIME_EXIT variant is
    # always auto-materialized alongside the requested SIGNAL_INVALIDATION
    # one -- `include_time_exit_horizon` only controls WHICH bar count it
    # uses; callers not asking for a TIME_EXIT sibling still get one (with
    # horizon `1`) but simply never look it up.
    horizon_values = (include_time_exit_horizon,) if include_time_exit_horizon is not None else (1,)
    hyp = _register_hypothesis_with_variants(
        registry, direction, signature_id, horizon_values, (exit_h,), entry or _DEFAULT_ENTRY,
    )
    variants = registry.variants_for(hyp.hypothesis_id)
    signal_variant = next(v for v in variants if v.exit_hypothesis.exit_family == ExitFamily.SIGNAL_INVALIDATION.value)
    return hyp.hypothesis_id, signal_variant.strategy_variant_id
