import json
from dataclasses import replace

import pytest

from data_foundation.adapters.yfinance_adapter import YFinanceAdapter, utc_now_iso
from data_foundation.calendar.admission import AdmissionRegistry, admit_source_via_operator_attestation
from data_foundation.calendar.contract import build_trading_calendar
from data_foundation.calendar.entities import CalendarSource
from data_foundation.calendar.registry import CalendarRegistry
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


# FORMAL_DEVELOPMENT now REQUIRES a registry-resolved, OFFICIAL_VERIFIED
# calendar (decision registry B1; GPT review, Stage 2 changes-required
# round) -- `fast_evaluation_config`'s own evaluation_mode is
# FORMAL_DEVELOPMENT (unchanged from evaluation.yaml's default), so every
# existing test calling run_evaluation() with it must now also supply
# this registered calendar. Session_dates == the tiny_universe's own
# DATES, so target-session resolution matches every existing bar-position
# expectation exactly (no behavior shift beyond what Stage 2 itself
# authorizes).
@pytest.fixture
def formal_calendar():
    return build_trading_calendar(
        source=CalendarSource.OFFICIAL_VERIFIED.value, calendar_identifier="SPEC003_TINY_UNIVERSE_FIXTURE",
        calendar_version="v1", market="US_EQUITIES", timezone="America/New_York",
        coverage_start=DATES[0], coverage_end=DATES[-1], session_dates=tuple(DATES),
        session_open_time="09:30", session_close_time="16:00",
        verified_by="radu", verified_at="2026-10-06T00:00:00Z",
    )


@pytest.fixture
def formal_calendar_registry(formal_calendar):
    admission_registry = AdmissionRegistry()
    raw = json.dumps({"session_dates": list(formal_calendar.session_dates), "early_close_dates": []})
    admitted = admit_source_via_operator_attestation(
        registry=admission_registry, source_identifier="SPEC003_TEST_FIXTURE_FEED", operator_name="radu", attested_at="2026-10-06T00:00:00Z",
        version="v1", publication_date=DATES[0], coverage_start=formal_calendar.coverage_start,
        coverage_end=formal_calendar.coverage_end, market=formal_calendar.market, timezone=formal_calendar.timezone,
        raw_content=raw,
    )
    registry = CalendarRegistry()
    registry.register_verified(
        formal_calendar, admission_registry, admitted.artifact_digest, verified_by="radu", verified_at="2026-10-06T00:00:00Z",
    )
    return registry


@pytest.fixture
def formal_calendar_id(formal_calendar):
    return formal_calendar.calendar_id
