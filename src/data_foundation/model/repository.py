"""Repository functions: typed reads/writes against the 7 schema tables.

Write semantics by table kind:
- Raw / factual tables (security_master, symbol_history, price_history,
  corporate_actions, listing_status_history): INSERT OR IGNORE, keyed on
  the table's natural primary key. Re-running ingestion is idempotent;
  raw facts are never overwritten in place.
- Derived / recomputable tables (adjustment_factors, qa_results): INSERT
  OR REPLACE. These are reproducible outputs of a documented methodology,
  not source-of-truth facts, so recomputation is expected to supersede
  prior rows for the same key.

These functions are intentionally low-level (no as_of filtering, no
status derivation) -- that logic belongs to pit/access.py. Direct callers
of this module are the adapter/ingestion path and, for their own
inspection, storage-level tests -- never research-facing consumers (see
Spec #001 SS10-11).
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from data_foundation.model.entities import (
    AdjustmentFactor,
    CorporateAction,
    ListingStatusEntry,
    PriceBar,
    QAResult,
    SecurityMaster,
    SymbolHistoryEntry,
)


def insert_security_master(conn: sqlite3.Connection, row: SecurityMaster) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO security_master
            (security_id, security_type, primary_exchange, currency,
             source_provider, source_security_id, ingestion_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.security_id, row.security_type, row.primary_exchange,
            row.currency, row.source_provider, row.source_security_id,
            row.ingestion_timestamp,
        ),
    )
    conn.commit()


def get_security_by_provider_id(
    conn: sqlite3.Connection, source_provider: str, source_security_id: str
) -> Optional[SecurityMaster]:
    cur = conn.execute(
        """SELECT * FROM security_master
           WHERE source_provider = ? AND source_security_id = ?""",
        (source_provider, source_security_id),
    )
    r = cur.fetchone()
    return _row_to_security_master(r) if r else None


def get_security_by_id(conn: sqlite3.Connection, security_id: str) -> Optional[SecurityMaster]:
    cur = conn.execute("SELECT * FROM security_master WHERE security_id = ?", (security_id,))
    r = cur.fetchone()
    return _row_to_security_master(r) if r else None


def _row_to_security_master(r: sqlite3.Row) -> SecurityMaster:
    return SecurityMaster(
        security_id=r["security_id"], security_type=r["security_type"],
        primary_exchange=r["primary_exchange"], currency=r["currency"],
        source_provider=r["source_provider"], source_security_id=r["source_security_id"],
        ingestion_timestamp=r["ingestion_timestamp"],
    )


def insert_symbol_history(conn: sqlite3.Connection, row: SymbolHistoryEntry) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO symbol_history
            (security_id, ticker, exchange, valid_from, valid_to, source_provider)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (row.security_id, row.ticker, row.exchange, row.valid_from, row.valid_to, row.source_provider),
    )
    conn.commit()


def close_symbol_history(conn: sqlite3.Connection, security_id: str, valid_from: str, valid_to: str) -> None:
    """Set valid_to on an open symbol_history row (ticker change/delisting)."""
    conn.execute(
        """UPDATE symbol_history SET valid_to = ?
           WHERE security_id = ? AND valid_from = ? AND valid_to IS NULL""",
        (valid_to, security_id, valid_from),
    )
    conn.commit()


def get_symbol_history_for_security(conn: sqlite3.Connection, security_id: str) -> list[SymbolHistoryEntry]:
    cur = conn.execute(
        "SELECT * FROM symbol_history WHERE security_id = ? ORDER BY valid_from", (security_id,)
    )
    return [_row_to_symbol_history(r) for r in cur.fetchall()]


def get_symbol_history_for_ticker(conn: sqlite3.Connection, ticker: str) -> list[SymbolHistoryEntry]:
    cur = conn.execute(
        "SELECT * FROM symbol_history WHERE ticker = ? ORDER BY valid_from", (ticker,)
    )
    return [_row_to_symbol_history(r) for r in cur.fetchall()]


def _row_to_symbol_history(r: sqlite3.Row) -> SymbolHistoryEntry:
    return SymbolHistoryEntry(
        security_id=r["security_id"], ticker=r["ticker"], exchange=r["exchange"],
        valid_from=r["valid_from"], valid_to=r["valid_to"], source_provider=r["source_provider"],
    )


def insert_price_bar(conn: sqlite3.Connection, row: PriceBar) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO price_history
            (security_id, date, raw_open, raw_high, raw_low, raw_close,
             raw_volume, source_provider, ingestion_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.security_id, row.date, row.raw_open, row.raw_high, row.raw_low,
            row.raw_close, row.raw_volume, row.source_provider, row.ingestion_timestamp,
        ),
    )


def insert_price_bars(conn: sqlite3.Connection, rows: list[PriceBar]) -> None:
    for row in rows:
        insert_price_bar(conn, row)
    conn.commit()


def get_price_history(conn: sqlite3.Connection, security_id: str) -> list[PriceBar]:
    cur = conn.execute(
        "SELECT * FROM price_history WHERE security_id = ? ORDER BY date", (security_id,)
    )
    return [_row_to_price_bar(r) for r in cur.fetchall()]


def _row_to_price_bar(r: sqlite3.Row) -> PriceBar:
    return PriceBar(
        security_id=r["security_id"], date=r["date"], raw_open=r["raw_open"],
        raw_high=r["raw_high"], raw_low=r["raw_low"], raw_close=r["raw_close"],
        raw_volume=r["raw_volume"], source_provider=r["source_provider"],
        ingestion_timestamp=r["ingestion_timestamp"],
    )


def upsert_adjustment_factor(conn: sqlite3.Connection, row: AdjustmentFactor) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO adjustment_factors
            (security_id, date, split_adjustment_factor, total_return_adjustment_factor,
             provider_adjusted_close, methodology_version, source_provider, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.security_id, row.date, row.split_adjustment_factor,
            row.total_return_adjustment_factor, row.provider_adjusted_close,
            row.methodology_version, row.source_provider, row.computed_at,
        ),
    )


def upsert_adjustment_factors(conn: sqlite3.Connection, rows: list[AdjustmentFactor]) -> None:
    for row in rows:
        upsert_adjustment_factor(conn, row)
    conn.commit()


def get_adjustment_factors(conn: sqlite3.Connection, security_id: str) -> list[AdjustmentFactor]:
    cur = conn.execute(
        "SELECT * FROM adjustment_factors WHERE security_id = ? ORDER BY date", (security_id,)
    )
    return [_row_to_adjustment_factor(r) for r in cur.fetchall()]


def _row_to_adjustment_factor(r: sqlite3.Row) -> AdjustmentFactor:
    return AdjustmentFactor(
        security_id=r["security_id"], date=r["date"],
        split_adjustment_factor=r["split_adjustment_factor"],
        total_return_adjustment_factor=r["total_return_adjustment_factor"],
        provider_adjusted_close=r["provider_adjusted_close"],
        methodology_version=r["methodology_version"], source_provider=r["source_provider"],
        computed_at=r["computed_at"],
    )


def insert_corporate_action(conn: sqlite3.Connection, row: CorporateAction) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO corporate_actions
            (action_id, security_id, action_type, announcement_date, effective_date,
             value, source_provider, source_status, source_status_date, ingestion_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.action_id, row.security_id, row.action_type, row.announcement_date,
            row.effective_date, row.value, row.source_provider, row.source_status,
            row.source_status_date, row.ingestion_timestamp,
        ),
    )


def insert_corporate_actions(conn: sqlite3.Connection, rows: list[CorporateAction]) -> None:
    for row in rows:
        insert_corporate_action(conn, row)
    conn.commit()


def get_corporate_actions(conn: sqlite3.Connection, security_id: str) -> list[CorporateAction]:
    cur = conn.execute(
        "SELECT * FROM corporate_actions WHERE security_id = ? ORDER BY effective_date", (security_id,)
    )
    return [_row_to_corporate_action(r) for r in cur.fetchall()]


def _row_to_corporate_action(r: sqlite3.Row) -> CorporateAction:
    return CorporateAction(
        action_id=r["action_id"], security_id=r["security_id"], action_type=r["action_type"],
        announcement_date=r["announcement_date"], effective_date=r["effective_date"],
        value=r["value"], source_provider=r["source_provider"], source_status=r["source_status"],
        source_status_date=r["source_status_date"], ingestion_timestamp=r["ingestion_timestamp"],
    )


def insert_listing_status(conn: sqlite3.Connection, row: ListingStatusEntry) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO listing_status_history
            (security_id, status, effective_from, effective_to, source_provider, delisting_reason)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (row.security_id, row.status, row.effective_from, row.effective_to,
         row.source_provider, row.delisting_reason),
    )
    conn.commit()


def close_listing_status(conn: sqlite3.Connection, security_id: str, effective_from: str, effective_to: str) -> None:
    conn.execute(
        """UPDATE listing_status_history SET effective_to = ?
           WHERE security_id = ? AND effective_from = ? AND effective_to IS NULL""",
        (effective_to, security_id, effective_from),
    )
    conn.commit()


def get_listing_status_history(conn: sqlite3.Connection, security_id: str) -> list[ListingStatusEntry]:
    cur = conn.execute(
        "SELECT * FROM listing_status_history WHERE security_id = ? ORDER BY effective_from", (security_id,)
    )
    return [_row_to_listing_status(r) for r in cur.fetchall()]


def _row_to_listing_status(r: sqlite3.Row) -> ListingStatusEntry:
    return ListingStatusEntry(
        security_id=r["security_id"], status=r["status"], effective_from=r["effective_from"],
        effective_to=r["effective_to"], source_provider=r["source_provider"],
        delisting_reason=r["delisting_reason"],
    )


def upsert_qa_result(conn: sqlite3.Connection, row: QAResult) -> None:
    import json
    conn.execute(
        """
        INSERT OR REPLACE INTO qa_results
            (security_id, date, qa_pass, reason_codes, severities, computed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            row.security_id, row.date, int(row.qa_pass),
            json.dumps(row.reason_codes), json.dumps(row.severities), row.computed_at,
        ),
    )


def upsert_qa_results(conn: sqlite3.Connection, rows: list[QAResult]) -> None:
    for row in rows:
        upsert_qa_result(conn, row)
    conn.commit()


def get_qa_results(conn: sqlite3.Connection, security_id: str) -> list[QAResult]:
    import json
    cur = conn.execute(
        "SELECT * FROM qa_results WHERE security_id = ? ORDER BY date", (security_id,)
    )
    return [
        QAResult(
            security_id=r["security_id"], date=r["date"], qa_pass=bool(r["qa_pass"]),
            reason_codes=json.loads(r["reason_codes"]), severities=json.loads(r["severities"]),
            computed_at=r["computed_at"],
        )
        for r in cur.fetchall()
    ]
