"""Ingestion orchestration: drives a ProviderAdapter and writes its output
into storage via the repository layer.

Deliberately NOT here: cross-provider / cross-ticker identity resolution.
yfinance's free tier exposes no stable per-listing identifier (no
ISIN/CIK/FIGI), so there is no reliable signal this module could use to
automatically decide "ticker X today is the same real-world company as
ticker Y three years ago" (a rename) vs "ticker X today is an unrelated
company that happens to reuse a symbol X used by someone else in the
past" (reuse). Deciding that is a Level 1 orchestration/seed-data
responsibility -- the caller always supplies security_id explicitly (see
docs/known_limitations.md). This keeps the module free of guessing logic
that could silently merge two companies' histories (Spec #001 SS4/TEST 6).
"""
from __future__ import annotations

import hashlib

from data_foundation.adapters.base import ProviderAdapter, RawPriceBar
from data_foundation.model import repository as repo
from data_foundation.model.entities import (
    CorporateAction, PriceBar, SecurityMaster, SymbolHistoryEntry,
)


def new_security_id(seed: str) -> str:
    """Deterministic id from a caller-chosen disambiguating seed string
    (e.g. "yfinance:AAPL", or "yfinance:ZZZQ:company_a" when the caller
    already knows a ticker is being reused). Determinism keeps re-running
    a seed/ingestion script reproducible; the seed content is entirely
    the caller's disambiguation responsibility."""
    return "sec_" + hashlib.sha256(seed.encode()).hexdigest()[:16]


def generate_action_id(security_id: str, action_type: str, effective_date: str,
                        source_provider: str, value) -> str:
    key = f"{security_id}:{action_type}:{effective_date}:{source_provider}:{value}".encode()
    return "ca_" + hashlib.sha256(key).hexdigest()[:16]


def ensure_security(conn, security_id: str, adapter: ProviderAdapter, ticker: str,
                     ingestion_timestamp: str, security_type_override: str | None = None) -> None:
    """Idempotently ensures a security_master row exists for the given,
    caller-assigned security_id."""
    if repo.get_security_by_id(conn, security_id) is not None:
        return

    info = adapter.fetch_security_info(ticker)
    security_type = security_type_override or info.security_type
    if security_type is None:
        raise ValueError(
            f"security_type unavailable from {adapter.provider_name} for {ticker} "
            f"and no security_type_override supplied -- refusing to invent a value"
        )

    repo.insert_security_master(conn, SecurityMaster(
        security_id=security_id, security_type=security_type,
        primary_exchange=info.primary_exchange, currency=info.currency,
        source_provider=adapter.provider_name, source_security_id=ticker,
        ingestion_timestamp=ingestion_timestamp,
    ))


def ensure_symbol_history(conn, security_id: str, ticker: str, valid_from: str,
                           valid_to: str | None, source_provider: str) -> None:
    repo.insert_symbol_history(conn, SymbolHistoryEntry(
        security_id=security_id, ticker=ticker, exchange=None,
        valid_from=valid_from, valid_to=valid_to, source_provider=source_provider,
    ))


def ingest_prices(conn, adapter: ProviderAdapter, security_id: str, ticker: str,
                   start: str, end: str, ingestion_timestamp: str) -> list[RawPriceBar]:
    raw_bars = adapter.fetch_price_history(ticker, start, end)
    repo.insert_price_bars(conn, [
        PriceBar(
            security_id=security_id, date=b.date, raw_open=b.raw_open, raw_high=b.raw_high,
            raw_low=b.raw_low, raw_close=b.raw_close, raw_volume=b.raw_volume,
            source_provider=adapter.provider_name, ingestion_timestamp=ingestion_timestamp,
        )
        for b in raw_bars
    ])
    return raw_bars


def ingest_corporate_actions(conn, adapter: ProviderAdapter, security_id: str, ticker: str,
                              start: str, end: str, ingestion_timestamp: str) -> list[CorporateAction]:
    """Level 1 knowledge-time policy (Radu's correction, 2026-09-21):
    available_at is set to the adapter's announcement_date when the
    adapter supplies one (we trust that as our knowledge-time signal),
    and left NULL otherwise -- never guessed, never backfilled from
    ingestion_timestamp. yfinance never supplies announcement_date today,
    so every yfinance-sourced action currently gets available_at=NULL,
    which pit/access.py handles via its explicit Level 1 fallback."""
    raw_events = adapter.fetch_corporate_actions(ticker, start, end)
    actions = [
        CorporateAction(
            action_id=generate_action_id(security_id, e.action_type, e.effective_date,
                                          adapter.provider_name, e.value),
            security_id=security_id, action_type=e.action_type,
            announcement_date=e.announcement_date, effective_date=e.effective_date,
            value=e.value, source_provider=adapter.provider_name,
            source_status=e.source_status, source_status_date=e.source_status_date,
            available_at=e.announcement_date,
            ingestion_timestamp=ingestion_timestamp,
            last_updated_timestamp=ingestion_timestamp,
        )
        for e in raw_events
    ]
    # Enrichment upsert, not a plain insert: re-ingesting the same
    # action_id (e.g. a status later reported CANCELLED) must reach the
    # stored row, not be silently dropped (GPT Final Review #001,
    # 2026-09-21 -- see repository.upsert_corporate_action).
    repo.upsert_corporate_actions(conn, actions)
    return actions
