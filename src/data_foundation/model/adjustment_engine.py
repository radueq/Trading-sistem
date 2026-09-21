"""Adjustment engine -- computes split-adjusted and total-return factors.

Spec #001 SS6 requires raw / split-adjusted / total-return to be three
distinct, non-confused series. This module derives the latter two from
raw price_history + corporate_actions. It never touches raw_* values.

Methodology (v1_backward_multiplicative), documented for audit (Spec #001
SS6 "metodologia exactă ... va fi explicită"):

  split_adjustment_factor(t) = product, over every SPLIT/REVERSE_SPLIT
  action with effective_date > t, of (1 / ratio).
  ratio is expressed as new-shares-per-old-share (e.g. 4.0 for a 4-for-1
  forward split, 0.2 for a 1-for-5 reverse split) -- the same formula
  direction is correct for both, since a forward split's ratio > 1 drives
  the factor below 1 (scale historical prices down to match the lower
  post-split price level) and a reverse split's ratio < 1 drives the
  factor above 1 (scale historical prices up).

  total_return_adjustment_factor(t) = split_adjustment_factor(t) *
  product, over every DIVIDEND with effective_date (ex-date) > t, of
  (1 - dividend_value / raw_close(previous trading date before ex-date)).

  Known simplification (Level 1, see docs/known_limitations.md): the
  dividend ratio denominator uses the RAW close on the prior trading day,
  not a split-adjusted close. When a split and a dividend fall close
  together for the same security this slightly misstates the combined
  factor; none of the Level 1 fixtures exercise that overlap. A more
  precise v2 methodology would use the split-adjusted prior close.

provider_adjusted_close is carried through unmodified from whatever the
provider reported (if anything) -- kept for audit/comparison only, never
used as an input to the two factors above (Spec #001 SS6).

TOTAL_RETURN_STATUS (Radu's correction, 2026-09-21): the dividend-
reinvestment math above has not been validated against real provider or
reference total-return data -- every computed row is explicitly marked
EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH so it can never be silently
mistaken for a validated series. split_adjustment_factor carries no such
caveat; it remains available as-is (TEST 2 validates it directly).
"""
from __future__ import annotations

from data_foundation.model import repository as repo
from data_foundation.model.entities import ActionType, AdjustmentFactor

METHODOLOGY_VERSION = "v1_backward_multiplicative"
TOTAL_RETURN_STATUS = "EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH"


def _previous_trading_date(sorted_dates: list[str], date: str) -> str | None:
    prev = None
    for d in sorted_dates:
        if d >= date:
            break
        prev = d
    return prev


def split_dividend_actions(actions) -> tuple[list, list]:
    split_actions = [a for a in actions if a.action_type in (ActionType.SPLIT.value, ActionType.REVERSE_SPLIT.value)]
    dividend_actions = [a for a in actions if a.action_type == ActionType.DIVIDEND.value]
    return split_actions, dividend_actions


def compute_factors(
    dates: list[str], close_by_date: dict[str, float | None], split_actions: list, dividend_actions: list,
) -> dict[str, tuple[float, float]]:
    """Pure function: date -> (split_adjustment_factor, total_return_adjustment_factor).

    Shared by the full-history batch path below AND by pit/access.py,
    which calls this with an as_of-scoped `dates` list and an
    as_of-scoped `split_actions`/`dividend_actions` (effective_date <=
    as_of only) -- that scoping is what makes a PIT-simulated adjusted
    price immune to corporate actions ingested after the fact (TEST 9).
    """
    result: dict[str, tuple[float, float]] = {}
    for d in dates:
        split_factor = 1.0
        for a in split_actions:
            if a.effective_date > d and a.value:
                split_factor *= 1.0 / a.value

        total_return_factor = split_factor
        for a in dividend_actions:
            if a.effective_date > d and a.value:
                prior_date = _previous_trading_date(dates, a.effective_date)
                prior_close = close_by_date.get(prior_date) if prior_date else None
                if prior_close and prior_close > 0:
                    total_return_factor *= max(0.0, 1.0 - (a.value / prior_close))

        result[d] = (split_factor, total_return_factor)
    return result


def compute_adjustment_factors(
    conn, security_id: str, provider_adjusted_close_by_date: dict[str, float] | None = None,
) -> list[AdjustmentFactor]:
    """Full-history ("latest known") factors -- NOT PIT-safe. This is a
    convenience view for today's research use (e.g. "give me AAPL's
    best-known adjusted series right now"), recomputed whenever new
    corporate actions are ingested. A PIT-simulated historical query must
    NOT read this table -- see pit/access.py, which recomputes factors
    from an as_of-scoped action set instead."""
    provider_adjusted_close_by_date = provider_adjusted_close_by_date or {}
    bars = repo.get_price_history(conn, security_id)
    actions = repo.get_corporate_actions(conn, security_id)

    dates = [b.date for b in bars]
    close_by_date = {b.date: b.raw_close for b in bars}
    split_actions, dividend_actions = split_dividend_actions(actions)
    factors = compute_factors(dates, close_by_date, split_actions, dividend_actions)

    rows = []
    for d in dates:
        split_factor, total_return_factor = factors[d]
        rows.append(AdjustmentFactor(
            security_id=security_id, date=d,
            split_adjustment_factor=split_factor,
            total_return_adjustment_factor=total_return_factor,
            total_return_status=TOTAL_RETURN_STATUS,
            provider_adjusted_close=provider_adjusted_close_by_date.get(d),
            methodology_version=METHODOLOGY_VERSION,
            source_provider=bars[0].source_provider if bars else "unknown",
            computed_at=_now_iso(),
        ))
    return rows


def compute_and_store_adjustment_factors(
    conn, security_id: str, provider_adjusted_close_by_date: dict[str, float] | None = None,
) -> list[AdjustmentFactor]:
    rows = compute_adjustment_factors(conn, security_id, provider_adjusted_close_by_date)
    repo.upsert_adjustment_factors(conn, rows)
    return rows


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
