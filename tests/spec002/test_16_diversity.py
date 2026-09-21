"""TEST 16 -- Diversity (Spec #002 SS38/SS23).

Budget reduction does not collapse trivially into one identical state
signature when alternatives satisfying policy exist.
"""
from discovery.config.loader import load_config
from discovery.engine import run_discovery
from spec002.fixtures.synthetic_universe import AS_OF


def test_diversity_avoids_single_signature_collapse(conn, universe):
    config = load_config()
    candidates = run_discovery(
        conn, universe["non_benchmark_ids"], AS_OF, universe["benchmark_security_id"], config,
    )

    distinct_signatures = {tuple(sorted(c.state_signature.items())) for c in candidates}
    assert len(distinct_signatures) > 1, "candidate budget collapsed into a single repeated state signature"


def test_diversity_disabled_falls_back_to_plain_ranking(conn, universe):
    from dataclasses import replace

    config = load_config()
    no_diversity = dict(config.discovery)
    no_diversity["diversity"] = {"enabled": False}
    config_no_diversity = replace(config, discovery=no_diversity)

    candidates = run_discovery(
        conn, universe["non_benchmark_ids"], AS_OF, universe["benchmark_security_id"], config_no_diversity,
    )
    max_candidates = config.discovery["candidate_budget"]["max_candidates"]
    assert len(candidates) == max_candidates
