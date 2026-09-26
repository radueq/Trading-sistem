"""Spec #004 SS43/SS45-46 -- consensus computation.

Consensus is agreement on STRUCTURE among independent reviewers, never a
vote on truth (SS43: "2 agenti vote LONG" does not make LONG correct).
`compute_consensus` only classifies the shape of the reviews that
occurred; `can_preregister` is the ONE gate that matters for the
lifecycle -- consensus_status by itself can never move a proposal to
PREREGISTERED (TEST 30), only an explicit `HumanDecision(decision=
APPROVE, ...)` can (TEST 31/54), regardless of whether that decision
agrees with or overrides the agents' stances -- Radu remains final
approver (SS46).

PATCH #004-A finding #1 (GPT Review #004 Round 1): the original
`can_preregister()` treated ANY non-empty `human_decision` string as
approval -- "REJECT", "NU SUNT DE ACORD" and "NO" all passed the gate,
because non-emptiness was used as a boolean. `human_decision` is now a
structured `HumanDecision` whose `decision` field must literally equal
`HumanDecisionValue.APPROVE`; `REJECT` is an equally valid, explicitly
recorded outcome that `can_preregister()` correctly refuses.
"""
from __future__ import annotations

from hypothesis.models.entities import (
    AgentReview,
    AgentStance,
    ConsensusRecord,
    ConsensusStatus,
    HumanDecision,
    HumanDecisionValue,
)


def compute_consensus(
    proposal_id: str, reviews: tuple[AgentReview, ...], human_decision: HumanDecision | None = None,
) -> ConsensusRecord:
    objecting = [r for r in reviews if r.stance == AgentStance.OBJECT.value]
    supporting = [r for r in reviews if r.stance == AgentStance.SUPPORT.value]
    unresolved = tuple(o for r in objecting for o in r.objections)

    if not objecting:
        status = ConsensusStatus.CONSENSUS.value
    elif not supporting:
        status = ConsensusStatus.BLOCKED.value
    else:
        status = ConsensusStatus.DISAGREEMENT.value

    return ConsensusRecord(
        proposal_id=proposal_id,
        reviews=tuple(reviews),
        consensus_status=status,
        unresolved_objections=unresolved,
        human_decision=human_decision,
    )


def can_preregister(record: ConsensusRecord) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    if record.human_decision is None:
        errors.append(
            "human_decision is required before PREREGISTERED -- AI consensus, of any status, "
            "can never self-approve (SS46, TEST 30-31)"
        )
    elif record.human_decision.decision != HumanDecisionValue.APPROVE.value:
        errors.append(
            f"human_decision.decision={record.human_decision.decision!r} -- only an explicit "
            f"{HumanDecisionValue.APPROVE.value!r} may preregister; a REJECT (or any other value) "
            f"is a valid, final outcome that must NOT be treated as approval (PATCH #004-A finding #1, "
            f"TEST 54)"
        )
    return (not errors, tuple(errors))
