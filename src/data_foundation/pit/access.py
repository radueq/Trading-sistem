"""Point-in-Time Access Layer -- Spec #001 SS10-13.

This module is the SOLE gateway to data for any downstream research
consumer (Discovery Engine, Candidate Selector, Hypothesis Engine,
Backtester, Evaluation Engine). No such consumer may query
data_foundation.model.repository directly (SS10-11) -- storage/adapter
tests are the one carve-out, and only for testing storage/the adapter
itself (Radu's clarification on SS10-11), never as a stand-in for a
downstream consumer.

get_data(security_id, as_of) is the single entry point. Everything else
in this module is a building block it composes.

Corporate action status is NEVER stored (Radu's correction to Spec #001
SS8/28, 2026-09-20): corporate_actions rows hold only persisted temporal
facts (announcement_date, effective_date, source_status,
source_status_date). derive_corporate_action_pit_status() computes
NOT_KNOWN / ANNOUNCED / EFFECTIVE / CANCELLED fresh for the given as_of
every time this module is called, so the same stored row can never
change meaning based on which wall-clock day ingestion happened to run.

Adjustment factors are likewise recomputed here from an as_of-scoped
corporate-actions set (effective_date <= as_of only) rather than read
from adjustment_engine's precomputed, full-history table -- see
get_price_series_as_of(). That precomputed table reflects today's best
knowledge and would leak future corporate actions into a PIT-simulated
historical price if used directly here (SS12, TEST 9).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from data_foundation.model import repository as repo
from data_foundation.model.adjustment_engine import compute_factors, split_dividend_actions
from data_foundation.model.entities import CorporateAction, ListingStatusEntry, PITCorporateActionStatus


def derive_corporate_action_pit_status(action: CorporateAction, as_of: str) -> str:
    if action.source_status == "CANCELLED" and action.source_status_date and as_of >= action.source_status_date:
        return PITCorporateActionStatus.CANCELLED.value

    if action.announcement_date and as_of >= action.announcement_date:
        if as_of >= action.effective_date:
            return PITCorporateActionStatus.EFFECTIVE.value
        return PITCorporateActionStatus.ANNOUNCED.value

    # No announcement_date fact available (e.g. yfinance never supplies
    # one) -- but if the event's effective_date has itself already
    # passed relative to as_of, the event has objectively already
    # happened and is knowable, so it is at least EFFECTIVE.
    if as_of >= action.effective_date:
        return PITCorporateActionStatus.EFFECTIVE.value

    return PITCorporateActionStatus.NOT_KNOWN.value


@dataclass(frozen=True)
class PITCorporateAction:
    action: CorporateAction
    pit_status: str


@dataclass(frozen=True)
class PITPriceBar:
    date: str
    raw_open: Optional[float]
    raw_high: Optional[float]
    raw_low: Optional[float]
    raw_close: Optional[float]
    raw_volume: Optional[int]
    split_adjusted_close: Optional[float]
    total_return_adjusted_close: Optional[float]


@dataclass(frozen=True)
class PITSnapshot:
    security_id: str
    as_of: str
    ticker: Optional[str]
    listing_status: Optional[str]
    delisting_reason: Optional[str]
    prices: list[PITPriceBar]
    corporate_actions: list[PITCorporateAction]
    qa_pass_by_date: dict[str, bool]


def get_ticker_as_of(conn, security_id: str, as_of: str) -> Optional[str]:
    """Answers 'what ticker did this security_id have at date t' (SS4)."""
    for entry in repo.get_symbol_history_for_security(conn, security_id):
        if entry.valid_from <= as_of and (entry.valid_to is None or as_of < entry.valid_to):
            return entry.ticker
    return None


def get_security_id_for_ticker_as_of(conn, ticker: str, as_of: str) -> Optional[str]:
    """Answers 'what security did this ticker represent at date t' (SS4).
    Correctly disambiguates ticker reuse: only the era whose
    [valid_from, valid_to) window contains as_of is returned."""
    for entry in repo.get_symbol_history_for_ticker(conn, ticker):
        if entry.valid_from <= as_of and (entry.valid_to is None or as_of < entry.valid_to):
            return entry.security_id
    return None


def get_listing_status_as_of(conn, security_id: str, as_of: str) -> Optional[ListingStatusEntry]:
    applicable = None
    for entry in repo.get_listing_status_history(conn, security_id):
        if entry.effective_from <= as_of and (entry.effective_to is None or as_of < entry.effective_to):
            applicable = entry
    return applicable


def get_corporate_actions_as_of(conn, security_id: str, as_of: str) -> list[PITCorporateAction]:
    result = []
    for action in repo.get_corporate_actions(conn, security_id):
        status = derive_corporate_action_pit_status(action, as_of)
        if status == PITCorporateActionStatus.NOT_KNOWN.value:
            continue  # not yet knowable as of this simulated moment -- never exposed
        result.append(PITCorporateAction(action=action, pit_status=status))
    return result


def get_price_series_as_of(conn, security_id: str, as_of: str) -> list[PITPriceBar]:
    bars = [b for b in repo.get_price_history(conn, security_id) if b.date <= as_of]
    dates = [b.date for b in bars]
    close_by_date = {b.date: b.raw_close for b in bars}

    # Adjustment factors must be recomputed from an as_of-scoped action
    # set (effective_date <= as_of), NOT read from the precomputed
    # full-history adjustment_factors table -- see module docstring.
    known_actions = [
        a for a in repo.get_corporate_actions(conn, security_id) if a.effective_date <= as_of
    ]
    split_actions, dividend_actions = split_dividend_actions(known_actions)
    factors = compute_factors(dates, close_by_date, split_actions, dividend_actions)

    result = []
    for b in bars:
        split_factor, total_return_factor = factors[b.date]
        result.append(PITPriceBar(
            date=b.date, raw_open=b.raw_open, raw_high=b.raw_high, raw_low=b.raw_low,
            raw_close=b.raw_close, raw_volume=b.raw_volume,
            split_adjusted_close=b.raw_close * split_factor if b.raw_close is not None else None,
            total_return_adjusted_close=b.raw_close * total_return_factor if b.raw_close is not None else None,
        ))
    return result


def get_data(conn, security_id: str, as_of: str) -> PITSnapshot:
    """THE single gateway entry point for downstream consumers."""
    listing = get_listing_status_as_of(conn, security_id, as_of)
    qa_rows = [r for r in repo.get_qa_results(conn, security_id) if r.date <= as_of]
    return PITSnapshot(
        security_id=security_id,
        as_of=as_of,
        ticker=get_ticker_as_of(conn, security_id, as_of),
        listing_status=listing.status if listing else None,
        delisting_reason=listing.delisting_reason if listing else None,
        prices=get_price_series_as_of(conn, security_id, as_of),
        corporate_actions=get_corporate_actions_as_of(conn, security_id, as_of),
        qa_pass_by_date={r.date: r.qa_pass for r in qa_rows},
    )
