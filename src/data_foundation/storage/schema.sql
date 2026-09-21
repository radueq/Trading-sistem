-- Spec #001 -- Standard Internal Data Schema
-- Raw / factual tables only. No derived or as-of-today status is stored here --
-- derivation for a simulated moment happens exclusively in pit/access.py.

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
CREATE TABLE IF NOT EXISTS corporate_actions (
    action_id          TEXT PRIMARY KEY,
    security_id         TEXT NOT NULL REFERENCES security_master(security_id),
    action_type         TEXT NOT NULL,
    announcement_date      TEXT,
    effective_date        TEXT NOT NULL,
    value             REAL,
    source_provider       TEXT NOT NULL,
    source_status        TEXT,
    source_status_date     TEXT,
    available_at         TEXT,
    ingestion_timestamp     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_security ON corporate_actions(security_id);

CREATE TABLE IF NOT EXISTS listing_status_history (
    security_id      TEXT NOT NULL REFERENCES security_master(security_id),
    status         TEXT NOT NULL,
    effective_from     TEXT NOT NULL,
    effective_to      TEXT,
    source_provider    TEXT NOT NULL,
    delisting_reason   TEXT,
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
