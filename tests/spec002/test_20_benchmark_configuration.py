"""TEST 20 -- Benchmark configuration (Spec #002 SS38/SS10/SS32).

Changing benchmark changes RS through config/data, not code
modification -- no ticker string is hardcoded anywhere in the RS lane.
"""
import inspect

from discovery.config.loader import load_config
from discovery.engine import run_discovery
from discovery.features import relative_strength
from spec002.fixtures.synthetic_universe import AS_OF


def test_no_hardcoded_benchmark_ticker_in_rs_module():
    source = inspect.getsource(relative_strength)
    for forbidden_ticker in ("SPY", "spy"):
        assert forbidden_ticker not in source


def test_changing_benchmark_security_changes_rs_output(conn, universe):
    config = load_config()
    sid = universe["named"]["TREND_UP"]

    against_benchmark = run_discovery(conn, [sid], AS_OF, universe["benchmark_security_id"], config)[0]
    against_self = run_discovery(conn, [sid], AS_OF, sid, config)[0]

    assert (
        against_benchmark.feature_vector["relative_return_63d"]
        != against_self.feature_vector["relative_return_63d"]
    )
    # against itself as its own benchmark, relative return must be exactly 0
    assert abs(against_self.feature_vector["relative_return_63d"]) < 1e-9
