"""SQLite connection + schema init. Level 1 prototype persistence.

Deliberately plain sqlite3 -- no ORM. Per spec principle #26 (correctness +
auditability + modularity before sophistication), we don't build DB
infrastructure this module doesn't need yet. Migrating to Postgres later
only requires replacing this module, since nothing upstream should depend
on sqlite specifics.

NO MIGRATION PATH at Level 1 (accepted explicitly, GPT Final Review #001,
2026-09-21 -- see schema.sql's SCHEMA_VERSION note): init_schema() runs
`CREATE TABLE IF NOT EXISTS`, which does nothing to a table that already
exists under an older shape -- it will NOT add a newly-introduced column
to an existing on-disk database file. A schema change requires deleting
and recreating the SQLite file, not migrating one in place. There is
currently no persisted database file anywhere in this repository worth
migrating (every test uses `:memory:`), so this is a real but currently
inert gap -- revisit with a proper migration mechanism before any Level 1
database is expected to persist across a schema change.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def connect(db_path: str) -> sqlite3.Connection:
    """Open a connection with FK enforcement and row access by name."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    schema_sql = _SCHEMA_PATH.read_text()
    conn.executescript(schema_sql)
    conn.commit()


def connect_and_init(db_path: str) -> sqlite3.Connection:
    conn = connect(db_path)
    init_schema(conn)
    return conn
