"""Spec #004 SS44 -- AgentReview ingestion/validation.

An AgentReview is a structured stance on ONE HypothesisProposal, never
executable logic and never the source of truth for approval (SS46) --
see consensus.py for how a set of reviews becomes a ConsensusRecord, and
why consensus alone can never preregister anything.
"""
from __future__ import annotations

from hypothesis.models.entities import AgentReview, AgentStance


def validate_review(review: AgentReview) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    valid_stances = {AgentStance.SUPPORT.value, AgentStance.OBJECT.value, AgentStance.ABSTAIN.value}
    if review.stance not in valid_stances:
        errors.append(f"stance {review.stance!r} is not a recognized AgentStance (TEST 29)")
    if review.stance == AgentStance.OBJECT.value and not review.objections:
        errors.append("stance=OBJECT requires at least one entry in objections[]")
    return (not errors, tuple(errors))


def collect_reviews(reviews: list[AgentReview], proposal_id: str) -> tuple[AgentReview, ...]:
    """Rejects reviews that don't belong to `proposal_id` and duplicate
    `agent_id`s for the same proposal (SS44 implies one stance per agent
    per proposal, not a moving target)."""
    seen_agents: set[str] = set()
    for r in reviews:
        if r.hypothesis_proposal_id != proposal_id:
            raise ValueError(f"review from agent_id={r.agent_id!r} targets proposal {r.hypothesis_proposal_id!r}, not {proposal_id!r}")
        ok, errors = validate_review(r)
        if not ok:
            raise ValueError(f"review from agent_id={r.agent_id!r} is invalid: {errors}")
        if r.agent_id in seen_agents:
            raise ValueError(f"duplicate review from agent_id={r.agent_id!r} for proposal {proposal_id!r}")
        seen_agents.add(r.agent_id)
    return tuple(reviews)
