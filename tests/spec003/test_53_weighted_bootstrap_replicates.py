"""TEST 53 -- per-replicate weighted bootstrap estimator, round 2
correction (joint remediation design 003+004 section 6; decision
registry A1/A4, Stage 4 -- GPT's CHANGES REQUIRED verdict on commit
`74dc218`).

Round 1 (commit `74dc218`) reused `time_block_bootstrap_replicates()`'s
own "silently drop an empty-composition iteration" behavior across
per-bin lists that later get combined BY POSITION -- an empty
iteration in one bin's list shifts every LATER iteration's position in
that bin's own list, so index `r` stops identifying the SAME iteration
across bins once combined. GPT reproduced this exactly (two bins,
`block_length_bars=1`, 8 iterations, seed 0) and separately found that
the signature side's bootstrap was one flat, bin-blind resample, so a
bin's baseline-side exclusion in a given replica was never mirrored on
the signature side -- A1's own blackout covers the ORIGINAL population
only, not a transient per-replica support gap.

Fixed: `time_block_bootstrap_replicates(..., keep_empty_as_none=True)`
never compacts -- every per-bin list is exactly `iterations` long,
`None` at an empty iteration. `common_support_difference_replicates()`
combines signature-by-bin and baseline-by-bin per ITERATION, excluding
a bin from BOTH sides whenever EITHER side is `None` at that index.
"""
import pytest

from evaluation.statistics.bootstrap import (
    common_support_difference_replicates, percentile_ci, signature_bootstrap_replicates_by_bin,
    stratified_baseline_replicates_by_bin, time_block_bootstrap_replicates, weighted_mean_by_security,
)


def test_weighted_mean_by_security_equalizes_per_security_contribution():
    rows = [("A", 0.0), ("A", 1.0), ("A", 2.0), ("B", 100.0)]
    result = weighted_mean_by_security(rows)
    assert result == pytest.approx(1.0 * 0.5 + 100.0 * 0.5)
    plain_mean = sum(v for _, v in rows) / len(rows)
    assert result != pytest.approx(plain_mean)


def test_weighted_mean_by_security_empty_returns_none():
    assert weighted_mean_by_security([]) is None


def test_keep_empty_as_none_preserves_iteration_identity_and_length():
    # block_length_bars=1 over 2 sessions, ONE observation (on session
    # 1 only) -- some replicates MUST land on session 2 only, making
    # the resampled composition empty for that iteration.
    dated = [("2024-01-01", 0.0)]
    session_dates = ["2024-01-01", "2024-01-02"]
    reps = time_block_bootstrap_replicates(
        dated, session_dates, block_length_bars=1, iterations=8, seed=0, keep_empty_as_none=True,
    )
    assert len(reps) == 8
    assert None in reps, "sanity: at least one of 8 replicates must have landed on session-2-only"
    without_flag = time_block_bootstrap_replicates(dated, session_dates, block_length_bars=1, iterations=8, seed=0)
    assert len(without_flag) < 8, "default behavior (keep_empty_as_none=False) must be UNCHANGED -- still compacts"
    assert [r for r in reps if r is not None] == without_flag


def test_gpt_exact_reproduction_bin_a_bin_b_eight_iterations_seed_zero():
    # GPT's own exact fixture: bin "A" has a single observation (value
    # 0) on session 1 of 2; bin "B" has 100 on session 1 and 200 on
    # session 2. block_length_bars=1, 8 iterations, base seed 0,
    # weights 0.5/0.5 -- sorted(["A","B"]) gives offsets A=0, B=1.
    session_dates = ["2024-01-01", "2024-01-02"]
    rep_a = time_block_bootstrap_replicates(
        [("2024-01-01", 0.0)], session_dates, block_length_bars=1, iterations=8, seed=0, keep_empty_as_none=True,
    )
    rep_b = time_block_bootstrap_replicates(
        [("2024-01-01", 100.0), ("2024-01-02", 200.0)], session_dates, block_length_bars=1, iterations=8, seed=1, keep_empty_as_none=True,
    )
    assert rep_a == [None, 0.0, None, None, 0.0, 0.0, 0.0, 0.0]
    assert rep_b == [100.0, 150.0, 200.0, 200.0, 100.0, 150.0, 200.0, 150.0]

    # Isolate the CROSS-BIN (Problem 1) combine specifically: hold the
    # "signature" side always-available (all zero) so
    # common_support_difference_replicates() reduces to a pure
    # baseline-only cross-bin combine, matching what
    # stratified_baseline_replicates_by_bin()'s own combine must do.
    always_available = {"A": [0.0] * 8, "B": [0.0] * 8}
    baseline_by_bin = {"A": rep_a, "B": rep_b}
    weights = {"A": 0.5, "B": 0.5}
    diffs = common_support_difference_replicates(always_available, baseline_by_bin, weights, 8)
    combined_baseline_only = [-d for d in diffs]

    assert combined_baseline_only == pytest.approx([100.0, 75.0, 200.0, 200.0, 50.0, 75.0, 100.0, 75.0])
    # the buggy (pre-correction) result GPT reported -- regression-
    # locking that THIS is wrong, not a valid alternative.
    assert combined_baseline_only != pytest.approx([50.0, 75.0, 100.0, 100.0, 50.0, 150.0, 200.0, 150.0])


def test_bin_excluded_from_both_sides_when_either_side_is_none_at_that_iteration():
    # Bin "A" signature-side is None at iteration 0 (empty draw) while
    # baseline-side IS available there -- bin A must be excluded from
    # BOTH sides for iteration 0, not just the side that happens to be
    # missing.
    sig_by_bin = {"A": [None, 5.0], "B": [10.0, 10.0]}
    base_by_bin = {"A": [1.0, 1.0], "B": [2.0, 2.0]}
    weights = {"A": 0.5, "B": 0.5}
    diffs = common_support_difference_replicates(sig_by_bin, base_by_bin, weights, 2)
    # iter0: A excluded (sig None there) -> only B: sig=10, base=2 -> diff=8
    # iter1: both available -> sig=0.5*5+0.5*10=7.5, base=0.5*1+0.5*2=1.5 -> diff=6.0
    assert diffs == pytest.approx([8.0, 6.0])


def test_no_common_support_pair_omits_that_iterations_difference_entirely():
    sig_by_bin = {"A": [None, 5.0, 3.0]}
    base_by_bin = {"A": [1.0, None, 3.0]}
    weights = {"A": 1.0}
    diffs = common_support_difference_replicates(sig_by_bin, base_by_bin, weights, 3)
    # iter0: sig None -> no bin qualifies -> omitted.
    # iter1: base None -> no bin qualifies -> omitted.
    # iter2: both available -> diff = 3.0 - 3.0 = 0.0 -- the ONLY entry.
    assert diffs == pytest.approx([0.0])


def test_dense_case_with_no_empty_replicas_matches_the_plain_weighted_combine():
    # No bin ever empty -- the corrected mechanism must reproduce the
    # straightforward weighted combine exactly (no regression in the
    # ordinary case).
    sig_by_bin = {"early": [1.0, 2.0, 3.0], "late": [4.0, 5.0, 6.0]}
    base_by_bin = {"early": [0.5, 0.5, 0.5], "late": [1.0, 1.0, 1.0]}
    weights = {"early": 0.6, "late": 0.4}
    diffs = common_support_difference_replicates(sig_by_bin, base_by_bin, weights, 3)
    expected = [
        (0.6 * sig_by_bin["early"][r] + 0.4 * sig_by_bin["late"][r])
        - (0.6 * base_by_bin["early"][r] + 0.4 * base_by_bin["late"][r])
        for r in range(3)
    ]
    assert diffs == pytest.approx(expected)


def test_bin_empty_in_some_replicas_only_despite_full_original_support():
    # The ORIGINAL population has a row in EVERY bin (full common
    # support at the point-estimate level, A1 would not blackout this
    # profile) -- but block resampling with replacement can still
    # empty out a bin in SOME replicas. Confirms this is handled
    # per-replica, not assumed away by the original population's own
    # full support.
    session_dates_by_bin = {"x": ["2024-01-01", "2024-01-02", "2024-01-03"]}
    # One row only, on session 1 -- original population has exactly
    # ONE row in this bin (non-empty, so A1's own gate sees support
    # here), but block_length=1 means a replicate drawing session 2 or
    # 3 blocks lands empty for this bin.
    rows_by_bin = {"x": [("SEC", "2024-01-01", 7.0)]}
    reps = stratified_baseline_replicates_by_bin(rows_by_bin, session_dates_by_bin, block_length_bars=1, iterations=30, seed=5)
    assert len(reps["x"]) == 30
    assert any(v is None for v in reps["x"]), "sanity: some of 30 replicates (3 sessions, block=1) must miss the only row"
    assert any(v is not None for v in reps["x"]), "sanity: some replicates must still hit it"


def test_interval_construction_from_replicates_is_plain_unweighted_percentile():
    replicates = [1.0, 2.0, 3.0, 4.0, 100.0]
    ci = percentile_ci(replicates)
    assert ci.lower is not None and ci.upper is not None
    assert ci.method == "TIME_BLOCK_BOOTSTRAP_PERCENTILE"


def test_real_engine_produces_a_sensible_mean_difference_ci_even_with_some_empty_replicas():
    # GPT's own closing instruction: verify the CI through the real
    # engine (_evaluate_signature_horizon()), not just isolated
    # helpers. Two bins, full common support in the ORIGINAL
    # population (so A1 does not blackout this profile), but a short
    # block_length_bars relative to each bin's own session count so
    # SOME bootstrap replicates land empty in a bin -- exercising the
    # corrected None-aware path for real, not just in a hand-built
    # helper call.
    from datetime import date, timedelta

    from evaluation.baseline.universe import partition_temporal_bins
    from evaluation.config.loader import load_config as load_evaluation_config
    from evaluation.engine import _evaluate_signature_horizon
    from evaluation.models.entities import (
        EvaluationSignatureDefinition, ForwardOutcome, LaneStateCondition, OutcomeStatus,
    )
    from fixtures.config_overrides import evaluation_config_with_overrides

    class Bar:
        def __init__(self, d, close):
            self.date, self.split_adjusted_close = d, close

    def _dense_bars(start, end, base=100.0):
        s, e = date.fromisoformat(start), date.fromisoformat(end)
        n = (e - s).days + 1
        return [Bar((s + timedelta(days=i)).isoformat(), base + i * 0.01) for i in range(n)]

    def _fake_outcome(sid, as_of, relative_return):
        return ForwardOutcome(
            security_id=sid, observation_as_of=as_of, timeframe="1D", horizon_bars=1,
            entry_reference_price=100.0, exit_reference_price=101.0, exit_as_of=as_of,
            forward_return=0.01, benchmark_return=0.0, relative_return=relative_return,
            outcome_status=OutcomeStatus.VALID.value, development_end=None,
            outcome_engine_version="v1.0.0", config_version="cfg_x",
        )

    bins = partition_temporal_bins("2024-01-01", "2024-12-31", 2)
    early, late = bins[0], bins[1]
    early_date, late_date = early.start_date, late.start_date
    end = (date.fromisoformat(late_date) + timedelta(days=1)).isoformat()
    bars_by_security = {"SIG_SEC": _dense_bars(early_date, end)}
    benchmark_bars = _dense_bars(early_date, end)
    raw_matches_by_security = {"SIG_SEC": [early_date, late_date]}

    # Full common support: baseline has data in BOTH bins (A1 passes).
    baseline_pool_h = [
        ("OTHER_A", early_date, _fake_outcome("OTHER_A", early_date, 0.001)),
        ("OTHER_B", late_date, _fake_outcome("OTHER_B", late_date, 0.002)),
    ]

    ev_config = evaluation_config_with_overrides(
        bootstrap={"block_length_bars": 1, "iterations": 100, "seed": 7, "clustering": "TIME_BLOCK"},
        comparison=load_evaluation_config().data["comparison"],
        support=load_evaluation_config().data["support"],
        stability=load_evaluation_config().data["stability"],
    )
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

    assert profile.support.valid_episode_n == 2, "sanity: both episodes must have produced a VALID outcome"
    bc = profile.baseline_comparison
    # Full common support -> A1 does NOT blackout: mean_difference_ci
    # must be populated, not the None A1's own gate would produce.
    assert bc.mean_difference is not None
    assert bc.mean_difference_ci is not None
    assert bc.mean_difference_ci.lower is not None and bc.mean_difference_ci.upper is not None
    assert bc.mean_difference_ci.lower <= bc.mean_difference_ci.upper
    import math
    assert math.isfinite(bc.mean_difference_ci.lower) and math.isfinite(bc.mean_difference_ci.upper)


def test_signature_side_per_bin_replicates_use_plain_mean_not_weighted():
    # The signature side is never per-security weighted (F4+F5 is a
    # baseline-only concept) -- signature_bootstrap_replicates_by_bin()
    # must use the plain mean, confirmed by NOT taking a security_id at
    # all in its payload (plain (as_of, value) rows).
    session_dates_by_bin = {"x": ["2024-01-01", "2024-01-02"]}
    dated_by_bin = {"x": [("2024-01-01", 1.0), ("2024-01-02", 3.0)]}
    reps = signature_bootstrap_replicates_by_bin(dated_by_bin, session_dates_by_bin, block_length_bars=2, iterations=5, seed=1)
    # block_length=2 over 2 sessions -> ONE block covering both -- every
    # replicate reconstructs the exact same two values, mean=(1+3)/2=2.0.
    assert reps["x"] == [2.0, 2.0, 2.0, 2.0, 2.0]
