from dataclasses import replace

import pytest

from data_foundation.adapters.yfinance_adapter import YFinanceAdapter, utc_now_iso
from data_foundation.model import ingestion as ing
from data_foundation.storage.db import connect_and_init
from fixtures.fake_yfinance import make_ticker_factory

from discovery.config.loader import load_config as load_discovery_config
from evaluation.config.loader import load_config as load_evaluation_config

from spec003.fixtures.tiny_universe import ALL_DATASETS, BENCHMARK, DATES


@pytest.fixture
def conn():
    c = connect_and_init(":memory:")
    yield c
    c.close()


@pytest.fixture
def now():
    return utc_now_iso()


@pytest.fixture
def tiny_universe(conn, now):
    ticker_to_dataset = {BENCHMARK["ticker"]: BENCHMARK}
    for ds in ALL_DATASETS:
        ticker_to_dataset[ds["ticker"]] = ds
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory(ticker_to_dataset))

    security_ids: dict[str, str] = {}
    for ticker, ds in ticker_to_dataset.items():
        sid = ing.new_security_id(f"spec003:{ticker}")
        ing.ensure_security(conn, sid, adapter, ticker, now)
        start, end = ds["bars"][0]["date"], ds["bars"][-1]["date"]
        ing.ensure_symbol_history(conn, sid, ticker, start, None, "yfinance")
        ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)
        security_ids[ticker] = sid

    benchmark_security_id = security_ids[BENCHMARK["ticker"]]
    non_benchmark_ids = [sid for ticker, sid in security_ids.items() if ticker != BENCHMARK["ticker"]]
    return {
        "security_ids": security_ids,
        "benchmark_security_id": benchmark_security_id,
        "non_benchmark_ids": non_benchmark_ids,
    }


# Days [33..40] (0-indexed into DATES) are COMPQ's clean EXTREME_COMPRESSION/
# COMPRESSION run (verified manually against BB_width_percentile with
# percentile_window=15); [49..53] is a second, separate burst -- see
# tests/spec003/fixtures/tiny_universe.py's module docstring.
COMPRESSION_WINDOW_START = DATES[30]
COMPRESSION_WINDOW_END = DATES[55]


@pytest.fixture
def reduced_discovery_config():
    base = load_discovery_config()
    return replace(
        base,
        features={**base.features, "percentile_window": 15, "percentile_min_periods": 15},
        eligibility={**base.eligibility, "minimum_history_days": 15, "minimum_adv_20": 1000},
    )


@pytest.fixture
def fast_evaluation_config():
    base = load_evaluation_config()
    data = dict(base.data)
    data["support"] = {"minimum_episode_count": 1, "minimum_unique_securities": 1}
    data["bootstrap"] = {**base.data["bootstrap"], "iterations": 200, "block_length_bars": 5}
    data["comparison"] = {**base.data["comparison"], "iterations": 200}
    data["stability"] = {"temporal_bins": 3}
    return replace(base, data=data)
