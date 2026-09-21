"""TEST 10 -- Missing history (Spec #002 SS38/SS30).

Insufficient observations -> explicit status, no silent calculation.
"""
from discovery.config.loader import load_config
from discovery.engine import run_discovery
from discovery.normalization.rolling_percentile import rolling_percentile
from spec002.fixtures.synthetic_universe import AS_OF


def test_insufficient_history_reported_explicitly():
    values = [float(i) for i in range(100)]  # only 100 of 252 required observations
    out = rolling_percentile(values, window=252, min_periods=252)
    assert all(p.value is None and p.status == "INSUFFICIENT_HISTORY" for p in out)


def test_insufficient_history_security_excluded_by_eligibility(conn, universe):
    from discovery.eligibility.engine import evaluate_eligibility

    config = load_config()
    sid = universe["named"]["INSUFFICIENT_HISTORY"]

    from data_foundation.pit import access as pit
    bars = pit.get_price_series_as_of(conn, sid, AS_OF)
    result = evaluate_eligibility(
        security_id=sid, as_of=AS_OF, latest_close=bars[-1].raw_close,
        history_days=len(bars), latest_adv_20=None, primary_exchange=None,
        config=config.eligibility,
    )
    assert result.eligible is False
    assert "MINIMUM_HISTORY" in result.failed_rules

    candidates = run_discovery(conn, [sid], AS_OF, universe["benchmark_security_id"], config)
    assert candidates == [], "a security failing minimum-history eligibility must not become a candidate"
