"""TEST 59 -- A1 (F3 common support blackout), run_evaluation()-level
completion (joint remediation design 003+004 section 3-6; decision
registry A1, Stage 4 -- GPT's own completion request on commit
`abc74f1`'s review).

`test_58_common_support_blackout_wired_in_engine.py` already proves
the blackout fires correctly by calling the real, private
`_evaluate_signature_horizon()` directly -- GPT accepted that as
useful, production-code-exercising coverage, not a reason to reject.
This test COMPLETES it with the additional case GPT asked for: the
PUBLIC `run_evaluation()` entry point, a real SQLite test database,
real price/benchmark fixtures, and real config objects.

The ONE explicitly declared substitution (GPT's own exact scope,
nothing broader): `compute_discovery_observations()` is replaced, at
the Discovery->Evaluation boundary, by a deterministic fixture that
returns observations for ONLY three (security_id, as_of) pairs --
everything else about Discovery's own feature/state computation is
irrelevant to A1's own mechanism, so it is never exercised here and
never claimed to be. From that boundary onward, this test changes
NOTHING: `run_evaluation()` itself builds the baseline, computes real
forward/relative returns via `compute_forward_outcome()`, applies
`exclude_self()`, forms episodes via `build_episodes()`, and
determines common support via `_evaluate_signature_horizon()`'s own
real A1 gate -- none of these are stubbed or hand-substituted.

Fixture shape (GPT's own specification): the signal security matches
the signature on one date in EACH of two temporal bins, far enough
apart (by real, dense daily bars, so build_episodes()'s bar-INDEX gap
measurement sees them as separate) to form two distinct episodes. A
control security has ONE eligible, non-matching observation in ONLY
the first bin -- contributing to that bin's baseline, while nothing
else provides baseline coverage for the second bin.
"""
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from data_foundation.adapters.yfinance_adapter import YFinanceAdapter, utc_now_iso
from data_foundation.model import ingestion as ing
from data_foundation.storage.db import connect_and_init
from discovery.config.loader import load_config as load_discovery_config
from discovery.models.entities import DescriptiveMetrics, DiscoveryObservation
from evaluation.baseline.universe import partition_temporal_bins
from evaluation.config.loader import load_config as load_evaluation_config
from evaluation.engine import run_evaluation
from evaluation.models.entities import EvaluationSignatureDefinition, LaneStateCondition
from evaluation.registry.signatures import freeze_signature_set
from fixtures.config_overrides import evaluation_config_with_overrides
from fixtures.fake_yfinance import make_ticker_factory

DEVELOPMENT_START = "2024-01-01"
DEVELOPMENT_END = "2024-04-10"
BAR_DATA_END = "2024-04-20"  # a few days of buffer past development_end, for horizon forward returns

EARLY_SIGNAL_DATE = "2024-01-10"
EARLY_CONTROL_DATE = "2024-01-15"
LATE_SIGNAL_DATE = "2024-03-01"

SIG_SEC_TICKER = "SIGSEC"
CONTROL_SEC_TICKER = "CTRLSEC"
BENCHMARK_TICKER = "BENCH59"


def _dense_bars(start: str, end: str, base_price: float) -> list[dict]:
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    n = (e - s).days + 1
    bars = []
    for i in range(n):
        d = (s + timedelta(days=i)).isoformat()
        close = round(base_price + i * 0.01, 4)
        bars.append({
            "date": d, "open": close, "high": close * 1.001, "low": close * 0.999,
            "close": close, "adj_close": close, "volume": 100_000,
        })
    return bars


def _dataset(ticker: str, base_price: float) -> dict:
    return {
        "ticker": ticker,
        "info": {"quoteType": "EQUITY", "exchange": "SYNTH", "currency": "USD"},
        "bars": _dense_bars(DEVELOPMENT_START, BAR_DATA_END, base_price),
        "splits": {}, "dividends": {},
    }


def _observation(security_id: str, as_of: str, state_label: str) -> DiscoveryObservation:
    return DiscoveryObservation(
        security_id=security_id, ticker_as_of=None, as_of=as_of, timeframe="1D",
        feature_vector={}, normalized_feature_vector={}, state_signature={"volatility": state_label},
        transition_vector={}, active_lanes=["volatility"],
        descriptive_metrics=DescriptiveMetrics(
            extremeness=0.0, persistence=0, state_frequency=None, sample_count=0, support_status="PENDING_DATA",
        ),
        reason_codes=[], config_version="cfg_x", feature_engine_version="v1.0.0",
        discovery_engine_version="v1.0.0",
    )


@pytest.fixture
def fixture_universe():
    conn = connect_and_init(":memory:")
    now = utc_now_iso()
    datasets = {
        BENCHMARK_TICKER: _dataset(BENCHMARK_TICKER, 100.0),
        SIG_SEC_TICKER: _dataset(SIG_SEC_TICKER, 50.0),
        CONTROL_SEC_TICKER: _dataset(CONTROL_SEC_TICKER, 75.0),
    }
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory(datasets))
    security_ids = {}
    for ticker, ds in datasets.items():
        sid = ing.new_security_id(f"test59:{ticker}")
        ing.ensure_security(conn, sid, adapter, ticker, now)
        start, end = ds["bars"][0]["date"], ds["bars"][-1]["date"]
        ing.ensure_symbol_history(conn, sid, ticker, start, None, "yfinance")
        ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)
        security_ids[ticker] = sid
    yield conn, security_ids
    conn.close()


def test_partial_common_support_via_real_run_evaluation_propagates_to_evidence_packet(fixture_universe):
    conn, security_ids = fixture_universe
    benchmark_security_id = security_ids[BENCHMARK_TICKER]
    sig_sec_id = security_ids[SIG_SEC_TICKER]
    control_sec_id = security_ids[CONTROL_SEC_TICKER]
    non_benchmark_ids = [sig_sec_id, control_sec_id]

    def fake_discovery_observations(conn, security_ids_arg, as_of, benchmark_security_id_arg, config=None, *, config_registry=None):
        if as_of == EARLY_SIGNAL_DATE:
            return [_observation(sig_sec_id, as_of, "COMPRESSION")]
        if as_of == EARLY_CONTROL_DATE:
            return [_observation(control_sec_id, as_of, "NORMAL")]  # eligible, does NOT match the signature
        if as_of == LATE_SIGNAL_DATE:
            return [_observation(sig_sec_id, as_of, "COMPRESSION")]
        return []  # every other session date: no eligible observations at all

    signature = EvaluationSignatureDefinition(
        signature_id="SIG", lane_conditions=(LaneStateCondition("volatility", "COMPRESSION"),),
        reason_code_conditions=(), timeframe="1D", discovery_engine_version="v1.0.0",
        discovery_config_version=load_discovery_config().config_version, creation_mode="PRE_REGISTERED",
        created_before_outcome_evaluation=True,
    )
    sigset = freeze_signature_set([signature])
    eval_config = evaluation_config_with_overrides(
        evaluation_mode="EXPLORATORY",
        support={"minimum_episode_count": 1, "minimum_unique_securities": 1},
        bootstrap={**load_evaluation_config().data["bootstrap"], "iterations": 50, "block_length_bars": 5},
        comparison={**load_evaluation_config().data["comparison"], "iterations": 50},
        stability={"temporal_bins": 2},
    )

    with patch("evaluation.engine.compute_discovery_observations", side_effect=fake_discovery_observations):
        profiles, registry = run_evaluation(
            conn, non_benchmark_ids, benchmark_security_id,
            DEVELOPMENT_START, DEVELOPMENT_END, sigset,
            load_discovery_config(), eval_config,
        )

    assert registry.mode == "EXPLORATORY"
    # The mocked observations/dense bars are identical across every
    # horizon Discovery-wise, so the SAME partial-support pattern must
    # hold at every horizon_bars this run tested -- checked on all of
    # them, not just one, so the packet's own reference horizon (3,
    # hypothesis.yaml's default -- NOT 1) is covered too.
    assert len(profiles) >= 2, "sanity: run_evaluation() must have tested more than one horizon"

    for profile in profiles:
        # Two episodes, in two different bins, both VALID -- confirms
        # the fixture itself is shaped as specified, before checking
        # A1's own behavior.
        assert profile.support.valid_episode_n == 2
        bins_with_episodes = {s.bin_label for s in profile.stability if s.episode_n > 0}
        assert bins_with_episodes == {"early", "late"}

        bc = profile.baseline_comparison
        # Baseline available ONLY in "early" (the control security's
        # own observation there, after exclude_self() removes nothing
        # from it since it never matched the signature) -- NOTHING
        # provides baseline in "late": partial common support -> the
        # 5-field blackout, TOGETHER.
        assert bc.mean_difference is None
        assert bc.median_difference is None
        assert bc.raw_p is None
        assert bc.mean_difference_ci is None
        assert bc.standardized_effect is None
        # baseline_mean/baseline_median themselves are NOT blacked
        # out -- they reflect whatever bin(s) the baseline pool
        # actually has data in (early only here).
        assert bc.baseline_mean is not None

        # The signature's own full-population descriptive stats
        # remain available -- A1 restricts comparison fields only,
        # never these.
        assert profile.relative_outcome.n == 2
        assert profile.relative_outcome.mean is not None
        assert profile.absolute_outcome.n == 2

    # Propagate to #004: the None set must survive build_evidence_
    # packet() unchanged, never crashing or substituting a value --
    # checked on the packet's own policy-fixed reference horizon.
    from hypothesis.config.loader import load_config as load_hypothesis_config
    from hypothesis.evidence.packet import build_evidence_packet
    from hypothesis.evidence.queue import compute_review_priority

    all_profiles_this_signature = [p for p in profiles if p.signature_id == "SIG"]
    packet = build_evidence_packet(signature, all_profiles_this_signature, registry, load_hypothesis_config())
    assert packet.primary_evidence_horizon_bars == 3  # hypothesis.yaml's reference_horizon_bars -- sanity
    assert packet.primary_standardized_effect is None
    assert packet.primary_adjusted_p is None  # EXPLORATORY mode never computes adjusted_p, regardless of A1

    key = compute_review_priority(packet)
    assert key[0] == float("inf")
