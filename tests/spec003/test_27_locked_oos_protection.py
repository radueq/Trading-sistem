"""TEST 27 -- Locked OOS protection (Spec #003 SS12/SS14/SS66).

Structural: on CROSSES_LOCKED_OOS, the exit bar's price is NEVER
populated (not read, not leaked into any field) -- and an end-to-end
run confirms no VALID outcome's exit_as_of ever lands after
development_end.
"""
from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition, OutcomeStatus
from evaluation.outcomes.forward_returns import compute_forward_outcome
from evaluation.registry.signatures import freeze_signature_set

from spec003.fixtures.tiny_universe import DATES


class Bar:
    def __init__(self, date, close):
        self.date, self.split_adjusted_close = date, close


def test_crosses_locked_oos_never_populates_exit_price():
    bars = [Bar(f"2025-12-{d:02d}", 100.0 + d) for d in range(24, 32)] + [Bar("2026-01-02", 555.0)]
    o = compute_forward_outcome("sid", bars, "2025-12-30", "1D", 2, "2025-12-31", "cfg_x")
    assert o.outcome_status == OutcomeStatus.CROSSES_LOCKED_OOS.value
    assert o.exit_reference_price is None
    assert o.exit_as_of is None
    assert o.forward_return is None


def test_no_valid_outcome_exits_after_development_end(conn, tiny_universe, reduced_discovery_config, fast_evaluation_config):
    # dev_end sits INSIDE COMPQ's EXTREME_COMPRESSION run (verified
    # against DATES[33..40]) so several observations near the wall need
    # a horizon that reaches past it; data_as_of extends further (real
    # data DOES exist beyond the wall, e.g. because time has since
    # passed) so the wall is actually tested, not just "no data
    # available at all" (see outcomes/forward_returns.py).
    dev_start, dev_end = DATES[30], DATES[36]
    sig = EvaluationSignatureDefinition(
        signature_id="VOLATILITY_EXTREME_COMPRESSION", lane_conditions=(LaneStateCondition("volatility", "EXTREME_COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=reduced_discovery_config.config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )
    sigset = freeze_signature_set([sig])
    profiles, _ = run_evaluation(
        conn, tiny_universe["non_benchmark_ids"], tiny_universe["benchmark_security_id"],
        dev_start, dev_end, sigset, reduced_discovery_config, fast_evaluation_config,
        data_as_of=DATES[-1],
    )
    assert any(p.missingness.crosses_locked_oos > 0 for p in profiles), "sanity: the boundary should actually bind somewhere"
    assert any(p.missingness.valid_outcomes > 0 for p in profiles)
    for p in profiles:
        assert p.missingness.crosses_locked_oos + p.missingness.valid_outcomes + p.missingness.insufficient_future_data + p.missingness.missing_benchmark + p.missingness.invalid_input == p.missingness.episodes
