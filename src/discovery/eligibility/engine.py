"""Universe Eligibility engine (Spec #002 SS29).

Kept explicitly separate from Data QA (Spec #001 SS2) and from
Discovery: eligibility decides whether we WANT to consider an
instrument at all (a system-design constraint), never whether an
observation is trustworthy (that's QA) and never how noteworthy its
current state is (that's Discovery). Rules are minimum floors, never a
narrow target range -- Radu's explicit decision that e.g. a market-cap
rule must never mean "select companies around $1-2B."
"""
from __future__ import annotations

from typing import Optional

from discovery.models.entities import EligibilityResult

# No PIT market cap field exists anywhere in the Spec #001 Data
# Foundation schema (security_master has no such column). Never
# fabricated -- always reported PENDING_DATA at Level 1, and eligibility
# proceeds on the other dimensions regardless of eligibility.yaml's
# market_cap_floor value (Spec #002 SS29).
MARKET_CAP_FILTER_STATUS = "PENDING_DATA"


def evaluate_eligibility(
    security_id: str,
    as_of: str,
    latest_close: Optional[float],
    history_days: int,
    latest_adv_20: Optional[float],
    primary_exchange: Optional[str],
    config: dict,
) -> EligibilityResult:
    failed: list[str] = []

    min_price = config.get("minimum_price")
    if min_price is not None and (latest_close is None or latest_close < min_price):
        failed.append("MINIMUM_PRICE")

    min_history = config.get("minimum_history_days")
    if min_history is not None and history_days < min_history:
        failed.append("MINIMUM_HISTORY")

    min_adv = config.get("minimum_adv_20")
    if min_adv is not None and (latest_adv_20 is None or latest_adv_20 < min_adv):
        failed.append("MINIMUM_LIQUIDITY")

    allowed_exchanges = config.get("allowed_exchanges")
    if allowed_exchanges and primary_exchange not in allowed_exchanges:
        failed.append("EXCHANGE_ELIGIBILITY")

    return EligibilityResult(
        security_id=security_id, as_of=as_of, eligible=(len(failed) == 0),
        failed_rules=failed, market_cap_filter_status=MARKET_CAP_FILTER_STATUS,
    )
