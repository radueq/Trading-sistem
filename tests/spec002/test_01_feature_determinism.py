"""TEST 1 -- Feature determinism (Spec #002 SS38/SS34).

Identical data/config/software version -> identical Feature/Discovery
output, every run. No randomness anywhere in this pipeline (Spec #002
SS34).
"""
from discovery.config.loader import load_config
from discovery.engine import run_discovery
from spec002.fixtures.synthetic_universe import AS_OF


def test_feature_determinism(conn, universe):
    config = load_config()
    sids = universe["non_benchmark_ids"]
    bench = universe["benchmark_security_id"]

    run1 = run_discovery(conn, sids, AS_OF, bench, config)
    run2 = run_discovery(conn, sids, AS_OF, bench, config)

    assert run1 == run2
