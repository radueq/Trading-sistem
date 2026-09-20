"""TEST 4 -- Delisting PIT (Spec #001 SS23).

Before the delisting event, get_data() must reflect the information
available at that simulated moment (ACTIVE, no delisting reason). After
delisting, status must reflect the event. No hindsight leakage.
"""
from data_foundation.adapters.yfinance_adapter import YFinanceAdapter
from data_foundation.model import ingestion as ing, repository as repo
from data_foundation.model.entities import ListingStatus, ListingStatusEntry
from data_foundation.pit import access as pit
from fixtures.fake_yfinance import make_ticker_factory
from fixtures.market_data import DELISTING


def test_delisting_pit_no_hindsight_leakage(conn, now):
    ticker = DELISTING["ticker"]
    adapter = YFinanceAdapter(ticker_factory=make_ticker_factory({ticker: DELISTING}))
    sid = ing.new_security_id(f"yfinance:{ticker}")
    ing.ensure_security(conn, sid, adapter, ticker, now)
    start, end = DELISTING["bars"][0]["date"], DELISTING["bars"][-1]["date"]
    ing.ingest_prices(conn, adapter, sid, ticker, start, end, now)

    active_from = DELISTING["bars"][0]["date"]
    delisted_from = DELISTING["delisted_effective"]
    repo.insert_listing_status(conn, ListingStatusEntry(
        security_id=sid, status=ListingStatus.ACTIVE.value,
        effective_from=active_from, effective_to=delisted_from,
        source_provider="manual", delisting_reason=None,
    ))
    repo.insert_listing_status(conn, ListingStatusEntry(
        security_id=sid, status=ListingStatus.DELISTED.value,
        effective_from=delisted_from, effective_to=None,
        source_provider="manual", delisting_reason=DELISTING["delisting_reason"],
    ))

    before = pit.get_data(conn, sid, as_of="2019-01-10")
    assert before.listing_status == ListingStatus.ACTIVE.value
    assert before.delisting_reason is None

    # right up to the last active day: still ACTIVE, no leakage of the
    # delisting that is already sitting in the store dated a day later
    boundary = pit.get_data(conn, sid, as_of="2019-01-15")
    assert boundary.listing_status == ListingStatus.ACTIVE.value
    assert boundary.delisting_reason is None

    after = pit.get_data(conn, sid, as_of="2019-01-20")
    assert after.listing_status == ListingStatus.DELISTED.value
    assert after.delisting_reason == DELISTING["delisting_reason"]
