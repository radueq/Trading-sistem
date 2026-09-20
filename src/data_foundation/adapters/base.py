"""Provider Adapter contract (Spec #001 SS18).

Each provider gets its own adapter implementing this interface. Adapters
translate provider-shaped data into provider-agnostic "Raw*" carriers.
They do NOT assign internal security_id (cross-provider identity
resolution is an ingestion-orchestration concern, not an adapter
concern -- a single adapter call has no way to know whether a ticker
maps to a security already known under a different provider).

Adapter contract (non-negotiable, Spec #001 SS18):
  1. receives provider data
  2. maps identifiers (ticker -> source_security_id)
  3. converts into the internal raw schema shapes below
  4. declares unavailable fields explicitly (unavailable_fields lists)
  5. never invents values for missing fields
  6. preserves provider/source metadata (provider name, ingestion timestamp)

No module outside adapters/ may contain `if provider == "X":` branching
(Spec #001 SS19) -- provider quirks are handled here and nowhere else.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class RawSecurityInfo:
    source_security_id: str
    security_type: Optional[str]
    primary_exchange: Optional[str]
    currency: Optional[str]
    unavailable_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RawPriceBar:
    source_security_id: str
    date: str  # ISO YYYY-MM-DD
    raw_open: Optional[float]
    raw_high: Optional[float]
    raw_low: Optional[float]
    raw_close: Optional[float]
    raw_volume: Optional[int]
    provider_adjusted_close: Optional[float]


@dataclass(frozen=True)
class RawCorporateActionEvent:
    source_security_id: str
    action_type: str
    announcement_date: Optional[str]
    effective_date: str
    value: Optional[float]
    source_status: Optional[str]
    source_status_date: Optional[str]


class ProviderAdapter(ABC):
    provider_name: str

    @abstractmethod
    def fetch_security_info(self, ticker: str) -> RawSecurityInfo:
        ...

    @abstractmethod
    def fetch_price_history(self, ticker: str, start: str, end: str) -> list[RawPriceBar]:
        ...

    @abstractmethod
    def fetch_corporate_actions(self, ticker: str, start: str, end: str) -> list[RawCorporateActionEvent]:
        ...
