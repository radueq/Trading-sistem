"""TEST 41 -- Numeric validation: finite, strictly positive prices
(Spec #003 S1, Top Finding 16; GPT's decision, relayed by Radu,
authorized 2026-10-06 as Stage 1 of the joint #003+#004 remediation
plan; decision registry J1, revision 6).

A price that is PRESENT (not `None`) but zero, negative, `NaN`, or
infinite must never reach a division as if it were a real price -- it
routes to INVALID_INPUT instead, at all FOUR price positions: the
security's own entry price, its own exit price, the benchmark's own
entry price, and the benchmark's own exit price. `None` stays on its
own, existing, separate path (INVALID_INPUT for a missing entry bar
price, INSUFFICIENT_FUTURE_DATA for a missing exit bar price,
MISSING_BENCHMARK for an absent benchmark bar) -- this check never
folds `None` into itself.
"""
import math

import pytest

from evaluation.models.entities import OutcomeStatus
from evaluation.outcomes.benchmark import attach_benchmark_return
from evaluation.outcomes.forward_returns import compute_forward_outcome


class Bar:
    def __init__(self, date, close):
        self.date, self.split_adjusted_close = date, close


BAD_VALUES = [0.0, -5.0, math.nan, math.inf, -math.inf]
BAD_IDS = ["zero", "negative", "nan", "inf", "neg_inf"]


@pytest.mark.parametrize("bad_value", BAD_VALUES, ids=BAD_IDS)
def test_security_entry_price_invalid(bad_value):
    bars = [Bar("2024-01-02", bad_value), Bar("2024-01-03", 101.0)]
    o = compute_forward_outcome("sid", bars, "2024-01-02", "1D", 1, None, "cfg_x")
    assert o.outcome_status == OutcomeStatus.INVALID_INPUT.value
    assert o.forward_return is None
    assert o.entry_reference_price is None
    assert o.exit_reference_price is None


@pytest.mark.parametrize("bad_value", BAD_VALUES, ids=BAD_IDS)
def test_security_exit_price_invalid(bad_value):
    bars = [Bar("2024-01-02", 100.0), Bar("2024-01-03", bad_value)]
    o = compute_forward_outcome("sid", bars, "2024-01-02", "1D", 1, None, "cfg_x")
    assert o.outcome_status == OutcomeStatus.INVALID_INPUT.value
    assert o.forward_return is None
    assert o.entry_reference_price is None
    assert o.exit_reference_price is None


@pytest.mark.parametrize("bad_value", BAD_VALUES, ids=BAD_IDS)
def test_benchmark_entry_price_invalid(bad_value):
    bars = [Bar("2024-01-02", 100.0), Bar("2024-01-03", 110.0)]
    bench = [Bar("2024-01-02", bad_value), Bar("2024-01-03", 204.0)]
    o = compute_forward_outcome("sid", bars, "2024-01-02", "1D", 1, None, "cfg_x")
    assert o.outcome_status == OutcomeStatus.VALID.value  # security side unaffected
    ob = attach_benchmark_return(o, bench)
    assert ob.outcome_status == OutcomeStatus.INVALID_INPUT.value
    assert ob.benchmark_return is None
    assert ob.relative_return is None
    # The security's own already-valid forward_return is untouched by this rejection.
    assert ob.forward_return == pytest.approx(0.10, rel=1e-12)


@pytest.mark.parametrize("bad_value", BAD_VALUES, ids=BAD_IDS)
def test_benchmark_exit_price_invalid(bad_value):
    bars = [Bar("2024-01-02", 100.0), Bar("2024-01-03", 110.0)]
    bench = [Bar("2024-01-02", 200.0), Bar("2024-01-03", bad_value)]
    o = compute_forward_outcome("sid", bars, "2024-01-02", "1D", 1, None, "cfg_x")
    ob = attach_benchmark_return(o, bench)
    assert ob.outcome_status == OutcomeStatus.INVALID_INPUT.value
    assert ob.benchmark_return is None
    assert ob.relative_return is None
    assert ob.forward_return == pytest.approx(0.10, rel=1e-12)


def test_none_prices_stay_on_existing_distinct_path():
    """Corrected scope (decision registry J1): `None` must never be
    folded into the finite/positive check -- each position keeps its
    own existing, already-established status for a missing price."""
    bars_missing_entry = [Bar("2024-01-02", None), Bar("2024-01-03", 101.0)]
    o = compute_forward_outcome("sid", bars_missing_entry, "2024-01-02", "1D", 1, None, "cfg_x")
    assert o.outcome_status == OutcomeStatus.INVALID_INPUT.value

    bars_missing_exit = [Bar("2024-01-02", 100.0), Bar("2024-01-03", None)]
    o2 = compute_forward_outcome("sid", bars_missing_exit, "2024-01-02", "1D", 1, None, "cfg_x")
    assert o2.outcome_status == OutcomeStatus.INSUFFICIENT_FUTURE_DATA.value

    bars_ok = [Bar("2024-01-02", 100.0), Bar("2024-01-03", 110.0)]
    bench_missing_entry = [Bar("2024-01-02", None), Bar("2024-01-03", 204.0)]
    o3 = compute_forward_outcome("sid", bars_ok, "2024-01-02", "1D", 1, None, "cfg_x")
    ob3 = attach_benchmark_return(o3, bench_missing_entry)
    assert ob3.outcome_status == OutcomeStatus.MISSING_BENCHMARK.value

    bench_missing_exit = [Bar("2024-01-02", 200.0), Bar("2024-01-03", None)]
    o4 = compute_forward_outcome("sid", bars_ok, "2024-01-02", "1D", 1, None, "cfg_x")
    ob4 = attach_benchmark_return(o4, bench_missing_exit)
    assert ob4.outcome_status == OutcomeStatus.MISSING_BENCHMARK.value


def test_valid_path_unaffected():
    """Matches TEST 1/TEST 4's own existing assertions -- a regression
    here would mean the new check rejects legitimate prices, not only
    the bad ones it targets."""
    bars = [Bar("2024-01-02", 100.0), Bar("2024-01-03", 110.0)]
    bench = [Bar("2024-01-02", 200.0), Bar("2024-01-03", 204.0)]
    o = compute_forward_outcome("sid", bars, "2024-01-02", "1D", 1, None, "cfg_x")
    assert o.outcome_status == OutcomeStatus.VALID.value
    ob = attach_benchmark_return(o, bench)
    assert ob.outcome_status == OutcomeStatus.VALID.value
    assert ob.forward_return == pytest.approx(0.10, rel=1e-12)
    assert ob.benchmark_return == pytest.approx(0.02, rel=1e-12)
    assert ob.relative_return == pytest.approx(0.08, rel=1e-9)
