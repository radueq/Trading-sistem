"""Spec #005 v1.0 Batch 2 -- a small, real SQLite-backed universe for
PIT/snapshot/cache tests.

Direct-repository-insert helpers, not synthetic in-memory objects and
not the fake-yfinance-adapter ingestion path `tests/spec002/conftest.py`/
`tests/spec003/conftest.py` use -- Batch 2 is specifically about
exercising `data_foundation.pit.access` against real stored facts, so
inserting rows straight through `repository.py` (mirroring
`tests/test_13_knowledge_time_policy.py`'s pattern, the closest existing
precedent) is more direct than driving a full ingestion pipeline for
data that doesn't need adapter-level realism.
"""
from __future__ import annotations

from typing import Optional

from data_foundation.model import ingestion as ing, repository as repo
from data_foundation.model.entities import CorporateAction, ListingStatusEntry, PriceBar, SecurityMaster

from fixtures.market_data import make_bars


def make_security(conn, seed: str, now: str) -> str:
    sid = ing.new_security_id(seed)
    repo.insert_security_master(conn, SecurityMaster(
        security_id=sid, security_type="EQUITY", primary_exchange=None, currency="USD",
        source_provider="manual", source_security_id=seed, ingestion_timestamp=now,
    ))
    return sid


def insert_price_history(
    conn, security_id: str, now: str, start: str, end: str, base_price: float, daily_drift: float = 0.0,
) -> None:
    bars = make_bars(start, end, base_price=base_price, daily_drift=daily_drift)
    repo.insert_price_bars(conn, [
        PriceBar(
            security_id=security_id, date=b["date"], raw_open=b["open"], raw_high=b["high"],
            raw_low=b["low"], raw_close=b["close"], raw_volume=b["volume"],
            source_provider="manual", ingestion_timestamp=now,
        )
        for b in bars
    ])


def insert_corporate_action(
    conn, security_id: str, action_id: str, action_type: str, effective_date: str, value: float, now: str,
    announcement_date: Optional[str] = None, available_at: Optional[str] = None,
    source_status: Optional[str] = None, source_status_date: Optional[str] = None,
) -> None:
    repo.upsert_corporate_actions(conn, [CorporateAction(
        action_id=action_id, security_id=security_id, action_type=action_type,
        announcement_date=announcement_date, effective_date=effective_date, value=value,
        source_provider="manual", source_status=source_status, source_status_date=source_status_date,
        available_at=available_at, ingestion_timestamp=now, last_updated_timestamp=now,
    )])


def insert_listing_status(
    conn, security_id: str, status: str, effective_from: str, now: str,
    effective_to: Optional[str] = None, available_at: Optional[str] = None,
    delisting_reason: Optional[str] = None,
) -> None:
    repo.upsert_listing_status(conn, ListingStatusEntry(
        security_id=security_id, status=status, effective_from=effective_from, effective_to=effective_to,
        source_provider="manual", delisting_reason=delisting_reason, available_at=available_at,
        last_updated_timestamp=now,
    ))
