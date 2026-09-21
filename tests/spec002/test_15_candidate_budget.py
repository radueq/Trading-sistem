"""TEST 15 -- Candidate Budget (Spec #002 SS38/SS22).

Large synthetic candidate set -> configured budget respected.
"""
from discovery.config.loader import load_config
from discovery.engine import run_discovery
from spec002.fixtures.synthetic_universe import AS_OF


def test_candidate_budget_respected(conn, universe):
    config = load_config()
    candidates = run_discovery(
        conn, universe["non_benchmark_ids"], AS_OF, universe["benchmark_security_id"], config,
    )
    max_candidates = config.discovery["candidate_budget"]["max_candidates"]
    assert len(candidates) <= max_candidates
    # sanity: the synthetic universe has more eligible securities than
    # the budget, so the budget must actually bind (not just happen to
    # produce fewer than max_candidates)
    assert len(candidates) == max_candidates


def test_candidate_budget_disabled_returns_everything(conn, universe):
    config = load_config()
    unbounded = dict(config.discovery)
    unbounded["candidate_budget"] = {"enabled": False, "max_candidates": 1}
    from dataclasses import replace
    config_unbounded = replace(config, discovery=unbounded)

    candidates = run_discovery(
        conn, universe["non_benchmark_ids"], AS_OF, universe["benchmark_security_id"], config_unbounded,
    )
    assert len(candidates) > 1
