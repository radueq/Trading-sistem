"""TEST 24 -- Pre-budget observation isolation (PATCH #002-B, Radu's
decision, 2026-09-25, approving Spec #003's IMPLEMENTATION BLOCKER
§74A).

compute_discovery_observations() is the statistical dataset Spec #003's
Evaluation Engine must consume -- every ELIGIBLE security at `as_of`,
before Candidate Budget ever runs. Candidate Budget (`max_candidates`)
exists purely for downstream/LLM compute budget (Spec #002 SS21); it
must never be able to change what this pre-budget layer contains, or
the statistical dataset would silently depend on an operational
convenience parameter that has nothing to do with statistics. Spec
#003's own TEST 33 re-verifies this from the Evaluation Engine's
consuming side; this test verifies it at the source.
"""
import dataclasses

from discovery.config.loader import load_config
from discovery.engine import compute_discovery_observations, run_discovery
from fixtures.config_overrides import discovery_config_with_overrides
from spec002.fixtures.synthetic_universe import AS_OF


def _without_config_version(observations):
    return [dataclasses.replace(o, config_version=None) for o in observations]


def test_changing_max_candidates_does_not_change_pre_budget_observations(conn, universe):
    config = load_config()

    observations_default = compute_discovery_observations(
        conn, universe["non_benchmark_ids"], AS_OF, universe["benchmark_security_id"], config,
    )

    tiny_budget = dict(config.discovery)
    tiny_budget["candidate_budget"] = {"enabled": True, "max_candidates": 1}
    config_tiny_budget = discovery_config_with_overrides(discovery=tiny_budget)
    observations_tiny_budget = compute_discovery_observations(
        conn, universe["non_benchmark_ids"], AS_OF, universe["benchmark_security_id"], config_tiny_budget,
    )

    unbounded = dict(config.discovery)
    unbounded["candidate_budget"] = {"enabled": False, "max_candidates": 1}
    config_unbounded = discovery_config_with_overrides(discovery=unbounded)
    observations_unbounded = compute_discovery_observations(
        conn, universe["non_benchmark_ids"], AS_OF, universe["benchmark_security_id"], config_unbounded,
    )

    # Honest hashing (Stage 3, config identity infrastructure) means
    # config_tiny_budget/config_unbounded genuinely differ in
    # config_version from config (candidate_budget IS part of
    # discovery.yaml's own content) -- that label difference is
    # EXPECTED and asserted separately below; the actual claim this
    # test makes is that every OTHER field is untouched.
    assert _without_config_version(observations_default) == _without_config_version(observations_tiny_budget) == _without_config_version(observations_unbounded)
    assert observations_default[0].config_version == config.config_version
    assert observations_tiny_budget[0].config_version == config_tiny_budget.config_version
    assert config_tiny_budget.config_version != config.config_version != config_unbounded.config_version

    # sanity: the budget DOES bind on run_discovery()'s post-budget output,
    # so this isn't passing merely because the budget never mattered here
    candidates_default = run_discovery(
        conn, universe["non_benchmark_ids"], AS_OF, universe["benchmark_security_id"], config,
    )
    candidates_tiny_budget = run_discovery(
        conn, universe["non_benchmark_ids"], AS_OF, universe["benchmark_security_id"], config_tiny_budget,
    )
    assert len(candidates_tiny_budget) == 1
    assert len(candidates_default) > len(candidates_tiny_budget)
    assert len(observations_default) >= len(candidates_default), (
        "pre-budget observations must be at least as many as the post-budget candidate list"
    )
