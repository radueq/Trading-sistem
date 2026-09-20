"""yfinance Provider Adapter -- Level 1 (Technical Prototype) provider.

All yfinance-specific quirks (auto_adjust semantics, column names, the
fact that yfinance exposes no corporate-action announcement_date, that
Adj Close is the provider's own adjusted series) are isolated here and
must never leak into downstream modules (Spec #001 SS19).

The yfinance `Ticker` object is injected via `ticker_factory` so this
adapter can be exercised in tests against recorded fixture data without
live network access, while defaulting to the real `yfinance.Ticker` in
production use.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Callable, Optional

from data_foundation.adapters.base import (
    ProviderAdapter,
    RawCorporateActionEvent,
    RawPriceBar,
    RawSecurityInfo,
)
from data_foundation.model.entities import ActionType


def _default_ticker_factory(ticker: str):
    import yfinance as yf
    return yf.Ticker(ticker)


def _clean_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _clean_int(value) -> Optional[int]:
    f = _clean_float(value)
    return None if f is None else int(f)


def _to_iso_date(ts) -> str:
    return ts.strftime("%Y-%m-%d")


class YFinanceAdapter(ProviderAdapter):
    provider_name = "yfinance"

    def __init__(self, ticker_factory: Callable[[str], object] = _default_ticker_factory):
        self._ticker_factory = ticker_factory

    def fetch_security_info(self, ticker: str) -> RawSecurityInfo:
        unavailable: list[str] = []
        security_type = primary_exchange = currency = None
        try:
            info = self._ticker_factory(ticker).info
        except Exception:
            info = {}
            unavailable.extend(["security_type", "primary_exchange", "currency"])
        else:
            quote_type = info.get("quoteType")
            security_type = "EQUITY" if quote_type == "EQUITY" else None
            if security_type is None:
                unavailable.append("security_type")

            primary_exchange = info.get("exchange")
            if primary_exchange is None:
                unavailable.append("primary_exchange")

            currency = info.get("currency")
            if currency is None:
                unavailable.append("currency")

        return RawSecurityInfo(
            source_security_id=ticker,
            security_type=security_type,
            primary_exchange=primary_exchange,
            currency=currency,
            unavailable_fields=unavailable,
        )

    def fetch_price_history(self, ticker: str, start: str, end: str) -> list[RawPriceBar]:
        t = self._ticker_factory(ticker)
        # auto_adjust=False is required to get both raw OHLC and the
        # provider's own adjusted close as a separate, clearly-labeled
        # column -- with auto_adjust=True (yfinance's default) the raw
        # values are silently replaced by adjusted ones, which would
        # violate "raw data must be preserved" (Spec #001 SS5).
        hist = t.history(start=start, end=end, auto_adjust=False, actions=True)

        bars: list[RawPriceBar] = []
        for idx, row in hist.iterrows():
            bars.append(
                RawPriceBar(
                    source_security_id=ticker,
                    date=_to_iso_date(idx),
                    raw_open=_clean_float(row.get("Open")),
                    raw_high=_clean_float(row.get("High")),
                    raw_low=_clean_float(row.get("Low")),
                    raw_close=_clean_float(row.get("Close")),
                    raw_volume=_clean_int(row.get("Volume")),
                    provider_adjusted_close=_clean_float(row.get("Adj Close")),
                )
            )
        return bars

    def fetch_corporate_actions(self, ticker: str, start: str, end: str) -> list[RawCorporateActionEvent]:
        t = self._ticker_factory(ticker)
        events: list[RawCorporateActionEvent] = []

        splits = getattr(t, "splits", None)
        if splits is not None:
            for idx, ratio in splits.items():
                date = _to_iso_date(idx)
                if not (start <= date <= end):
                    continue
                ratio = _clean_float(ratio)
                if ratio is None or ratio == 0:
                    continue
                action_type = ActionType.SPLIT.value if ratio >= 1 else ActionType.REVERSE_SPLIT.value
                events.append(
                    RawCorporateActionEvent(
                        source_security_id=ticker,
                        action_type=action_type,
                        # yfinance's free tier does not expose a distinct
                        # announcement date for splits -- declared
                        # unavailable rather than invented (Spec #001 SS18.5).
                        announcement_date=None,
                        effective_date=date,
                        value=ratio,
                        source_status=None,
                        source_status_date=None,
                    )
                )

        dividends = getattr(t, "dividends", None)
        if dividends is not None:
            for idx, amount in dividends.items():
                date = _to_iso_date(idx)
                if not (start <= date <= end):
                    continue
                amount = _clean_float(amount)
                if amount is None:
                    continue
                events.append(
                    RawCorporateActionEvent(
                        source_security_id=ticker,
                        action_type=ActionType.DIVIDEND.value,
                        announcement_date=None,
                        effective_date=date,
                        value=amount,
                        source_status=None,
                        source_status_date=None,
                    )
                )

        return events


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
