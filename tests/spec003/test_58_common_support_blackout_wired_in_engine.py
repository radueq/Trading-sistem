"""TEST 58 -- F3 common support blackout, WIRED into the real engine
(joint remediation design 003+004 section 3-6; decision registry A1,
Stage 4).

TEST 54 proves the detection LOGIC in isolation and that a
hand-built `None` set propagates safely downstream. This test closes
that gap: it calls the REAL, private `_evaluate_signature_horizon()`
(the actual production code path, not a reimplementation) with a
hand-built signature that has real episodes in TWO temporal bins, and
a hand-built `baseline_pool_h` that only has data in ONE of them --
proving the engine's OWN gate actually fires, not just that the
concept is sound. Verification discipline: this exact scenario was
used to confirm the gate catches a regression (temporarily forcing
`full_common_support = True` in engine.py made this test -- and
nothing else in the full suite -- fail) before being restored and
locked here.
"""
from datetime import date, timedelta

from evaluation.baseline.universe import partition_temporal_bins
from evaluation.config.loader import load_config as load_evaluation_config
from evaluation.engine import _evaluate_signature_horizon
from evaluation.models.entities import (
    EvaluationSignatureDefinition, ForwardOutcome, LaneStateCondition, OutcomeStatus,
)


class Bar:
    def __init__(self, d, close):
        self.date, self.split_adjusted_close = d, close


def _dense_bars(start: str, end: str, base_price=100.0):
    """Every calendar day from start to end inclusive -- DENSE, not
    sparse, because build_episodes() measures gaps in the security's
    own bar-INDEX positions, never calendar days (engine.py's own
    documented convention). A sparse bar list would make two
    far-apart calendar dates look only a few bars apart, silently
    merging them into ONE episode instead of the two this scenario
    needs."""
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    n = (e - s).days + 1
    return [Bar((s + timedelta(days=i)).isoformat(), base_price + i * 0.01) for i in range(n)]


def _fake_outcome(sid, as_of, relative_return, status=OutcomeStatus.VALID.value):
    return ForwardOutcome(
        security_id=sid, observation_as_of=as_of, timeframe="1D", horizon_bars=1,
        entry_reference_price=100.0, exit_reference_price=101.0, exit_as_of=as_of,
        forward_return=0.01, benchmark_return=0.0, relative_return=relative_return,
        outcome_status=status, development_end=None,
        outcome_engine_version="v1.0.0", config_version="cfg_x",
    )


def test_partial_common_support_blacks_out_comparison_fields_via_the_real_engine():
    bins = partition_temporal_bins("2024-01-01", "2024-12-31", 2)
    early, late = bins[0], bins[1]
    early_date, late_date = early.start_date, late.start_date

    bars = _dense_bars(early_date, (date.fromisoformat(late_date) + timedelta(days=1)).isoformat())
    bars_by_security = {"SIG_SEC": bars}
    benchmark_bars = _dense_bars(early_date, (date.fromisoformat(late_date) + timedelta(days=1)).isoformat())
    raw_matches_by_security = {"SIG_SEC": [early_date, late_date]}

    # Baseline pool: ONLY early-bin data -- the signature has real
    # weight in BOTH bins, but the baseline has nothing in "late".
    baseline_pool_h = [
        ("OTHER_SEC", early_date, _fake_outcome("OTHER_SEC", early_date, 0.001)),
    ]

    ev_config = load_evaluation_config()
    profile = _evaluate_signature_horizon(
        signature=EvaluationSignatureDefinition(
            signature_id="SIG", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
            reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
            discovery_config_version="cfg_x", creation_mode="PRE_REGISTERED", created_before_outcome_evaluation=True,
        ),
        horizon_bars=1, timeframe="1D", raw_matches_by_security=raw_matches_by_security,
        bars_by_security=bars_by_security, benchmark_bars=benchmark_bars, development_end=None,
        config_version="cfg_x", baseline_pool_h=baseline_pool_h, bins=bins,
        session_dates=[b.date for b in bars_by_security["SIG_SEC"]],
        ev_config=ev_config, run_id="run_x", mode="EXPLORATORY",
    )

    assert profile.support.valid_episode_n == 2, "sanity: both episodes must have produced a VALID outcome, not merged into one"
    bc = profile.baseline_comparison
    assert bc.mean_difference is None
    assert bc.median_difference is None
    assert bc.raw_p is None
    assert bc.mean_difference_ci is None
    assert bc.standardized_effect is None
    # baseline_mean itself is NOT blacked out -- it reflects whatever
    # bin(s) the baseline pool actually has data in (early only here).
    assert bc.baseline_mean is not None
    # the signature's own full-population descriptive stats are untouched.
    assert profile.relative_outcome.n == 2
    assert profile.relative_outcome.mean is not None


def test_full_common_support_does_not_black_out_comparison_fields():
    # Sanity counterpart: the SAME two-episode signature, but the
    # baseline pool now has data in BOTH bins -- comparison fields
    # must NOT be blacked out.
    bins = partition_temporal_bins("2024-01-01", "2024-12-31", 2)
    early, late = bins[0], bins[1]
    early_date, late_date = early.start_date, late.start_date

    bars = _dense_bars(early_date, (date.fromisoformat(late_date) + timedelta(days=1)).isoformat())
    bars_by_security = {"SIG_SEC": bars}
    benchmark_bars = _dense_bars(early_date, (date.fromisoformat(late_date) + timedelta(days=1)).isoformat())
    raw_matches_by_security = {"SIG_SEC": [early_date, late_date]}

    baseline_pool_h = [
        ("OTHER_SEC", early_date, _fake_outcome("OTHER_SEC", early_date, 0.001)),
        ("OTHER_SEC_2", late_date, _fake_outcome("OTHER_SEC_2", late_date, 0.002)),
    ]

    ev_config = load_evaluation_config()
    profile = _evaluate_signature_horizon(
        signature=EvaluationSignatureDefinition(
            signature_id="SIG", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
            reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
            discovery_config_version="cfg_x", creation_mode="PRE_REGISTERED", created_before_outcome_evaluation=True,
        ),
        horizon_bars=1, timeframe="1D", raw_matches_by_security=raw_matches_by_security,
        bars_by_security=bars_by_security, benchmark_bars=benchmark_bars, development_end=None,
        config_version="cfg_x", baseline_pool_h=baseline_pool_h, bins=bins,
        session_dates=[b.date for b in bars_by_security["SIG_SEC"]],
        ev_config=ev_config, run_id="run_x", mode="EXPLORATORY",
    )

    assert profile.support.valid_episode_n == 2
    bc = profile.baseline_comparison
    assert bc.mean_difference is not None
    assert bc.median_difference is not None
    assert bc.standardized_effect is not None or bc.standardized_effect_status == "UNDEFINED_ZERO_SCALE"
