"""TEST 8 -- Provider consistency (Spec #001 SS23).

Requires comparing the same instrument/period across two providers.
Level 1 runs a single provider (yfinance); a second provider adapter is
out of scope until Level 2/3. Approved by Radu (2026-09-20) to remain
PENDING_LEVEL_2_DATA rather than claim a false PASS.
"""
import pytest


def test_provider_consistency_pending_level_2_data():
    pytest.skip(
        "PENDING_LEVEL_2_DATA: only one provider (yfinance) is implemented at "
        "Level 1; cross-provider comparison needs a second adapter, deferred to "
        "Level 2/3 per Radu's approval (2026-09-20)."
    )
