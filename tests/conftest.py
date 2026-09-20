import pytest

from data_foundation.adapters.yfinance_adapter import utc_now_iso
from data_foundation.storage.db import connect_and_init


@pytest.fixture
def conn():
    c = connect_and_init(":memory:")
    yield c
    c.close()


@pytest.fixture
def now():
    return utc_now_iso()
