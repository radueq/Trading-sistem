"""TEST 22 -- ATR basis reconciliation between the signal session and the
entry session (docs/spec005_exit_amendment_v1.0.md, ACCEPTED, section 3),
including the exact worked example from the accepted document and its
paired "same-day, no evidence" rejection.

`atr_window=3` (not the real 14) is used throughout, mirroring Spec #002
TEST 7's own established convention: Wilder's recursive method was
specifically chosen so a SMALL synthetic OHLC sequence stays
hand-verifiable, and this test exploits exactly that.
"""
from backtest.exits.protection import compute_atr_basis_reconciliation

from spec005.fixtures.pit_universe import insert_corporate_action, make_security
from data_foundation.model import repository as repo
from data_foundation.model.entities import PriceBar

_VOL_CFG = {"atr_window": 3, "bb_window": 3, "bb_num_std": 2.0, "realized_vol_window": 3}


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
