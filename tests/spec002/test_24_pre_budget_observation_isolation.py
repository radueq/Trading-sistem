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
from dataclasses import replace

from discovery.config.loader import load_config
from discovery.engine import compute_discovery_observations, run_discovery
from spec002.fixtures.synthetic_universe import AS_OF


def test_changing_max_candidates_does_not_change_pre_budget_observations(conn, universe):
    config = load_config()

    observations_default = compute_discovery_observations(
        conn, universe["non_benchmark_ids"], AS_OF, universe["benchmark_security_id"], config,
    )

    tiny_budget = dict(config.discovery)
    tiny_budget["candidate_budget"] = {"enabled": True, "max_candidates": 1}
    config_tiny_budget = replace(config, discovery=tiny_budget)
    observations_tiny_budget = compute_discovery_observations(
        conn, universe["non_benchmark_ids"], AS_OF, universe["benchmark_security_id"], config_tiny_budget,
    )

    unbounded = dict(config.discovery)
    unbounded["candidate_budget"] = {"enabled": False, "max_candidates": 1}
    config_unbounded = replace(config, discovery=unbounded)
    observations_unbounded = compute_discovery_observations(
        conn, universe["non_benchmark_ids"], AS_OF, universe["benchmark_security_id"], config_unbounded,
    )

    assert observations_default == observations_tiny_budget == observations_unbounded

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
