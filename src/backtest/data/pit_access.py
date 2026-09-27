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

Batch 2 patch round-4 review (P1 finding #1, `build_authorized_
subset_connection()` below): the round-3 subset builder used
`conn.backup(subset)` (a full byte-level copy of EVERY row, including
OOS prices and every other security) followed by a `DELETE` of the rows
that turned out to be out of scope -- an independent probe on the
extracted function confirmed the forbidden rows were genuinely present
before that DELETE ran, and that only `price_history`'s upper bound was
ever filtered at all: a corporate action knowable only after
`max_as_of`, and prices for a security outside the authorized universe,
both survived untouched. This function now builds an EMPTY schema (via
`data_foundation.storage.db.init_schema()`) and `INSERT`s only rows that
were already authorized at read time -- `security_id` scoped to the
declared universe/benchmark on every table, plus each table's own
appropriate knowledge-time upper bound. Nothing forbidden is ever
copied in the first place."""
from __future__ import annotations

import sqlite3
from typing import Optional

from data_foundation.pit import access as pit
from data_foundation.pit.access import PITCorporateAction, PITListingStatus, PITPriceBar
from data_foundation.storage.db import init_schema

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


def build_authorized_subset_connection(
    conn, boundary: StageAccessBoundary, security_ids: tuple[str, ...],
) -> sqlite3.Connection:
    """Checking that a returned `DiscoveryObservation.as_of` label
    equals the requested session date (see `backtest.data.cache`)
    cannot catch code that reads out-of-scope data internally and then
    reports an honest label anyway -- that supervises the OUTPUT, not
    the actual READS. This builds a fresh, EMPTY in-memory database
    (same schema, via `init_schema()`) and copies in only rows that were
    already authorized: `security_id IN security_ids` on every table,
    plus each table's own knowledge-time upper bound at
    `boundary.max_as_of`. Nothing outside that domain is ever written
    into the copy, so a caller that ignores its own `as_of` parameter
    (or reads a security never in scope) still finds nothing to read.

    No LOWER date bound is applied to any table -- `price_history`/
    `corporate_actions` legitimately need arbitrarily old warm-up data
    for #001's own rolling adjustment-factor computation (SS3: "Warm-up
    data before a zone may be read..."), and `symbol_history`/
    `listing_status_history` must retain whatever old entry is still
    the ACTIVE one at any in-scope `as_of` -- #001's own PIT functions
    walk each security's full retained history to resolve that,
    regardless of how far back it starts. Only the read-domain's OWN
    caller-facing edges (a `StageAccessBoundary`'s `max_as_of`, and
    `backtest.data.cache`/`backtest.data.snapshot`'s own `min_as_of`
    checks) restrict how far back an `as_of` QUERY may itself reach.

    Per-table filter:
    - `security_master`: `security_id` scope only (no knowledge-time
      field exists at all, see `backtest.data.snapshot`).
    - `symbol_history`: `security_id` scope, `valid_from <= max_as_of`
      -- a ticker rename effective only in the future must not be
      physically present.
    - `price_history`: `security_id` scope, `date <= max_as_of`.
    - `corporate_actions`: `security_id` scope, and knowable-by-
      `max_as_of` (`available_at` when set, else falling back to
      `effective_date` -- mirroring `derive_corporate_action_pit_status`/
      `_is_action_known_for_adjustment`'s own knowledge-time policy in
      `data_foundation.pit.access`, so nothing physically present here
      could ever change what those functions already compute correctly
      -- this is defense in depth, not a second, independent PIT model).
    - `listing_status_history`: same knowledge-time pattern, falling
      back to `effective_from` when `available_at` is NULL.

    `adjustment_factors`/`qa_results` are never copied: nothing #005
    reads through this connection (`compute_discovery_observations()`,
    `build_data_snapshot()`) touches either table. The caller is
    responsible for closing the returned connection."""
    subset = sqlite3.connect(":memory:")
    subset.row_factory = conn.row_factory
    init_schema(subset)
    ids = tuple(security_ids)
    if not ids:
        return subset
    max_as_of = boundary.max_as_of
    placeholders = ",".join("?" for _ in ids)

    rows = conn.execute(
        f"SELECT * FROM security_master WHERE security_id IN ({placeholders})", ids,
    ).fetchall()
    subset.executemany("INSERT INTO security_master VALUES (?,?,?,?,?,?,?)", [tuple(r) for r in rows])

    rows = conn.execute(
        f"SELECT * FROM symbol_history WHERE security_id IN ({placeholders}) AND valid_from <= ?",
        (*ids, max_as_of),
    ).fetchall()
    subset.executemany("INSERT INTO symbol_history VALUES (?,?,?,?,?,?)", [tuple(r) for r in rows])

    rows = conn.execute(
        f"SELECT * FROM price_history WHERE security_id IN ({placeholders}) AND date <= ?",
        (*ids, max_as_of),
    ).fetchall()
    subset.executemany("INSERT INTO price_history VALUES (?,?,?,?,?,?,?,?,?)", [tuple(r) for r in rows])

    rows = conn.execute(
        f"SELECT * FROM corporate_actions WHERE security_id IN ({placeholders}) AND "
        f"(CASE WHEN available_at IS NOT NULL THEN available_at ELSE effective_date END) <= ?",
        (*ids, max_as_of),
    ).fetchall()
    subset.executemany("INSERT INTO corporate_actions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [tuple(r) for r in rows])

    rows = conn.execute(
        f"SELECT * FROM listing_status_history WHERE security_id IN ({placeholders}) AND "
        f"(CASE WHEN available_at IS NOT NULL THEN available_at ELSE effective_from END) <= ?",
        (*ids, max_as_of),
    ).fetchall()
    subset.executemany("INSERT INTO listing_status_history VALUES (?,?,?,?,?,?,?,?)", [tuple(r) for r in rows])

    subset.commit()
    return subset
