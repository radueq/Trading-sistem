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
source_status_date, available_at). derive_corporate_action_pit_status()
computes NOT_KNOWN / ANNOUNCED / EFFECTIVE / CANCELLED fresh for the
given as_of every time this module is called, so the same stored row can
never change meaning based on which wall-clock day ingestion happened to
run.

Knowledge-time policy (Radu's correction, 2026-09-21): three time axes
are kept strictly separate and must never be conflated:
  - effective/event time  (`effective_date` -- when the event actually happened)
  - available/knowledge time (`available_at` -- when it first became
    knowable to our system; NULLable)
  - ingestion time (`ingestion_timestamp` -- pure audit/provenance
    metadata: when WE happened to load this row)

`ingestion_timestamp` must NEVER be used as a stand-in for knowledge
time. If it were, a split from 2020 downloaded today would appear
"unknown" back in 2020 -- obviously wrong, since the split really was
public knowledge in 2020 regardless of when our system got around to
ingesting it.

When `available_at` is known, PIT status gates on it directly (info
cannot be exposed before `available_at`). When `available_at` is NULL
(true for every yfinance-sourced action at Level 1 -- yfinance supplies
no announcement date), we do NOT guess: derive_corporate_action_pit_status
falls back to gating on `effective_date` alone (the Level 1 behavior that
predates this correction), but every result is tagged
`knowledge_time_status = UNKNOWN` so nobody downstream can mistake this
approximation for validated, research-grade PIT correctness. Before
Level 3, any UNKNOWN case that could actually affect PIT research must be
resolved with real provider/announcement data, not left as a permanent
shortcut.

Adjustment factors are likewise recomputed here from an as_of-scoped
corporate-actions set rather than read from adjustment_engine's
precomputed, full-history table -- see get_price_series_as_of(). That
precomputed table reflects today's best knowledge and would leak future
corporate actions into a PIT-simulated historical price if used directly
here (SS12, TEST 9). The as_of scoping now also respects available_at
when present, not just effective_date: a corporate action that only
became knowable after its own effective_date (a retroactively-disclosed
case) must not be reflected in the adjusted price series before it was
actually knowable either.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from data_foundation.model import repository as repo
from data_foundation.model.adjustment_engine import TOTAL_RETURN_STATUS, compute_factors, split_dividend_actions
from data_foundation.model.entities import (
    CorporateAction,
    KnowledgeTimeStatus,
    ListingStatusEntry,
    PITCorporateActionStatus,
)


def derive_corporate_action_pit_status(action: CorporateAction, as_of: str) -> tuple[str, str]:
    """Returns (pit_status, knowledge_time_status).

    knowledge_time_status is KNOWN when the derivation is backed by a
    validated knowledge-time signal (available_at, or source_status_date
    for a cancellation) and UNKNOWN when it rests on the Level 1
    effective_date-only fallback -- see module docstring.
    """
    if action.source_status == "CANCELLED" and action.source_status_date and as_of >= action.source_status_date:
        # Driven by its own dated fact (source_status_date), independent
        # of whether available_at happens to be set on the underlying action.
        return PITCorporateActionStatus.CANCELLED.value, KnowledgeTimeStatus.KNOWN.value

    if action.available_at is not None:
        if as_of < action.available_at:
            return PITCorporateActionStatus.NOT_KNOWN.value, KnowledgeTimeStatus.KNOWN.value
        if as_of < action.effective_date:
            return PITCorporateActionStatus.ANNOUNCED.value, KnowledgeTimeStatus.KNOWN.value
        return PITCorporateActionStatus.EFFECTIVE.value, KnowledgeTimeStatus.KNOWN.value

    # available_at is NULL: no validated knowledge-time signal exists.
    # Level 1 fallback -- gate on effective_date alone (never
    # ingestion_timestamp), with no ANNOUNCED phase (we have no evidence
    # one was ever observable). Always tagged UNKNOWN.
    if as_of >= action.effective_date:
        return PITCorporateActionStatus.EFFECTIVE.value, KnowledgeTimeStatus.UNKNOWN.value
    return PITCorporateActionStatus.NOT_KNOWN.value, KnowledgeTimeStatus.UNKNOWN.value


def _is_action_known_for_adjustment(action: CorporateAction, as_of: str) -> bool:
    """An action may only affect the as_of-scoped adjusted price series
    once it has both actually happened (effective_date <= as_of) AND, if
    a validated knowledge-time signal exists, been knowable
    (available_at <= as_of). Without a validated signal, Level 1 falls
    back to effective_date alone (see derive_corporate_action_pit_status)."""
    if action.effective_date > as_of:
        return False
    if action.available_at is not None and action.available_at > as_of:
        return False
    return True


@dataclass(frozen=True)
class PITCorporateAction:
    action: CorporateAction
    pit_status: str
    knowledge_time_status: str


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
    total_return_status: str


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
        status, knowledge_time_status = derive_corporate_action_pit_status(action, as_of)
        if status == PITCorporateActionStatus.NOT_KNOWN.value:
            continue  # not yet knowable as of this simulated moment -- never exposed
        result.append(PITCorporateAction(
            action=action, pit_status=status, knowledge_time_status=knowledge_time_status,
        ))
    return result


def get_price_series_as_of(conn, security_id: str, as_of: str) -> list[PITPriceBar]:
    bars = [b for b in repo.get_price_history(conn, security_id) if b.date <= as_of]
    dates = [b.date for b in bars]
    close_by_date = {b.date: b.raw_close for b in bars}

    # Adjustment factors must be recomputed from an as_of-scoped action
    # set, NOT read from the precomputed full-history adjustment_factors
    # table -- see module docstring.
    known_actions = [
        a for a in repo.get_corporate_actions(conn, security_id) if _is_action_known_for_adjustment(a, as_of)
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
            total_return_status=TOTAL_RETURN_STATUS,
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
