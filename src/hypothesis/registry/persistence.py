"""Spec #004 PATCH #004-A finding #6 (GPT Review #004 Round 1) --
durable, append-only research audit trail.

`HypothesisRegistry` itself stays a pure in-memory index (fast, easy to
test, and unchanged by this module -- all 52+ pre-existing tests keep
constructing a bare `HypothesisRegistry()`). `JsonlAuditLog` is a thin
layer around it: every meaningful write (a proposal registered, a
proposal rejected, a preregistration committed -- hypothesis + every
variant together, PATCH #004-B finding #4) is ALSO appended as one JSON
line to a file -- `append()` never rewrites or truncates it -- so
"considered 40, rejected 37, preregistered 3" survives a process
restart, the way a Strategy Registry/research audit trail must, before
Spec #005 ever consumes it. Level 1 scope: a single append-only file,
not a database -- durable and auditable without a new infrastructure
dependency (Radu's own instruction: "nu cer baza de date sofisticata...
e suficient ceva simplu si auditable").
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from evaluation.models.entities import EvaluationRunRegistry

from hypothesis.consensus.consensus import can_preregister
from hypothesis.models.entities import (
    ConsensusRecord,
    EntryDefinition,
    EvidenceProvenance,
    ExitHypothesis,
    HorizonCandidateSet,
    HypothesisComplexitySnapshot,
    HypothesisProposal,
    HypothesisProvenance,
    InvalidationCondition,
    LaneStateCondition,
    ReasonCodeCondition,
    StrategyHypothesis,
    StrategyVariant,
)
from hypothesis.proposals.validator import ProposalValidationResult
from hypothesis.registry.hypotheses import HypothesisRegistry
from hypothesis.registry.preregistration import preregister_hypothesis

_TYPE_REGISTRY = {
    cls.__name__: cls for cls in (
        StrategyHypothesis, StrategyVariant, HypothesisProposal, EntryDefinition,
        LaneStateCondition, ReasonCodeCondition, HorizonCandidateSet, EvidenceProvenance,
        HypothesisProvenance, HypothesisComplexitySnapshot, ExitHypothesis, InvalidationCondition,
    )
}
_TUPLE_KEY = "__tuple__"
_TYPE_KEY = "__type__"


def to_jsonable(obj: Any) -> Any:
    """Recursively converts a frozen dataclass (and any nested
    dataclasses/tuples/dicts/lists it contains) into a plain JSON-
    serializable structure, tagging each dataclass instance with its
    class name so `from_jsonable()` can reconstruct the exact type.
    Generic over every entity in this package rather than one
    hand-written (de)serializer per class, which would silently drift
    out of sync as fields change. Plain-dict recursion (PATCH #004-B
    finding #4) lets a caller wrap several dataclasses in one plain
    dict payload (e.g. `{"hypothesis": ..., "variants": [...]}`) for a
    single atomic audit-log record, without needing its own dataclass."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {_TYPE_KEY: type(obj).__name__, **{
            f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)
        }}
    if isinstance(obj, tuple):
        return {_TUPLE_KEY: [to_jsonable(v) for v in obj]}
    if isinstance(obj, list):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    return obj


def from_jsonable(obj: Any) -> Any:
    if isinstance(obj, dict) and _TUPLE_KEY in obj:
        return tuple(from_jsonable(v) for v in obj[_TUPLE_KEY])
    if isinstance(obj, dict) and _TYPE_KEY in obj:
        cls = _TYPE_REGISTRY[obj[_TYPE_KEY]]
        kwargs = {k: from_jsonable(v) for k, v in obj.items() if k != _TYPE_KEY}
        return cls(**kwargs)
    if isinstance(obj, list):
        return [from_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: from_jsonable(v) for k, v in obj.items()}
    return obj


class JsonlAuditLog:
    """Append-only. `append()` only ever opens the file in append mode
    and writes one line; `replay()` reconstructs an equivalent
    `HypothesisRegistry` from scratch by re-applying every line in file
    order into a fresh in-memory registry."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def append(self, record_type: str, payload: Any) -> None:
        line = json.dumps({"record_type": record_type, "payload": to_jsonable(payload)}, sort_keys=True)
        with open(self.path, "a") as f:
            f.write(line + "\n")

    def replay(self) -> HypothesisRegistry:
        registry = HypothesisRegistry()
        if not self.path.exists():
            return registry
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                _apply(registry, record["record_type"], record["payload"])
        return registry


def _apply(registry: HypothesisRegistry, record_type: str, payload: Any) -> None:
    if record_type == "proposal_registered":
        registry.register_proposal(from_jsonable(payload))
    elif record_type == "proposal_rejected":
        registry.mark_proposal_rejected(payload["proposal_id"])
    elif record_type == "preregistration_committed":
        # PATCH #004-B finding #4 (GPT Review #004 Round 2): ONE record
        # carries the hypothesis AND every variant together, so replay
        # can never observe a hypothesis with only some of its variants
        # (or vice versa) -- see PersistentHypothesisRegistry.preregister()
        # below for why this must be a single append() call. Already
        # validated once (by preregister_hypothesis()) before it was ever
        # appended -- replay reconstructs the same fact, it does not
        # re-derive it, so it bypasses register()'s PREREGISTERED guard
        # via _force_register() the same way the original insert did.
        committed = from_jsonable(payload)
        registry._force_register(committed["hypothesis"])
        for v in committed["variants"]:
            registry.register_variant(v)
    else:
        raise ValueError(f"unknown audit record_type {record_type!r}")


class PersistentHypothesisRegistry:
    """Composes a `HypothesisRegistry` with a `JsonlAuditLog`. The plain
    registry stays exactly the in-memory index every pre-existing test
    relies on; this wrapper is what production code (and Spec #005, once
    it consumes the registry) should use so research history survives a
    process restart."""

    def __init__(self, registry: HypothesisRegistry, audit_log: JsonlAuditLog):
        self.registry = registry
        self.audit_log = audit_log

    @classmethod
    def open(cls, path: Path | str) -> "PersistentHypothesisRegistry":
        log = JsonlAuditLog(path)
        return cls(registry=log.replay(), audit_log=log)

    def register_proposal(self, proposal: HypothesisProposal) -> HypothesisProposal:
        self.registry.register_proposal(proposal)
        self.audit_log.append("proposal_registered", proposal)
        return proposal

    def mark_proposal_rejected(self, proposal_id: str) -> None:
        self.registry.mark_proposal_rejected(proposal_id)
        self.audit_log.append("proposal_rejected", {"proposal_id": proposal_id})

    def preregister(
        self,
        draft: StrategyHypothesis,
        variants: tuple[StrategyVariant, ...],
        *,
        proposal: HypothesisProposal,
        proposal_validation: ProposalValidationResult,
        consensus: ConsensusRecord,
        run_registry: EvaluationRunRegistry,
        hypothesis_config: dict,
    ) -> StrategyHypothesis:
        """Runs the exact same atomic gate as `registry.preregistration.
        preregister_hypothesis()` (against `self.registry`), then appends
        the resulting hypothesis AND every variant as ONE JSONL record.

        PATCH #004-B finding #4 (GPT Review #004 Round 2): the original
        version wrote one `hypothesis_preregistered` line followed by N
        separate `variant_registered` lines -- if the process or disk
        died between those appends (or between the in-memory registry
        write and the first append), the in-memory state and the
        persisted log could diverge: a hypothesis with only some of its
        variants durable, or none at all. A single `preregistration_
        committed` record (`{"hypothesis": ..., "variants": [...]}`)
        makes the durable write atomic at the file-line level: on
        replay, the hypothesis and ALL of its variants appear together,
        or the line is simply not there yet -- never a partial state."""
        frozen = preregister_hypothesis(
            draft, variants, proposal=proposal, proposal_validation=proposal_validation, consensus=consensus,
            registry=self.registry, run_registry=run_registry, hypothesis_config=hypothesis_config,
        )
        self.audit_log.append("preregistration_committed", {"hypothesis": frozen, "variants": list(variants)})
        return frozen
