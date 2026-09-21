"""Standard Internal Data Model -- dataclasses for the 7 schema components.

These are plain data carriers. No business logic (adjustment math, PIT
filtering, QA) lives here -- that's adjustment engine / pit / qa modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SecurityType(str, Enum):
    EQUITY = "EQUITY"


class ActionType(str, Enum):
    SPLIT = "SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    DIVIDEND = "DIVIDEND"
    MERGER = "MERGER"
    ACQUISITION = "ACQUISITION"
    SPINOFF = "SPINOFF"
    OTHER = "OTHER"


class ListingStatus(str, Enum):
    PRE_IPO = "PRE_IPO"
    ACTIVE = "ACTIVE"
    HALTED = "HALTED"
    SUSPENDED = "SUSPENDED"
    DELISTED = "DELISTED"


class PITCorporateActionStatus(str, Enum):
    """Derived (never stored) status -- see pit/access.py."""
    NOT_KNOWN = "NOT_KNOWN"
    ANNOUNCED = "ANNOUNCED"
    EFFECTIVE = "EFFECTIVE"
    CANCELLED = "CANCELLED"


class KnowledgeTimeStatus(str, Enum):
    """Whether a PIT status derivation is backed by a validated
    available_at signal (KNOWN) or by the Level 1 effective_date-only
    fallback (UNKNOWN) -- Radu's correction, 2026-09-21. UNKNOWN must
    never be presented as research-grade PIT correctness; before Level 3
    it should be resolved via provider/date data wherever it could
    affect PIT research."""
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SecurityMaster:
    security_id: str
    security_type: str
    primary_exchange: Optional[str]
    currency: Optional[str]
    source_provider: str
    source_security_id: str
    ingestion_timestamp: str


@dataclass(frozen=True)
class SymbolHistoryEntry:
    security_id: str
    ticker: str
    exchange: Optional[str]
    valid_from: str
    valid_to: Optional[str]
    source_provider: str


@dataclass(frozen=True)
class PriceBar:
    security_id: str
    date: str
    raw_open: Optional[float]
    raw_high: Optional[float]
    raw_low: Optional[float]
    raw_close: Optional[float]
    raw_volume: Optional[int]
    source_provider: str
    ingestion_timestamp: str


@dataclass(frozen=True)
class AdjustmentFactor:
    security_id: str
    date: str
    split_adjustment_factor: float
    total_return_adjustment_factor: float
    total_return_status: str  # see adjustment_engine.TOTAL_RETURN_STATUS
    provider_adjusted_close: Optional[float]
    methodology_version: str
    source_provider: str
    computed_at: str


@dataclass(frozen=True)
class CorporateAction:
    action_id: str
    security_id: str
    action_type: str
    announcement_date: Optional[str]
    effective_date: str
    value: Optional[float]
    source_provider: str
    source_status: Optional[str]
    source_status_date: Optional[str]
    # Knowledge-time: when this action's effect first became knowable to
    # our system, distinct from announcement_date (a business fact about
    # the real-world event) and from ingestion_timestamp (pure audit
    # metadata, see model/ingestion.py). NULL means we have no validated
    # signal for it -- never substitute ingestion_timestamp or
    # announcement_date's absence with a guess (Radu's correction,
    # 2026-09-21). See pit/access.py for how NULL is handled at query time.
    available_at: Optional[str]
    ingestion_timestamp: str
    # Pure audit: when this row was first ingested vs when it was last
    # revised (repository.upsert_corporate_action preserves
    # ingestion_timestamp across revisions and bumps this field instead --
    # GPT Final Review #001, 2026-09-21). Never used by PIT derivation.
    last_updated_timestamp: str


@dataclass(frozen=True)
class ListingStatusEntry:
    security_id: str
    status: str
    effective_from: str
    effective_to: Optional[str]
    source_provider: str
    delisting_reason: Optional[str]
    # Same knowledge-time pattern as CorporateAction.available_at (GPT
    # Review #001 PATCH B, 2026-09-21): NULL means no validated signal,
    # pit/access.py falls back to effective_from/effective_to alone,
    # tagged UNKNOWN.
    available_at: Optional[str]
    # Same audit pattern as CorporateAction.last_updated_timestamp (GPT
    # Final Review #001, 2026-09-21).
    last_updated_timestamp: str


@dataclass(frozen=True)
class QAResult:
    security_id: str
    date: str
    qa_pass: bool
    reason_codes: list[str]
    severities: list[str]
    computed_at: str
