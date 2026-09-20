"""Fake yfinance.Ticker for tests -- see market_data.py for provenance.

Mimics the subset of yfinance's Ticker API the adapter uses (.history(),
.splits, .dividends, .info) so YFinanceAdapter itself is exercised by
tests, not bypassed. Swapping the real yfinance.Ticker back in (default
ticker_factory in yfinance_adapter.py) requires no adapter code changes.
"""
from __future__ import annotations

import pandas as pd


class FakeTicker:
    def __init__(self, ticker: str, dataset: dict):
        self.ticker = ticker
        self._dataset = dataset

    @property
    def info(self) -> dict:
        return dict(self._dataset.get("info", {}))

    def history(self, start: str | None = None, end: str | None = None,
                auto_adjust: bool = False, actions: bool = True) -> pd.DataFrame:
        rows, idx = [], []
        for bar in self._dataset["bars"]:
            d = bar["date"]
            if start and d < start:
                continue
            if end and d > end:
                continue
            idx.append(pd.Timestamp(d))
            rows.append({
                "Open": bar["open"], "High": bar["high"], "Low": bar["low"],
                "Close": bar["close"], "Adj Close": bar["adj_close"], "Volume": bar["volume"],
            })
        return pd.DataFrame(rows, index=pd.DatetimeIndex(idx, name="Date"))

    @property
    def splits(self) -> pd.Series:
        items = self._dataset.get("splits", {})
        if not items:
            return pd.Series(dtype="float64")
        return pd.Series(list(items.values()),
                          index=pd.DatetimeIndex([pd.Timestamp(d) for d in items.keys()]))

    @property
    def dividends(self) -> pd.Series:
        items = self._dataset.get("dividends", {})
        if not items:
            return pd.Series(dtype="float64")
        return pd.Series(list(items.values()),
                          index=pd.DatetimeIndex([pd.Timestamp(d) for d in items.keys()]))


def make_ticker_factory(datasets_by_ticker: dict[str, dict]):
    """Returns a ticker_factory(ticker) -> FakeTicker, per YFinanceAdapter's
    injectable factory contract."""
    def factory(ticker: str) -> FakeTicker:
        return FakeTicker(ticker, datasets_by_ticker[ticker])
    return factory
