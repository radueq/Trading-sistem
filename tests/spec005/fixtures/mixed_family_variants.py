"""Shared helper for building ONE `StrategyHypothesis` whose materialized
variants span all THREE exit families at once (TIME_EXIT auto-derived from
`horizon_candidate_set`, plus an explicit STOP_MANAGED_INVALIDATION and an
explicit SIGNAL_INVALIDATION `ExitHypothesis` via `materialize_variants()`'s
own `signal_invalidation_exits` parameter, which accepts any family) -- the
"one shared entry decision, several exit strategies tested in parallel"
scenario `docs/spec005_known_limitations.md` describes as the reason
`StrategyVariant`s exist at all. Used by the mixed-cohort `run_stage()`
integration test (Spec #005 -- Discovery Integration & Legacy Exits).

STOP_MANAGED_INVALIDATION's own invalidation lane is deliberately
DIFFERENT from SIGNAL_INVALIDATION's default ("momentum" vs.
"relative_strength") so a single Discovery observation sequence can
invalidate one family without the other -- `stop_managed_variants.
build_stop_managed_exit_hypothesis()` hardcodes "relative_strength" and
takes no lane parameter, so it is not reused here; this is an independent,
narrowly-scoped `ExitHypothesis` construction, not a modification of that
function.
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
    PartialProfitRule,
    StopLossRule,
    StrategyHypothesis,
)
from hypothesis.registry.hypotheses import HypothesisRegistry, build_hypothesis_id, hypothesis_fingerprint, materialize_variants

from spec005.fixtures.legacy_variants import build_signal_invalidation_exit_hypothesis

_EVIDENCE = dict(
    evaluation_run_id="run_x", evaluation_engine_version="v1.0.0", evaluation_config_version="cfg_eval",
    signature_id="SIG_X", signature_set_id="sigset_x", discovery_engine_version="v1.0.0",
    discovery_config_version="cfg_disc", timeframe="1D",
)


def build_stop_managed_exit_hypothesis_with_lane(
    lane: str, k: float = 2.0, r_multiple: Optional[float] = None, fraction: Optional[float] = None,
) -> ExitHypothesis:
    return ExitHypothesis(
        exit_family=ExitFamily.STOP_MANAGED_INVALIDATION.value, horizon_reference_point="ENTRY_BAR",
        exit_execution_policy="BAR_CLOSE", parameter_source=ParameterSource.AGENT_PROPOSED.value,
        invalidation_conditions=(InvalidationCondition(lane=lane, holds_labels=("HIGH", "VERY_HIGH")),),
        stop_loss=StopLossRule(basis="ATR_TRAILING_V1", atr_multiple=k),
        partial_profit=PartialProfitRule(r_multiple=r_multiple, fraction=fraction) if r_multiple is not None else None,
    )


def build_registered_mixed_family_hypothesis(
    registry: HypothesisRegistry, signature_id: str, time_exit_bars: int = 3,
    stop_managed_k: float = 2.0, signal_invalidation_max_holding_bars: int = 5,
    entry: Optional[EntryDefinition] = None,
    direction: str = Direction.LONG.value,
) -> dict[str, str]:
    """Registers one hypothesis with THREE materialized variants and
    returns `{"hypothesis_id": ..., "time_exit": vid, "stop_managed": vid,
    "signal_invalidation": vid}`."""
    entry = entry or EntryDefinition(core_conditions=(LaneStateCondition("volatility", "COMPRESSION"),))
    horizons = HorizonCandidateSet(unit="BARS", values=(time_exit_bars,), selection_basis="x", parameter_source=ParameterSource.PRE_SPECIFIED.value)
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
    stop_managed_exit = build_stop_managed_exit_hypothesis_with_lane("momentum", k=stop_managed_k)
    signal_invalidation_exit = build_signal_invalidation_exit_hypothesis(
        max_holding_bars=signal_invalidation_max_holding_bars,
        invalidation_conditions=(InvalidationCondition(lane="relative_strength", holds_labels=("HIGH", "VERY_HIGH")),),
    )
    variants = materialize_variants(hyp, signal_invalidation_exits=(stop_managed_exit, signal_invalidation_exit), created_at="t")
    hyp = dataclasses.replace(hyp, variant_ids=tuple(v.strategy_variant_id for v in variants))
    registry._force_register(hyp)
    for v in variants:
        registry.register_variant(v)

    by_family = {v.exit_hypothesis.exit_family: v.strategy_variant_id for v in variants}
    return {
        "hypothesis_id": hid,
        "time_exit": by_family[ExitFamily.TIME_EXIT.value],
        "stop_managed": by_family[ExitFamily.STOP_MANAGED_INVALIDATION.value],
        "signal_invalidation": by_family[ExitFamily.SIGNAL_INVALIDATION.value],
    }
