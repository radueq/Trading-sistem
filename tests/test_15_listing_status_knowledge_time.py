"""TEST 15 -- Listing status knowledge-time (GPT Review #001, commit
8492ade -- PATCH B).

A status with effective_from < available_at must not become visible
before available_at. Deliberately minimal, mirroring TEST 13's approach
for corporate actions: only the one nullable field, no full
announcement/status lifecycle for listings.
"""
from data_foundation.model import ingestion as ing, repository as repo
from data_foundation.model.entities import ListingStatus, ListingStatusEntry, SecurityMaster
from data_foundation.pit import access as pit


def _make_security(conn, seed: str, now: str) -> str:
    sid = ing.new_security_id(seed)
    repo.insert_security_master(conn, SecurityMaster(
        security_id=sid, security_type="EQUITY", primary_exchange=None, currency="USD",
        source_provider="manual", source_security_id=seed, ingestion_timestamp=now,
    ))
    return sid


def test_listing_status_hidden_before_available_at(conn, now):
    sid = _make_security(conn, "test15:retroactive_delisting", now)

    # the delisting really happened 2019-03-01, but our system (or the
    # market) only confirmed/learned about it on 2019-03-20
    repo.insert_listing_status(conn, ListingStatusEntry(
        security_id=sid, status=ListingStatus.DELISTED.value,
        effective_from="2019-03-01", effective_to=None,
        source_provider="manual", delisting_reason="retroactively confirmed bankruptcy",
        available_at="2019-03-20",
    ))

    # after effective_from but before available_at: not yet knowable
    before = pit.get_data(conn, sid, as_of="2019-03-10")
    assert before.listing_status is None
    assert before.listing_knowledge_time_status is None
    assert before.delisting_reason is None

    # at available_at: now visible, tagged KNOWN
    at_available = pit.get_data(conn, sid, as_of="2019-03-20")
    assert at_available.listing_status == ListingStatus.DELISTED.value
    assert at_available.listing_knowledge_time_status == "KNOWN"
    assert at_available.delisting_reason == "retroactively confirmed bankruptcy"


def test_listing_status_available_at_null_is_tagged_unknown(conn, now):
    """available_at=NULL preserves the pre-patch effective_from-only
    behavior, explicitly tagged UNKNOWN (not silently treated as KNOWN)."""
    sid = _make_security(conn, "test15:no_knowledge_time_signal", now)
    repo.insert_listing_status(conn, ListingStatusEntry(
        security_id=sid, status=ListingStatus.ACTIVE.value,
        effective_from="2020-01-01", effective_to=None,
        source_provider="manual", delisting_reason=None, available_at=None,
    ))

    snapshot = pit.get_data(conn, sid, as_of="2020-06-01")
    assert snapshot.listing_status == ListingStatus.ACTIVE.value
    assert snapshot.listing_knowledge_time_status == "UNKNOWN"
