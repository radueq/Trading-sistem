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
"""
from __future__ import annotations

from evaluation.models.entities import EvidenceProfile

from hypothesis.config.loader import HypothesisConfig
from hypothesis.models.entities import ResearchQueueEntry

PRIORITY_BASIS_OUTCOME_AWARE = "DEVELOPMENT_OUTCOME_AWARE_SELECTION"
PRIORITY_BASIS_NOT_APPLICABLE = "NOT_APPLICABLE"


def eligibility_basis(profile: EvidenceProfile, eligibility_config: dict) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    eligible = True

    m = profile.missingness
    non_valid = m.insufficient_future_data + m.crosses_locked_oos + m.missing_benchmark + m.invalid_input
    total = m.episodes
    missingness_ratio = (non_valid / total) if total else 1.0
    max_ratio = eligibility_config["maximum_missingness_ratio"]
    ok = missingness_ratio <= max_ratio
    eligible = eligible and ok
    reasons.append(f"missingness_ratio={missingness_ratio:.4f} {'<=' if ok else '>'} maximum_missingness_ratio={max_ratio}")

    min_valid = eligibility_config["minimum_valid_episode_n"]
    ok = profile.support.valid_episode_n >= min_valid
    eligible = eligible and ok
    reasons.append(f"valid_episode_n={profile.support.valid_episode_n} {'>=' if ok else '<'} minimum_valid_episode_n={min_valid}")

    min_sec = eligibility_config["minimum_unique_securities"]
    ok = profile.concentration.unique_security_count >= min_sec
    eligible = eligible and ok
    reasons.append(f"unique_security_count={profile.concentration.unique_security_count} {'>=' if ok else '<'} minimum_unique_securities={min_sec}")

    if eligibility_config.get("require_stability_bins", True):
        ok = len(profile.stability) > 0
        eligible = eligible and ok
        reasons.append("stability bins present" if ok else "stability bins required but missing")

    return eligible, tuple(reasons)


def is_eligible_for_review(profile: EvidenceProfile, eligibility_config: dict) -> bool:
    eligible, _ = eligibility_basis(profile, eligibility_config)
    return eligible


def compute_review_priority(profile: EvidenceProfile) -> tuple[float, float, float]:
    """Ascending sort key -- smaller is higher priority. Explicitly
    outcome-aware (adjusted_p, standardized_effect, valid_episode_n);
    every caller MUST label the result with `PRIORITY_BASIS_OUTCOME_AWARE`
    (see `build_research_queue` below) rather than treat it as a neutral
    ordering."""
    adjusted_p = profile.baseline_comparison.adjusted_p
    effect = profile.baseline_comparison.standardized_effect
    p_key = adjusted_p if adjusted_p is not None else float("inf")
    effect_key = -abs(effect) if effect is not None else 0.0
    support_key = float(-profile.support.valid_episode_n)
    return (p_key, effect_key, support_key)


def build_research_queue(
    profiles: list[EvidenceProfile], evaluation_run_id: str, config: HypothesisConfig,
) -> tuple[ResearchQueueEntry, ...]:
    eligibility_config = config.data["research_queue_eligibility"]

    computed = []
    for p in profiles:
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
            evidence_horizon_bars=p.horizon_bars,
            evaluation_run_id=evaluation_run_id,
            eligible=eligible,
            eligibility_basis=basis,
            eligibility_config_version=config.config_version,
            review_priority_rank=rank_of_index.get(i),
            review_priority_key=key,
            priority_basis=PRIORITY_BASIS_OUTCOME_AWARE if key is not None else PRIORITY_BASIS_NOT_APPLICABLE,
        ))
    return tuple(entries)
