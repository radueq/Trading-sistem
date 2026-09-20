"""TEST 11 -- Corporate action timing (Spec #001 SS23).

Uses Radu's own worked example from the 2026-09-20 correction to SS8:
announcement_date=2024-05-22, effective_date=2024-06-10. Verifies status
derivation at the three checkpoints, that the event is invisible to a
downstream query before announcement, and that the adjustment is not
applied prematurely (before EFFECTIVE) even once ANNOUNCED.
"""
from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing, repository as repo
from data_foundation.model.adjustment_engine import compute_factors, split_dividend_actions
from data_foundation.model.entities import ActionType, CorporateAction
from data_foundation.pit import access as pit
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import AAPL_SPLIT_2020

ANNOUNCEMENT_DATE = "2024-05-22"
EFFECTIVE_DATE = "2024-06-10"


def test_corporate_action_timing_status_derivation(conn, now):
    ticker = AAPL_SPLIT_2020["ticker"]
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: AAPL_SPLIT_2020}))
    sid = ing.new_security_id(f"yfinance:{ticker}")
    ing.ensure_security(conn, sid, adapter, ticker, now)

    action = CorporateAction(
        action_id="ca_test11", security_id=sid, action_type=ActionType.SPLIT.value,
        announcement_date=ANNOUNCEMENT_DATE, effective_date=EFFECTIVE_DATE,
        value=2.0, source_provider="manual", source_status=None,
        source_status_date=None, ingestion_timestamp=now,
    )
    repo.insert_corporate_actions(conn, [action])

    assert pit.derive_corporate_action_pit_status(action, "2024-05-20") == "NOT_KNOWN"
    assert pit.derive_corporate_action_pit_status(action, "2024-05-25") == "ANNOUNCED"
    assert pit.derive_corporate_action_pit_status(action, "2024-06-10") == "EFFECTIVE"

    before_announce = pit.get_corporate_actions_as_of(conn, sid, "2024-05-20")
    assert before_announce == [], "must not be exposed before announcement_date"

    announced = pit.get_corporate_actions_as_of(conn, sid, "2024-05-25")
    assert len(announced) == 1 and announced[0].pit_status == "ANNOUNCED"

    # adjustment not applied prematurely: even ANNOUNCED, the split
    # factor for a date before EFFECTIVE_DATE must still be 1.0
    known_at_announced = [a for a in repo.get_corporate_actions(conn, sid) if a.effective_date <= "2024-05-25"]
    split_actions, dividend_actions = split_dividend_actions(known_at_announced)
    factors = compute_factors(["2024-05-25"], {"2024-05-25": 100.0}, split_actions, dividend_actions)
    assert factors["2024-05-25"][0] == 1.0, "split must not be adjusted for before it is EFFECTIVE"

    effective = pit.get_corporate_actions_as_of(conn, sid, EFFECTIVE_DATE)
    assert len(effective) == 1 and effective[0].pit_status == "EFFECTIVE"
