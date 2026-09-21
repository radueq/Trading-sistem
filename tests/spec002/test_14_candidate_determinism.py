"""TEST 14 -- Candidate determinism (Spec #002 SS38/SS22/SS34).

Same universe -> same candidates AND same order, every run.
"""
from discovery.config.loader import load_config
from discovery.engine import run_discovery
from spec002.fixtures.synthetic_universe import AS_OF


def test_candidate_determinism(conn, universe):
    config = load_config()
    sids = universe["non_benchmark_ids"]
    bench = universe["benchmark_security_id"]

    run1 = run_discovery(conn, sids, AS_OF, bench, config)
    run2 = run_discovery(conn, sids, AS_OF, bench, config)

    assert [c.security_id for c in run1] == [c.security_id for c in run2]
    assert run1 == run2
