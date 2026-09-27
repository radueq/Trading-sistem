"""Spec #005 v1.0 SS3/SS6 -- bounded PIT access facade (Batch 2).

"Selection must not inspect or hash validation/OOS price content. A plan
can commit future window boundaries without opening those data." This
module is the ONLY way #005's own code (snapshotting, historical
observation caching, and later batches' signal/execution logic) may
reach #001's PIT gateway (`data_foundation.pit.access`) -- never a
direct import of that module elsewhere under `src/backtest/`.

#001's `get_price_series_as_of()` (and the other PIT functions) has no
LOWER `as_of` bound: it always returns everything on file up to `as_of`.
This means bounding the single UPPER edge is both necessary and
sufficient to guarantee no fact dated after a stage's own boundary can
ever be read through this facade -- see
`backtest.models.entities.StageAccessBoundary`.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from data_foundation.pit import access as pit
from data_foundation.pit.access import PITCorporateAction, PITListingStatus, PITPriceBar

from backtest.models.entities import StageAccessBoundary


class BoundedPITAccess:
    """Wraps every #001 PIT read #005 needs with one `StageAccessBoundary`
    check, performed BEFORE delegating -- if `as_of` is out of scope, the
    underlying #001 call is never made and nothing is logged. `access_log`
    records every ACCEPTED query as `(kind, security_id, as_of)`, both for
    `backtest.data.snapshot`'s table/field manifest and so a test can
    assert this object never queried outside its declared scope (the
    "access spy" Spec #005 SS23's Isolation family requires)."""

    def __init__(self, conn, boundary: StageAccessBoundary):
        self.conn = conn
        self._boundary = boundary
        self.access_log: list[tuple[str, str, str]] = []

    @property
    def boundary(self) -> StageAccessBoundary:
        """Read-only: a plain public attribute could be reassigned to a
        wider boundary after construction, silently defeating the whole
        guarantee this object exists to provide. There is no legitimate
        reason to swap it after construction -- callers who need a
        different scope construct a new `BoundedPITAccess`."""
        return self._boundary

    def _accept(self, kind: str, security_id: str, as_of: str) -> None:
        self._boundary.require_as_of_in_scope(as_of)
        self.access_log.append((kind, security_id, as_of))

    def get_price_series_as_of(self, security_id: str, as_of: str) -> list[PITPriceBar]:
        self._accept("PRICE_BARS", security_id, as_of)
        return pit.get_price_series_as_of(self.conn, security_id, as_of)

    def get_corporate_actions_as_of(self, security_id: str, as_of: str) -> list[PITCorporateAction]:
        self._accept("CORPORATE_ACTIONS", security_id, as_of)
        return pit.get_corporate_actions_as_of(self.conn, security_id, as_of)

    def get_listing_status_as_of(self, security_id: str, as_of: str) -> Optional[PITListingStatus]:
        self._accept("LISTING_STATUS", security_id, as_of)
        return pit.get_listing_status_as_of(self.conn, security_id, as_of)

    def get_ticker_as_of(self, security_id: str, as_of: str) -> Optional[str]:
        self._accept("SYMBOL_HISTORY", security_id, as_of)
        return pit.get_ticker_as_of(self.conn, security_id, as_of)


def build_authorized_price_subset_connection(conn, boundary: StageAccessBoundary) -> sqlite3.Connection:
    """Batch 2 patch round-3 review (P1 finding): checking that a
    returned `DiscoveryObservation.as_of` label equals the requested
    session date (see `backtest.data.cache`) cannot catch code that
    reads out-of-scope price data internally and then reports an
    honest label anyway -- that supervises the OUTPUT, not the actual
    READS. This builds a temporary, in-memory COPY of `conn` with every
    `price_history` row dated after `boundary.max_as_of` physically
    removed, and hands THAT to third-party PIT-consuming code (e.g.
    `discovery.engine.compute_discovery_observations()`) instead of the
    raw stage connection -- so even a caller that ignores its own
    `as_of` parameter and queries with a larger one internally still
    cannot reach that data: it is not present in the copy at all.

    Other tables are copied unfiltered: every #001 PIT function that
    reads them (`get_ticker_as_of`, `get_listing_status_as_of`) already
    self-restricts correctly from its OWN `as_of` argument.
    `get_price_series_as_of()` is the one gap a caller-supplied `as_of`
    cannot self-enforce (it trusts whatever `as_of` it is given), which
    is exactly what this subset closes. The caller is responsible for
    closing the returned connection."""
    subset = sqlite3.connect(":memory:")
    subset.row_factory = conn.row_factory
    conn.backup(subset)
    subset.execute("DELETE FROM price_history WHERE date > ?", (boundary.max_as_of,))
    subset.commit()
    return subset
