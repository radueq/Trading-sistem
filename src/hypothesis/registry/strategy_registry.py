"""Spec #004 SS63-67 -- StrategyDefinition assembly.

A StrategyDefinition is the terminal, tradeable artifact for ONE
StrategyVariant -- produced only once its parent StrategyHypothesis is
PREREGISTERED and the variant was one of the ones eagerly materialized at
that same freeze time (never a variant #005 invented afterward, SS106-109).
`universe_policy` is never a static ticker list (SS64-65 -- no cherry-
picking after seeing outcomes); it names Discovery's own eligibility
mechanism, preserving PIT discipline all the way through.
"""
from __future__ import annotations

import hashlib

from hypothesis.models.entities import HypothesisStatus, StrategyDefinition, StrategyHypothesis, StrategyVariant

UNIVERSE_POLICY = "DISCOVERY_ELIGIBLE_UNIVERSE"


def build_strategy_id(hypothesis_id: str, strategy_variant_id: str) -> str:
    digest = hashlib.sha256(f"{hypothesis_id}::{strategy_variant_id}".encode()).hexdigest()[:16]
    return f"strat_{digest}"


def build_strategy_definition(
    hypothesis: StrategyHypothesis, variant: StrategyVariant, market: str = "US_EQUITIES",
) -> StrategyDefinition:
    if hypothesis.status != HypothesisStatus.PREREGISTERED.value:
        raise ValueError(
            f"hypothesis {hypothesis.hypothesis_id!r} is not PREREGISTERED (status={hypothesis.status!r}) -- "
            f"a StrategyDefinition can only be built from a frozen, approved hypothesis (SS63)"
        )
    if variant.parent_hypothesis_id != hypothesis.hypothesis_id:
        raise ValueError(
            f"variant {variant.strategy_variant_id!r} belongs to hypothesis "
            f"{variant.parent_hypothesis_id!r}, not {hypothesis.hypothesis_id!r}"
        )
    if variant.strategy_variant_id not in hypothesis.variant_ids:
        raise ValueError(
            f"variant {variant.strategy_variant_id!r} was not eagerly materialized on hypothesis "
            f"{hypothesis.hypothesis_id!r} at freeze time -- #005 must never test an un-registered "
            f"variant (SS104-109)"
        )

    return StrategyDefinition(
        strategy_id=build_strategy_id(hypothesis.hypothesis_id, variant.strategy_variant_id),
        hypothesis_id=hypothesis.hypothesis_id,
        strategy_variant_id=variant.strategy_variant_id,
        market=market,
        timeframe=hypothesis.evidence_provenance.timeframe,
        universe_policy=UNIVERSE_POLICY,
        direction=hypothesis.direction,
        signal_definition=hypothesis.entry_definition,
        entry_execution_policy=hypothesis.entry_execution_policy,
        exit_definition=variant.exit_hypothesis,
        status=HypothesisStatus.PREREGISTERED.value,
    )
