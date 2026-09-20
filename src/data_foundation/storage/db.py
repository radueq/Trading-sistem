"""SQLite connection + schema init. Level 1 prototype persistence.

Deliberately plain sqlite3 -- no ORM. Per spec principle #26 (correctness +
auditability + modularity before sophistication), we don't build DB
infrastructure this module doesn't need yet. Migrating to Postgres later
only requires replacing this module, since nothing upstream should depend
on sqlite specifics.
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
