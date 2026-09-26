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

It also excludes an action once its CANCELLED status is knowable
(source_status_date <= as_of) -- see _is_action_known_for_adjustment().
GPT Review #001 (2026-09-21, commit 8492ade) found this gate missing:
derive_corporate_action_pit_status() correctly reported CANCELLED, but
the adjustment recomputation ignored cancellation entirely, so a
cancelled split/dividend could still alter the adjusted price series
even though the metadata said it never executed (TEST 14, PATCH A).

listing_status_history gets the same available_at knowledge-time field
as corporate_actions (GPT Review #001 PATCH B, 2026-09-21) -- see
get_listing_status_as_of() and PITListingStatus. Deliberately minimal:
no ANNOUNCED-style intermediate phase, just KNOWN/UNKNOWN gating on the
one nullable field, to avoid building two different PIT models in the
same foundation (TEST 15).
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
    back to effective_date alone (see derive_corporate_action_pit_status).

    Also excludes an action once its cancellation is knowable
    (source_status == CANCELLED and as_of >= source_status_date), mirroring
    derive_corporate_action_pit_status's own CANCELLED branch (GPT Review
    #001 PATCH A, 2026-09-21 -- previously this function ignored
    cancellation entirely, so an action correctly reported CANCELLED by
    the status-derivation function could still leak into compute_factors()
    and alter the adjusted price series; see TEST 14). Symmetric with
    status derivation: for an as_of BEFORE the cancellation is knowable, a
    still-pending action is treated normally (a PIT-simulated researcher
    at that earlier as_of wouldn't yet know it would later be cancelled)."""
    if action.effective_date > as_of:
        return False
    if action.available_at is not None and action.available_at > as_of:
        return False
    if action.source_status == "CANCELLED" and action.source_status_date and as_of >= action.source_status_date:
        return False
    return True


@dataclass(frozen=True)
class PITCorporateAction:
    action: CorporateAction
    pit_status: str
    knowledge_time_status: str


@dataclass(frozen=True)
class PITPriceBar:
    """PATCH #001-D (Split-Adjusted OHLC Completion, GPT Review #005
    scaffold blocker A): `split_adjusted_open/high/low` complete the
    split-adjusted OHLC representation that only `split_adjusted_close`
    (and `split_adjusted_volume`, PATCH #001-C) previously covered. Same
    per-date `split_adjustment_factor` already used for
    `split_adjusted_close`, applied identically -- no new adjustment
    methodology, no schema change (still derived on-the-fly here, never
    stored). A split scales price uniformly across open/high/low/close
    (Level 1's own multiplicative methodology has no field-specific
    component), so this is a mechanical extension, not a new formula."""
    date: str
    raw_open: Optional[float]
    raw_high: Optional[float]
    raw_low: Optional[float]
    raw_close: Optional[float]
    raw_volume: Optional[int]
    split_adjusted_open: Optional[float]
    split_adjusted_high: Optional[float]
    split_adjusted_low: Optional[float]
    split_adjusted_close: Optional[float]
    split_adjusted_volume: Optional[float]
    total_return_adjusted_close: Optional[float]
    total_return_status: str


@dataclass(frozen=True)
class PITSnapshot:
    security_id: str
    as_of: str
    ticker: Optional[str]
    listing_status: Optional[str]
    listing_knowledge_time_status: Optional[str]
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


@dataclass(frozen=True)
class PITListingStatus:
    entry: ListingStatusEntry
    knowledge_time_status: str


def get_listing_status_as_of(conn, security_id: str, as_of: str) -> Optional[PITListingStatus]:
    """Same available_at-first, effective_from-fallback policy as
    derive_corporate_action_pit_status (GPT Review #001 PATCH B,
    2026-09-21). Deliberately minimal -- no announcement/status
    lifecycle, no ANNOUNCED-style intermediate phase: an entry is either
    knowable (its effective window applies AND, if available_at is set,
    as_of has reached it) or it isn't considered at all.

    Known minimal-scope gap (see docs/known_limitations.md): if a status
    transition's available_at hasn't been reached yet, this may return
    None (no applicable status) rather than carrying the previous status
    forward, even though the previous entry's own effective_to has
    technically already passed. Extending that is a deliberately
    out-of-scope lifecycle feature, not built here."""
    applicable = None
    for entry in repo.get_listing_status_history(conn, security_id):
        if entry.available_at is not None and entry.available_at > as_of:
            continue  # not yet knowable, even if its effective window would otherwise match
        if entry.effective_from <= as_of and (entry.effective_to is None or as_of < entry.effective_to):
            applicable = entry
    if applicable is None:
        return None
    knowledge_time_status = (
        KnowledgeTimeStatus.KNOWN.value if applicable.available_at is not None
        else KnowledgeTimeStatus.UNKNOWN.value
    )
    return PITListingStatus(entry=applicable, knowledge_time_status=knowledge_time_status)


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
        # split_adjusted_volume (PATCH #001-C, Radu's correction,
        # 2026-09-21): the INVERSE of the price direction, using the
        # same PIT-safe split_factor as split_adjusted_close. A 4-for-1
        # forward split scales historical price down by split_factor=0.25
        # (post-split shares are worth ~1/4); the same split scales
        # historical volume UP by dividing by that factor (raw_volume/0.25
        # = 4x), since post-split there are 4x as many shares for the same
        # dollar turnover. Derived on-the-fly here, exactly like
        # split_adjusted_close -- no schema change, raw_volume untouched.
        #
        # split_adjusted_open/high/low (PATCH #001-D, GPT Review #005
        # scaffold blocker A, 2026-09-26): the SAME split_factor applied
        # to raw_open/raw_high/raw_low -- a split scales the entire OHLC
        # bar uniformly, there is no separate open/high/low-specific
        # methodology. Multiplying every field by the same positive
        # scalar preserves ordering (low <= open,close <= high stays true
        # after scaling), and the same as_of-scoped `factors` computation
        # above already makes this knowledge-time-safe with zero extra
        # code -- no new PIT logic, just applying an existing PIT-safe
        # factor to three more fields.
        result.append(PITPriceBar(
            date=b.date, raw_open=b.raw_open, raw_high=b.raw_high, raw_low=b.raw_low,
            raw_close=b.raw_close, raw_volume=b.raw_volume,
            split_adjusted_open=b.raw_open * split_factor if b.raw_open is not None else None,
            split_adjusted_high=b.raw_high * split_factor if b.raw_high is not None else None,
            split_adjusted_low=b.raw_low * split_factor if b.raw_low is not None else None,
            split_adjusted_close=b.raw_close * split_factor if b.raw_close is not None else None,
            split_adjusted_volume=b.raw_volume / split_factor if b.raw_volume is not None else None,
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
        listing_status=listing.entry.status if listing else None,
        listing_knowledge_time_status=listing.knowledge_time_status if listing else None,
        delisting_reason=listing.entry.delisting_reason if listing else None,
        prices=get_price_series_as_of(conn, security_id, as_of),
        corporate_actions=get_corporate_actions_as_of(conn, security_id, as_of),
        qa_pass_by_date={r.date: r.qa_pass for r in qa_rows},
    )
