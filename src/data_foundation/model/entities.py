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
    ingestion_timestamp: str


@dataclass(frozen=True)
class ListingStatusEntry:
    security_id: str
    status: str
    effective_from: str
    effective_to: Optional[str]
    source_provider: str
    delisting_reason: Optional[str]


@dataclass(frozen=True)
class QAResult:
    security_id: str
    date: str
    qa_pass: bool
    reason_codes: list[str]
    severities: list[str]
    computed_at: str
