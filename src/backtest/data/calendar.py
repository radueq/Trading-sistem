"""Spec #005 v1.0 SS11 -- calendar-input contract and fail-closed gate
(Batch 1).

RELOCATED (joint remediation design 003+004, section 2; decision
registry B4, revision 5; authorized 2026-10-06, Stage 2): the actual
implementation now lives in `data_foundation.calendar.contract`, so
both `evaluation` (Spec #003) and `backtest` (Spec #005) can import it
without `evaluation` ever needing to import `backtest`. Every name
below is re-exported UNCHANGED -- a pure relocation, not a behavior
change -- so every existing import site (`from backtest.data.calendar
import ...`) keeps working without modification.
"""
from __future__ import annotations

from data_foundation.calendar.contract import (
    build_trading_calendar,
    is_session,
    require_calendar_covers_window,
    require_verified_calendar_for_formal_run,
)

__all__ = [
    "build_trading_calendar",
    "is_session",
    "require_calendar_covers_window",
    "require_verified_calendar_for_formal_run",
]
