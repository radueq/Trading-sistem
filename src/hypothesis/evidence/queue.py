"""Spec #004 SS56-62 -- Research Queue.

Two strictly separate concerns (Radu's SS110-H confirmation):

`is_eligible_for_review` / `eligibility_basis` use ONLY data-quality
fields (missingness, valid_episode_n, unique_security_count, presence of
stability bins) -- never `adjusted_p` or effect size. Thresholds live in
`config/hypothesis.yaml`'s `research_queue_eligibility` block and are
frozen/versioned BEFORE a queue run (`eligibility_config_version`), never
adjusted after seeing which signatures pass or fail (Radu's explicit
instruction).

`compute_review_priority` MAY use outcome-strength fields (adjusted_p,
standardized_effect, support) to order review attention -- but every
`ResearchQueueEntry` produced from it carries `priority_basis =
"DEVELOPMENT_OUTCOME_AWARE_SELECTION"` permanently (never silently), and
this module's output must never be imported by anything that builds a
`StrategyDefinition` (TEST 34 enforces this by field-name scan).

PATCH #004-A finding #4 (GPT Review #004 Round 1): the original design
took individual `EvidenceProfile`s and produced one `ResearchQueueEntry`
per (signature, horizon) -- meaning the SAME signature could occupy up
to 5 queue slots, and because priority was computed per-horizon from
that horizon's own outcome strength, whichever horizon happened to look
best would tend to rank first. No field named `selected_horizon` was
ever written anywhere, but operationally this was a backdoor form of
exactly the best-horizon selection Spec #004 exists to forbid (SS12/34).
Fixed: this module now consumes `EvidencePacket`s (already one per
signature, carrying the full decay curve for context, but with a single
policy-fixed `primary_*` reference point -- see `evidence/packet.py`) and
produces exactly ONE `ResearchQueueEntry` per signature, using ONLY that
same reference horizon for every signature uniformly.
"""
from __future__ import annotations

from hypothesis.config.loader import HypothesisConfig
from hypothesis.models.entities import EvidencePacket, ResearchQueueEntry

PRIORITY_BASIS_OUTCOME_AWARE = "DEVELOPMENT_OUTCOME_AWARE_SELECTION"
PRIORITY_BASIS_NOT_APPLICABLE = "NOT_APPLICABLE"


def eligibility_basis(packet: EvidencePacket, eligibility_config: dict) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    eligible = True

    missingness_ratio = packet.primary_missingness_ratio if packet.primary_missingness_ratio is not None else 1.0
    max_ratio = eligibility_config["maximum_missingness_ratio"]
    ok = missingness_ratio <= max_ratio
    eligible = eligible and ok
    reasons.append(f"missingness_ratio={missingness_ratio:.4f} {'<=' if ok else '>'} maximum_missingness_ratio={max_ratio}")

    min_valid = eligibility_config["minimum_valid_episode_n"]
    ok = packet.primary_valid_episode_n >= min_valid
    eligible = eligible and ok
    reasons.append(f"valid_episode_n={packet.primary_valid_episode_n} {'>=' if ok else '<'} minimum_valid_episode_n={min_valid}")

    min_sec = eligibility_config["minimum_unique_securities"]
    ok = packet.primary_unique_security_count >= min_sec
    eligible = eligible and ok
    reasons.append(f"unique_security_count={packet.primary_unique_security_count} {'>=' if ok else '<'} minimum_unique_securities={min_sec}")

    if eligibility_config.get("require_stability_bins", True):
        ok = packet.primary_has_stability_bins
        eligible = eligible and ok
        reasons.append("stability bins present" if ok else "stability bins required but missing")

    return eligible, tuple(reasons)


def is_eligible_for_review(packet: EvidencePacket, eligibility_config: dict) -> bool:
    eligible, _ = eligibility_basis(packet, eligibility_config)
    return eligible


def compute_review_priority(packet: EvidencePacket) -> tuple[float, float, float]:
    """Ascending sort key -- smaller is higher priority. Explicitly
    outcome-aware (adjusted_p, standardized_effect, valid_episode_n), ALL
    read from the packet's single policy-fixed reference horizon -- never
    from whichever horizon in the decay curve looks strongest. Every
    caller MUST label the result with `PRIORITY_BASIS_OUTCOME_AWARE` (see
    `build_research_queue` below) rather than treat it as neutral."""
    adjusted_p = packet.primary_adjusted_p
    effect = packet.primary_standardized_effect
    p_key = adjusted_p if adjusted_p is not None else float("inf")
    effect_key = -abs(effect) if effect is not None else 0.0
    support_key = float(-packet.primary_valid_episode_n)
    return (p_key, effect_key, support_key)


def build_research_queue(
    packets: list[EvidencePacket], config: HypothesisConfig,
) -> tuple[ResearchQueueEntry, ...]:
    """ONE entry per `EvidencePacket` (i.e. per signature) -- never per
    horizon. All packets must share the same `reference_horizon_bars`
    (they will, if all were built under the same `hypothesis_config`,
    since that's where the reference horizon comes from -- checked here
    defensively regardless)."""
    eligibility_config = config.data["research_queue_eligibility"]
    reference_horizon_bars = config.data["evidence_reference"]["reference_horizon_bars"]

    offenders = [p.signature_id for p in packets if p.primary_evidence_horizon_bars != reference_horizon_bars]
    if offenders:
        raise ValueError(
            f"packet(s) for {offenders!r} were not built at the configured reference_horizon_bars="
            f"{reference_horizon_bars!r} -- the Research Queue must compare every signature at the "
            f"SAME horizon (PATCH #004-A finding #4)"
        )

    computed = []
    for p in packets:
        eligible, basis = eligibility_basis(p, eligibility_config)
        key = compute_review_priority(p) if eligible else None
        computed.append((p, eligible, basis, key))

    eligible_indices = [i for i, c in enumerate(computed) if c[3] is not None]
    eligible_indices.sort(key=lambda i: computed[i][3])
    rank_of_index = {idx: rank + 1 for rank, idx in enumerate(eligible_indices)}

    entries = []
    for i, (p, eligible, basis, key) in enumerate(computed):
        entries.append(ResearchQueueEntry(
            signature_id=p.signature_id,
            reference_horizon_bars=p.primary_evidence_horizon_bars,
            evaluation_run_id=p.evidence_provenance.evaluation_run_id,
            eligible=eligible,
            eligibility_basis=basis,
            eligibility_config_version=config.config_version,
            review_priority_rank=rank_of_index.get(i),
            review_priority_key=key,
            priority_basis=PRIORITY_BASIS_OUTCOME_AWARE if key is not None else PRIORITY_BASIS_NOT_APPLICABLE,
        ))
    return tuple(entries)
