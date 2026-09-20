"""Data QA engine -- Spec #001 SS13-15.

Produces qa_pass + reason_codes[] + severity[] per (security_id, date),
never a single clean/suspicious/bad enum. severity->qa_pass is fixed
(ERROR implies qa_pass=FALSE); reason_code->severity is loaded from an
external config (severity_mapping.yaml), not hardcoded (Radu's approval).

Pipeline order this module depends on: run AFTER price/corporate-action
ingestion AND after adjustment_engine.compute_and_store_adjustment_factors
for the same security, since ADJUSTMENT_MISMATCH reads the precomputed
adjustment_factors table.

No silent forward-fill anywhere in this module (Spec #001 SS17): missing
bars are detected and reported as MISSING_BAR, never filled in.

Known Level 1 simplifications (see docs/known_limitations.md):
  - MISSING_BAR uses a plain Mon-Fri weekday calendar, no market holiday
    calendar -- a real holiday would currently be flagged as a false
    positive. Test fixtures avoid real US holidays to keep this
    exercisable without that dependency.
  - DUPLICATE_BAR and SOURCE_DISCREPANCY are structurally wired but
    largely dormant at Level 1: the storage schema's natural key
    (security_id, date, source_provider) already prevents an exact
    same-provider duplicate from persisting, and only one provider
    (yfinance) is active, so there is nothing to cross-compare yet.
    Both become meaningful once Level 2/3 introduces multi-provider
    ingestion or pre-storage batch inspection.
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import date as date_cls, datetime, timedelta, timezone

import yaml

from data_foundation.model import repository as repo
from data_foundation.model.entities import ActionType, QAResult
from data_foundation.qa.reason_codes import ReasonCode, Severity

DEFAULT_SEVERITY_MAPPING_PATH = os.path.join(os.path.dirname(__file__), "config", "severity_mapping.yaml")

# QA-internal tuning parameters. These are Data Quality heuristics, not
# Universe Eligibility thresholds (Spec #001 SS2) -- they decide whether
# an observation looks trustworthy, never whether the system wants to
# trade the instrument.
DEFAULT_GAP_THRESHOLD = 0.5        # 50% day-over-day move outside a known split -> SUSPICIOUS_GAP
DEFAULT_STALE_RUN_LENGTH = 5       # N identical consecutive closes -> STALE_PRICE
DEFAULT_MIN_HISTORY_BARS = 5       # fewer bars than this -> INSUFFICIENT_HISTORY
DEFAULT_ADJUSTMENT_MISMATCH_TOLERANCE = 0.05  # 5% relative divergence -> ADJUSTMENT_MISMATCH


def load_severity_mapping(path: str | None = None) -> dict[str, str]:
    with open(path or DEFAULT_SEVERITY_MAPPING_PATH) as f:
        return yaml.safe_load(f)


def _business_days(start: str, end: str) -> list[str]:
    d0, d1 = date_cls.fromisoformat(start), date_cls.fromisoformat(end)
    out = []
    d = d0
    while d <= d1:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _windows_overlap(from_a: str, to_a: str | None, from_b: str, to_b: str | None) -> bool:
    end_a = to_a or "9999-12-31"
    end_b = to_b or "9999-12-31"
    return from_a < end_b and from_b < end_a


def run_qa_checks(
    conn, security_id: str, severity_mapping: dict[str, str] | None = None,
    gap_threshold: float = DEFAULT_GAP_THRESHOLD,
    stale_run_length: int = DEFAULT_STALE_RUN_LENGTH,
    min_history_bars: int = DEFAULT_MIN_HISTORY_BARS,
    adjustment_mismatch_tolerance: float = DEFAULT_ADJUSTMENT_MISMATCH_TOLERANCE,
) -> list[QAResult]:
    severity_mapping = severity_mapping or load_severity_mapping()
    bars = repo.get_price_history(conn, security_id)  # ordered by date
    actions = repo.get_corporate_actions(conn, security_id)

    findings: dict[str, list[str]] = defaultdict(list)

    # OHLC_INVALID / NEGATIVE_PRICE / ZERO_VOLUME
    for b in bars:
        vals = [b.raw_open, b.raw_high, b.raw_low, b.raw_close]
        if any(v is not None and v < 0 for v in vals):
            findings[b.date].append(ReasonCode.NEGATIVE_PRICE.value)
        if all(v is not None for v in vals):
            o, h, l, c = b.raw_open, b.raw_high, b.raw_low, b.raw_close
            if not (l <= o <= h and l <= c <= h and l <= h):
                findings[b.date].append(ReasonCode.OHLC_INVALID.value)
        if b.raw_volume is not None and b.raw_volume == 0:
            findings[b.date].append(ReasonCode.ZERO_VOLUME.value)

    # MISSING_BAR -- expected weekday calendar within the security's own observed range
    dates_present = {b.date for b in bars}
    if bars:
        for d in _business_days(bars[0].date, bars[-1].date):
            if d not in dates_present:
                findings[d].append(ReasonCode.MISSING_BAR.value)

    # STALE_PRICE -- N consecutive identical raw closes
    run_length, prev_close = 0, None
    for b in bars:
        run_length = run_length + 1 if (prev_close is not None and b.raw_close == prev_close) else 1
        if run_length >= stale_run_length:
            findings[b.date].append(ReasonCode.STALE_PRICE.value)
        prev_close = b.raw_close

    # SUSPICIOUS_GAP -- large day-over-day move NOT explained by a known split/reverse-split
    split_dates = {a.effective_date for a in actions
                   if a.action_type in (ActionType.SPLIT.value, ActionType.REVERSE_SPLIT.value)}
    prev_close = None
    for b in bars:
        if prev_close and prev_close != 0 and b.date not in split_dates and b.raw_close is not None:
            if abs(b.raw_close - prev_close) / prev_close > gap_threshold:
                findings[b.date].append(ReasonCode.SUSPICIOUS_GAP.value)
        prev_close = b.raw_close

    # CORPORATE_ACTION_UNRESOLVED -- conflicting split ratios announced for the same effective_date
    by_date = defaultdict(list)
    for a in actions:
        if a.action_type in (ActionType.SPLIT.value, ActionType.REVERSE_SPLIT.value):
            by_date[a.effective_date].append(a.value)
    for d, ratios in by_date.items():
        if len(set(ratios)) > 1:
            findings[d].append(ReasonCode.CORPORATE_ACTION_UNRESOLVED.value)

    # STATUS_CONFLICT -- overlapping listing_status_history windows for this security
    statuses = repo.get_listing_status_history(conn, security_id)
    for i, s1 in enumerate(statuses):
        for s2 in statuses[i + 1:]:
            if _windows_overlap(s1.effective_from, s1.effective_to, s2.effective_from, s2.effective_to):
                findings[s1.effective_from].append(ReasonCode.STATUS_CONFLICT.value)

    # IDENTIFIER_CONFLICT -- same ticker, overlapping windows, DIFFERENT security_id
    # (legitimate ticker reuse has non-overlapping windows and must NOT flag here)
    for sym in repo.get_symbol_history_for_security(conn, security_id):
        for other in repo.get_symbol_history_for_ticker(conn, sym.ticker):
            if other.security_id == security_id:
                continue
            if _windows_overlap(sym.valid_from, sym.valid_to, other.valid_from, other.valid_to):
                findings[sym.valid_from].append(ReasonCode.IDENTIFIER_CONFLICT.value)

    # INSUFFICIENT_HISTORY -- summary flag surfaced on the most recent observed date
    if bars and len(bars) < min_history_bars:
        findings[bars[-1].date].append(ReasonCode.INSUFFICIENT_HISTORY.value)

    # ADJUSTMENT_MISMATCH -- our total-return-adjusted close vs provider's own adjusted close
    for f in repo.get_adjustment_factors(conn, security_id):
        if f.provider_adjusted_close is None:
            continue
        close = next((b.raw_close for b in bars if b.date == f.date), None)
        if close is None or close == 0:
            continue
        ours = close * f.total_return_adjustment_factor
        if abs(ours - f.provider_adjusted_close) / abs(f.provider_adjusted_close or ours or 1) > adjustment_mismatch_tolerance:
            findings[f.date].append(ReasonCode.ADJUSTMENT_MISMATCH.value)

    computed_at = datetime.now(timezone.utc).isoformat()
    results = []
    for date_key, codes in findings.items():
        severities = [severity_mapping.get(c, Severity.WARNING.value) for c in codes]
        qa_pass = not any(s == Severity.ERROR.value for s in severities)
        results.append(QAResult(security_id=security_id, date=date_key, qa_pass=qa_pass,
                                 reason_codes=codes, severities=severities, computed_at=computed_at))
    for b in bars:
        if b.date not in findings:
            results.append(QAResult(security_id=security_id, date=b.date, qa_pass=True,
                                     reason_codes=[], severities=[], computed_at=computed_at))
    return results


def run_and_store_qa_checks(conn, security_id: str, **kwargs) -> list[QAResult]:
    results = run_qa_checks(conn, security_id, **kwargs)
    repo.upsert_qa_results(conn, results)
    return results
