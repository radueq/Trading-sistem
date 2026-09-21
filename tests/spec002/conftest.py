import pytest

from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing
from fixtures.fake_yfinance import make_ticker_factory

from spec002.fixtures.synthetic_universe import ALL_DATASETS, BENCHMARK, NAMED_SECURITIES


@pytest.fixture
def universe(conn, now):
    """Ingests the full synthetic universe + benchmark into Data
    Foundation via the normal Spec #001 ingestion path (adapter ->
    ingestion -> repository) -- never inserted directly, so Discovery's
    PIT-only access is exercised against a realistic ingestion history.
    """
    ticker_to_dataset = {BENCHMARK["ticker"]: BENCHMARK}
    for ds in ALL_DATASETS:
        ticker_to_dataset[ds["ticker"]] = ds

    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory(ticker_to_dataset))

    security_ids: dict[str, str] = {}
    for ticker, ds in ticker_to_dataset.items():
        sid = ing.new_security_id(f"spec002:{ticker}")
        ing.ensure_security(conn, sid, adapter, ticker, now)
        start, end = ds["bars"][0]["date"], ds["bars"][-1]["date"]
        ing.ensure_symbol_history(conn, sid, ticker, start, None, "yfinance")
        ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)
        security_ids[ticker] = sid

    benchmark_security_id = security_ids[BENCHMARK["ticker"]]
    named = {name: security_ids[ds["ticker"]] for name, ds in NAMED_SECURITIES.items()}
    non_benchmark_ids = [sid for ticker, sid in security_ids.items() if ticker != BENCHMARK["ticker"]]

    return {
        "security_ids": security_ids,
        "benchmark_security_id": benchmark_security_id,
        "named": named,
        "non_benchmark_ids": non_benchmark_ids,
    }
