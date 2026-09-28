"""TEST 22 -- ATR basis reconciliation between the signal session and the
entry session (docs/spec005_exit_amendment_v1.0.md, ACCEPTED, section 3),
including the exact worked example from the accepted document and its
paired "same-day, no evidence" rejection.

`atr_window=3` (not the real 14) is used throughout, mirroring Spec #002
TEST 7's own established convention: Wilder's recursive method was
specifically chosen so a SMALL synthetic OHLC sequence stays
hand-verifiable, and this test exploits exactly that.
"""
import pytest

from backtest.exits.protection import check_new_splits_authorized_at_open, compute_atr_basis_reconciliation, compute_atr_from_bars

from spec005.fixtures.pit_universe import insert_corporate_action, make_security
from data_foundation.model import repository as repo
from data_foundation.model.entities import PriceBar
from data_foundation.pit.access import PITPriceBar

_VOL_CFG = {"atr_window": 3, "bb_window": 3, "bb_num_std": 2.0, "realized_vol_window": 3}


def _bar(date: str, raw_h: float, raw_l: float, raw_c: float, adj_h: float, adj_l: float, adj_c: float) -> PITPriceBar:
    return PITPriceBar(
        date=date, raw_open=raw_c, raw_high=raw_h, raw_low=raw_l, raw_close=raw_c, raw_volume=1000,
        split_adjusted_open=adj_c, split_adjusted_high=adj_h, split_adjusted_low=adj_l,
        split_adjusted_close=adj_c, split_adjusted_volume=1000.0,
        total_return_adjusted_close=adj_c, total_return_status="EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH",
    )


class _UnboundedAccess:
    """A trivial stand-in for BoundedPITAccess with no StageAccessBoundary
    check -- these tests exercise `protection.py`'s own reconciliation
    logic directly, not the Batch 2 scope-boundary machinery (already
    covered by tests/spec005/test_14-15)."""
    def __init__(self, conn):
        self.conn = conn

    def get_price_series_as_of(self, security_id, as_of):
        from data_foundation.pit import access as pit
        return pit.get_price_series_as_of(self.conn, security_id, as_of)

    def get_corporate_actions_as_of(self, security_id, as_of):
        from data_foundation.pit import access as pit
        return pit.get_corporate_actions_as_of(self.conn, security_id, as_of)


def _insert_flat_range_bars(conn, security_id, now, dates, high, low, close):
    repo.insert_price_bars(conn, [
        PriceBar(
            security_id=security_id, date=d, raw_open=close, raw_high=high, raw_low=low, raw_close=close,
            raw_volume=1000, source_provider="manual", ingestion_timestamp=now,
        )
        for d in dates
    ])


def test_worked_example_split_same_day_as_entry_with_evidence(conn, now):
    """ACCEPTED document section 3's exact worked example: ATR_14(s)=4
    pre-split; a 2-for-1 split effective the SAME day as entry, known
    before that day's open (explicit evidence supplied); F_e=50
    (post-split basis) -> ATR reexpressed = 4*(1/2.0) = 2."""
    sec = make_security(conn, "spec005:ATR_RECON_A", now)
    # 3 bars, each true range = 4 (high-low=4, no close-to-close gap
    # exceeding that range) -> Wilder seed (window=3) = mean(4,4,4) = 4.
    _insert_flat_range_bars(conn, sec, now, ["2024-01-08", "2024-01-09", "2024-01-10"], high=102.0, low=98.0, close=100.0)
    signal_date = "2024-01-10"
    entry_date = "2024-01-11"
    insert_corporate_action(
        conn, sec, "act_split_1", "SPLIT", effective_date=entry_date, value=2.0, now=now,
        available_at=entry_date,
    )
    pit = _UnboundedAccess(conn)

    atr, diagnostics = compute_atr_basis_reconciliation(
        pit, sec, signal_date, entry_date, same_day_evidence=frozenset({"act_split_1"}), volatility_config=_VOL_CFG,
    )
    assert atr == 2.0, diagnostics


def test_same_configuration_without_evidence_is_rejected(conn, now):
    """Same exact configuration, but WITHOUT the explicit same-day
    evidence -- section 3's paired case: "aceeași zi, oră necunoscută"
    must NOT authorize at open. NO_VALID_STOP_BASIS (signaled here as
    atr is None), never a silent 42-style price/ATR-basis mismatch."""
    sec = make_security(conn, "spec005:ATR_RECON_B", now)
    _insert_flat_range_bars(conn, sec, now, ["2024-01-08", "2024-01-09", "2024-01-10"], high=102.0, low=98.0, close=100.0)
    signal_date = "2024-01-10"
    entry_date = "2024-01-11"
    insert_corporate_action(
        conn, sec, "act_split_2", "SPLIT", effective_date=entry_date, value=2.0, now=now,
        available_at=entry_date,
    )
    pit = _UnboundedAccess(conn)

    atr, diagnostics = compute_atr_basis_reconciliation(
        pit, sec, signal_date, entry_date, same_day_evidence=frozenset(), volatility_config=_VOL_CFG,
    )
    assert atr is None
    assert "act_split_2" in diagnostics


def test_split_strictly_before_entry_auto_authorizes_without_evidence(conn, now):
    """A split effective strictly BEFORE the entry session (not the same
    day) never needs same-day evidence at all -- section 3's "strict
    anterior" branch."""
    sec = make_security(conn, "spec005:ATR_RECON_C", now)
    _insert_flat_range_bars(conn, sec, now, ["2024-01-08", "2024-01-09", "2024-01-10"], high=102.0, low=98.0, close=100.0)
    signal_date = "2024-01-10"
    effective_date = "2024-01-11"  # strictly between signal and entry
    entry_date = "2024-01-12"
    insert_corporate_action(
        conn, sec, "act_split_3", "SPLIT", effective_date=effective_date, value=2.0, now=now,
        available_at=effective_date,
    )
    pit = _UnboundedAccess(conn)

    atr, diagnostics = compute_atr_basis_reconciliation(
        pit, sec, signal_date, entry_date, same_day_evidence=frozenset(), volatility_config=_VOL_CFG,
    )
    assert atr == 2.0, diagnostics


def test_no_split_between_signal_and_entry_reexpresses_to_the_same_value(conn, now):
    """No split at all between s and entry -> ratio is 1.0, ATR unchanged."""
    sec = make_security(conn, "spec005:ATR_RECON_D", now)
    _insert_flat_range_bars(conn, sec, now, ["2024-01-08", "2024-01-09", "2024-01-10"], high=102.0, low=98.0, close=100.0)
    signal_date = "2024-01-10"
    entry_date = "2024-01-11"
    pit = _UnboundedAccess(conn)

    atr, diagnostics = compute_atr_basis_reconciliation(
        pit, sec, signal_date, entry_date, same_day_evidence=frozenset(), volatility_config=_VOL_CFG,
    )
    assert atr == 4.0, diagnostics


def test_insufficient_history_for_atr_window_is_rejected(conn, now):
    sec = make_security(conn, "spec005:ATR_RECON_E", now)
    _insert_flat_range_bars(conn, sec, now, ["2024-01-09", "2024-01-10"], high=102.0, low=98.0, close=100.0)  # only 2 bars, window=3
    pit = _UnboundedAccess(conn)

    atr, diagnostics = compute_atr_basis_reconciliation(
        pit, sec, "2024-01-10", "2024-01-11", same_day_evidence=frozenset(), volatility_config=_VOL_CFG,
    )
    assert atr is None
    assert diagnostics == ("INSUFFICIENT_HISTORY_FOR_ATR_WINDOW",)


# --------------------------------------------------------------------------
# GPT review round 2, finding #1: the temporal-access-at-open check must
# apply to the KNOWLEDGE date (available_at, or its effective_date
# fallback), never to effective_date directly.
# --------------------------------------------------------------------------

def test_available_at_before_effective_date_same_day_auto_authorizes(conn, now):
    """A split ANNOUNCED yesterday but EFFECTIVE today needs no evidence
    at all -- the previous, buggy implementation required it anyway,
    because it checked effective_date instead of the knowledge date."""
    sec = make_security(conn, "spec005:ATR_KNOW_A", now)
    signal_date, entry_date = "2024-01-05", "2024-01-11"
    insert_corporate_action(
        conn, sec, "act_know_a", "SPLIT", effective_date=entry_date, value=2.0, now=now,
        available_at="2024-01-10",  # known a day BEFORE the effective/entry date
    )
    pit = _UnboundedAccess(conn)
    authorized, blocking = check_new_splits_authorized_at_open(pit, sec, signal_date, entry_date, same_day_evidence=frozenset())
    assert authorized, blocking


def test_effective_earlier_but_available_same_day_requires_evidence(conn, now):
    """A split EFFECTIVE several days ago but only KNOWN (available_at)
    today needs the same same-day scrutiny a same-day-effective split
    would -- the previous implementation auto-authorized this (it only
    ever looked at effective_date, which was already in the past)."""
    sec = make_security(conn, "spec005:ATR_KNOW_B", now)
    signal_date, entry_date = "2024-01-05", "2024-01-11"
    insert_corporate_action(
        conn, sec, "act_know_b", "SPLIT", effective_date="2024-01-08", value=2.0, now=now,
        available_at=entry_date,  # only became knowable on the entry date itself
    )
    pit = _UnboundedAccess(conn)

    without_evidence, blocking = check_new_splits_authorized_at_open(pit, sec, signal_date, entry_date, same_day_evidence=frozenset())
    assert not without_evidence
    assert "act_know_b" in blocking

    with_evidence, blocking2 = check_new_splits_authorized_at_open(pit, sec, signal_date, entry_date, same_day_evidence=frozenset({"act_know_b"}))
    assert with_evidence, blocking2


# --------------------------------------------------------------------------
# GPT review round 2, finding #3: ATR must be computed on an internally
# COHERENT basis -- split_adjusted_high/low/close together, never raw
# high/low mixed with split-adjusted close (which would inject an
# artificial true-range spike at any split inside the window).
# --------------------------------------------------------------------------

def test_split_within_the_atr_window_does_not_distort_atr():
    """d1 is pre-split (raw levels ~200), d2/d3 are post a 2-for-1 split
    (raw levels ~100). On the split-adjusted basis, d1 rescales to match
    d2/d3's post-split scale -- a clean, flat 4-point range throughout,
    matching what a fully-adjusted, split-aware calculation must show.
    (On the RAW-only, buggy basis this project's Batch-3 code previously
    used, the d1->d2 transition would show a true range of 102, from the
    unadjusted ~200->~100 price-level halving -- an artifact of the split,
    not real volatility.)"""
    bars = [
        _bar("d1", raw_h=204.0, raw_l=196.0, raw_c=200.0, adj_h=102.0, adj_l=98.0, adj_c=100.0),
        _bar("d2", raw_h=102.0, raw_l=98.0, raw_c=100.0, adj_h=102.0, adj_l=98.0, adj_c=100.0),
        _bar("d3", raw_h=103.0, raw_l=99.0, raw_c=101.0, adj_h=103.0, adj_l=99.0, adj_c=101.0),
    ]
    atr = compute_atr_from_bars(bars, volatility_config=_VOL_CFG)
    assert atr == pytest.approx(4.0)


def test_reverse_split_within_the_atr_window_does_not_distort_atr():
    """d1 pre-reverse-split (raw levels ~100), d2/d3 post a 1-for-2
    reverse split (raw levels ~200, doubled). On the split-adjusted
    basis, d1 rescales UP to match -- a clean, flat 8-point range."""
    bars = [
        _bar("d1", raw_h=102.0, raw_l=98.0, raw_c=100.0, adj_h=204.0, adj_l=196.0, adj_c=200.0),
        _bar("d2", raw_h=204.0, raw_l=196.0, raw_c=200.0, adj_h=204.0, adj_l=196.0, adj_c=200.0),
        _bar("d3", raw_h=205.0, raw_l=197.0, raw_c=201.0, adj_h=205.0, adj_l=197.0, adj_c=201.0),
    ]
    atr = compute_atr_from_bars(bars, volatility_config=_VOL_CFG)
    assert atr == pytest.approx(8.0)


def test_dividend_within_the_atr_window_is_never_treated_as_an_adjustment():
    """A dividend produces a real, legitimate ex-dividend price move in
    raw prices -- it must NOT be smoothed away (split_adjusted_* is
    purely split-driven, by construction; this confirms the ATR module
    never accidentally reacts to a non-split action)."""
    bars = [
        _bar("d1", raw_h=102.0, raw_l=98.0, raw_c=100.0, adj_h=102.0, adj_l=98.0, adj_c=100.0),
        _bar("d2", raw_h=99.0, raw_l=95.0, raw_c=97.0, adj_h=99.0, adj_l=95.0, adj_c=97.0),  # ex-div drop, real
        _bar("d3", raw_h=100.0, raw_l=96.0, raw_c=98.0, adj_h=100.0, adj_l=96.0, adj_c=98.0),
    ]
    atr_adjusted_basis = compute_atr_from_bars(bars, volatility_config=_VOL_CFG)
    raw_only_bars = [_bar(b.date, b.raw_high, b.raw_low, b.raw_close, b.raw_high, b.raw_low, b.raw_close) for b in bars]
    atr_raw_basis = compute_atr_from_bars(raw_only_bars, volatility_config=_VOL_CFG)
    assert atr_adjusted_basis == pytest.approx(atr_raw_basis)
