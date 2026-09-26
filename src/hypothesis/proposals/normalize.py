"""Spec #004 SS36-37/SS93 -- ingesting a structured proposal.

`normalize_proposal` turns a plain dict (as typed by Radu, pasted from a
manual GPT/Claude relay -- exactly how this project already operates --
or later produced by an automated adapter) into a `HypothesisProposal`.
This module is SHAPE/TYPE coercion only: it does not check vocabulary,
complexity budget, or policy values -- that is `proposals/validator.py`'s
job, kept deliberately separate so the two failure modes (malformed
JSON vs. a well-formed but non-compliant proposal) are never conflated.
The core never cares which agent/model produced the dict (SS110-G) --
no LLM adapter is called from here or anywhere in this package.
"""
from __future__ import annotations

from typing import Any

from hypothesis.models.entities import (
    EntryDefinition,
    EvidenceProvenance,
    ExitHypothesis,
    HorizonCandidateSet,
    HypothesisProposal,
    InvalidationCondition,
    LaneStateCondition,
    ReasonCodeCondition,
)


def _require(raw: dict, key: str) -> Any:
    if key not in raw:
        raise ValueError(f"proposal is missing required field {key!r}")
    return raw[key]


def _normalize_condition(raw: dict) -> "LaneStateCondition | ReasonCodeCondition":
    if "lane" in raw:
        return LaneStateCondition(lane=raw["lane"], label=raw["label"], negate=bool(raw.get("negate", False)))
    if "reason_code" in raw:
        return ReasonCodeCondition(reason_code=raw["reason_code"], negate=bool(raw.get("negate", False)))
    raise ValueError(f"condition must have either 'lane' or 'reason_code': {raw!r}")


def _normalize_entry_definition(raw: dict) -> EntryDefinition:
    return EntryDefinition(
        core_conditions=tuple(_normalize_condition(c) for c in raw.get("core_conditions", ())),
        confirmation_conditions=tuple(_normalize_condition(c) for c in raw.get("confirmation_conditions", ())),
    )


def _normalize_invalidation(raw: dict) -> InvalidationCondition:
    return InvalidationCondition(
        lane=raw.get("lane"),
        holds_labels=tuple(raw["holds_labels"]) if raw.get("holds_labels") else None,
        reason_code=raw.get("reason_code"),
        triggers_on_presence=raw.get("triggers_on_presence"),
    )


def _normalize_exit_hypothesis(raw: dict) -> ExitHypothesis:
    return ExitHypothesis(
        exit_family=_require(raw, "exit_family"),
        horizon_reference_point=_require(raw, "horizon_reference_point"),
        exit_execution_policy=_require(raw, "exit_execution_policy"),
        parameter_source=_require(raw, "parameter_source"),
        time_exit_bars=raw.get("time_exit_bars"),
        invalidation_conditions=tuple(_normalize_invalidation(c) for c in raw.get("invalidation_conditions", ())),
        max_holding_bars=raw.get("max_holding_bars"),
    )


def _normalize_horizon_candidates(raw: dict) -> HorizonCandidateSet:
    return HorizonCandidateSet(
        unit=_require(raw, "unit"),
        values=tuple(_require(raw, "values")),
        selection_basis=raw.get("selection_basis", ""),
        parameter_source=_require(raw, "parameter_source"),
    )


def _normalize_evidence_provenance(raw: dict) -> EvidenceProvenance:
    return EvidenceProvenance(
        evaluation_run_id=_require(raw, "evaluation_run_id"),
        evaluation_engine_version=_require(raw, "evaluation_engine_version"),
        evaluation_config_version=_require(raw, "evaluation_config_version"),
        signature_id=_require(raw, "signature_id"),
        signature_set_id=_require(raw, "signature_set_id"),
        discovery_engine_version=_require(raw, "discovery_engine_version"),
        discovery_config_version=_require(raw, "discovery_config_version"),
        timeframe=_require(raw, "timeframe"),
    )


def normalize_proposal(raw: dict) -> HypothesisProposal:
    return HypothesisProposal(
        proposal_id=_require(raw, "proposal_id"),
        source_evidence=_normalize_evidence_provenance(_require(raw, "source_evidence")),
        direction=_require(raw, "direction"),
        direction_basis=_require(raw, "direction_basis"),
        entry_definition=_normalize_entry_definition(_require(raw, "entry_definition")),
        entry_execution_policy=_require(raw, "entry_execution_policy"),
        horizon_candidates=_normalize_horizon_candidates(_require(raw, "horizon_candidates")),
        exit_hypotheses=tuple(_normalize_exit_hypothesis(e) for e in raw.get("exit_hypotheses", ())),
        facts_from_evidence=tuple(raw.get("facts_from_evidence", ())),
        interpretation=raw.get("interpretation", ""),
        counterarguments=tuple(raw.get("counterarguments", ())),
        known_failure_modes=tuple(raw.get("known_failure_modes", ())),
        proposer=_require(raw, "proposer"),
        created_at=_require(raw, "created_at"),
    )
