-- Spec #001 -- Standard Internal Data Schema
-- Raw / factual tables only. No derived or as-of-today status is stored here --
-- derivation for a simulated moment happens exclusively in pit/access.py.
--
-- SCHEMA_VERSION: 3 (2026-09-21, GPT Final Review #001 -- persistence
-- lifecycle patch). Level 1 has NO ALTER TABLE migration path: a schema
-- change (like this one, which adds columns) requires deleting and
-- recreating the SQLite file, not migrating an existing one in place.
-- CREATE TABLE IF NOT EXISTS silently does nothing to a table that
-- already exists under the old shape -- it will NOT add new columns to
-- an old on-disk database. Accepted explicitly for Level 1 (Radu,
-- 2026-09-21): no persisted database exists yet worth migrating, and
-- building migration infrastructure now would be exactly the kind of
-- premature complexity SS26 warns against. Revisit before any Level 1
-- database is expected to persist across a schema change.

CREATE TABLE IF NOT EXISTS security_master (
    security_id         TEXT PRIMARY KEY,
    security_type        TEXT NOT NULL,
    primary_exchange      TEXT,
    currency             TEXT,
    source_provider       TEXT NOT NULL,
    source_security_id     TEXT NOT NULL,
    ingestion_timestamp     TEXT NOT NULL
    -- Deliberately NOT unique on (source_provider, source_security_id):
    -- a ticker is not identity (SS4), so the same provider ticker string
    -- can legitimately belong to two different security_id rows when a
    -- ticker is reused by an unrelated company (TEST 6). source_security_id
    -- here is provenance ("the identifier seen at first ingestion"), not
    -- a dedup key -- assigning security_id is an orchestration decision,
    -- see ingestion.py.
);

CREATE TABLE IF NOT EXISTS symbol_history (
    security_id     TEXT NOT NULL REFERENCES security_master(security_id),
    ticker         TEXT NOT NULL,
    exchange       TEXT,
    valid_from      TEXT NOT NULL,
    valid_to       TEXT,
    source_provider   TEXT NOT NULL,
    PRIMARY KEY (security_id, valid_from)
);
CREATE INDEX IF NOT EXISTS idx_symbol_history_ticker ON symbol_history(ticker);

CREATE TABLE IF NOT EXISTS price_history (
    security_id       TEXT NOT NULL REFERENCES security_master(security_id),
    date            TEXT NOT NULL,
    raw_open         REAL,
    raw_high         REAL,
    raw_low          REAL,
    raw_close         REAL,
    raw_volume        INTEGER,
    source_provider     TEXT NOT NULL,
    ingestion_timestamp   TEXT NOT NULL,
    PRIMARY KEY (security_id, date, source_provider)
);

-- Derived (but auditable/reproducible) adjustment factors. Computed by
-- adjustment_engine.py from corporate_actions + price_history, never
-- overwriting raw_* values in price_history.
--
-- total_return_status marks the total-return series' methodology
-- maturity (Radu's correction, 2026-09-21): currently always
-- 'EXPERIMENTAL_NOT_APPROVED_FOR_RESEARCH' -- the dividend-reinvestment
-- math (adjustment_engine.py) has not been validated against real
-- provider/reference data. split_adjustment_factor carries no such
-- caveat and remains available as-is.
CREATE TABLE IF NOT EXISTS adjustment_factors (
    security_id                   TEXT NOT NULL REFERENCES security_master(security_id),
    date                        TEXT NOT NULL,
    split_adjustment_factor            REAL NOT NULL,
    total_return_adjustment_factor        REAL NOT NULL,
    total_return_status              TEXT NOT NULL,
    provider_adjusted_close             REAL,
    methodology_version              TEXT NOT NULL,
    source_provider                 TEXT NOT NULL,
    computed_at                    TEXT NOT NULL,
    PRIMARY KEY (security_id, date, methodology_version)
);

-- Corporate actions store only persisted temporal FACTS. Status
-- (ANNOUNCED / EFFECTIVE / CANCELLED / NOT_KNOWN) is never materialized
-- here -- it is derived at query time by the PIT access layer against a
-- caller-supplied as_of, so the same row never changes meaning based on
-- the wall-clock day ingestion happened to run.
--
-- available_at is the knowledge-time axis, kept deliberately separate
-- from effective_date (event time) and ingestion_timestamp (pure audit
-- metadata -- see pit/access.py's module docstring for why
-- ingestion_timestamp must never be used as a knowledge-time proxy).
-- NULL means no validated knowledge-time signal exists for this row;
-- Level 1 corporate actions from yfinance (no announcement_date
-- available) always have available_at = NULL (Radu's correction,
-- 2026-09-21).
--
-- Persistence lifecycle (GPT Final Review #001, 2026-09-21): action_id
-- identity is stable, but our KNOWLEDGE of an action can be revised as
-- new information arrives (e.g. pending -> CANCELLED). Writes go
-- through repository.upsert_corporate_action(s), an ENRICHMENT upsert:
-- on conflict (same action_id), only announcement_date/source_status/
-- source_status_date/available_at are updated, and only when the new
-- value is non-NULL (a later fetch that happens to omit a field can
-- never regress an already-known value to unknown). ingestion_timestamp
-- is preserved as "first seen"; last_updated_timestamp records the most
-- recent revision. A plain INSERT OR IGNORE would have silently dropped
-- a real re-ingested cancellation forever (TEST 14c); a blind INSERT OR
-- REPLACE would have destroyed the first-seen ingestion_timestamp.
CREATE TABLE IF NOT EXISTS corporate_actions (
    action_id            TEXT PRIMARY KEY,
    security_id           TEXT NOT NULL REFERENCES security_master(security_id),
    action_type           TEXT NOT NULL,
    announcement_date        TEXT,
    effective_date          TEXT NOT NULL,
    value               REAL,
    source_provider         TEXT NOT NULL,
    source_status          TEXT,
    source_status_date       TEXT,
    available_at           TEXT,
    ingestion_timestamp       TEXT NOT NULL,
    last_updated_timestamp     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_security ON corporate_actions(security_id);

-- available_at: same knowledge-time pattern as corporate_actions (GPT
-- Review #001 PATCH B, 2026-09-21). NULL means no validated
-- knowledge-time signal -- pit/access.py then falls back to
-- effective_from/effective_to alone (the pre-patch behavior), tagged
-- UNKNOWN. Deliberately minimal: no announcement/status lifecycle, just
-- the one nullable field, mirroring corporate_actions rather than
-- building a second PIT model in the same foundation.
--
-- Same enrichment-upsert persistence policy as corporate_actions (GPT
-- Final Review #001, 2026-09-21), keyed on (security_id, effective_from):
-- repository.upsert_listing_status COALESCE-merges effective_to/
-- delisting_reason/available_at (new wins only if non-NULL);
-- last_updated_timestamp records the most recent revision.
CREATE TABLE IF NOT EXISTS listing_status_history (
    security_id          TEXT NOT NULL REFERENCES security_master(security_id),
    status             TEXT NOT NULL,
    effective_from         TEXT NOT NULL,
    effective_to          TEXT,
    source_provider        TEXT NOT NULL,
    delisting_reason       TEXT,
    available_at          TEXT,
    last_updated_timestamp     TEXT NOT NULL,
    PRIMARY KEY (security_id, effective_from)
);

CREATE TABLE IF NOT EXISTS qa_results (
    security_id    TEXT NOT NULL REFERENCES security_master(security_id),
    date        TEXT NOT NULL,
    qa_pass      INTEGER NOT NULL,
    reason_codes   TEXT NOT NULL,
    severities    TEXT NOT NULL,
    computed_at    TEXT NOT NULL,
    PRIMARY KEY (security_id, date)
);
