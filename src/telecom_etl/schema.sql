-- Target data warehouse schema (SQLite dialect).
-- T-SQL / SQL Server equivalents live in sql/sqlserver/.

CREATE TABLE IF NOT EXISTS dim_imsi_reference (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    imsi          TEXT    NOT NULL UNIQUE,
    subscriber_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_transaction (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,      -- surrogate key
    transaction_id INTEGER NOT NULL,                       -- source ID
    imsi           TEXT    NOT NULL CHECK (length(imsi) <= 9),
    subscriber_id  INTEGER NOT NULL,                       -- -99999 = IMSI not found
    tac            TEXT    NOT NULL,                       -- first 8 of IMEI, or -99999
    snr            TEXT    NOT NULL,                       -- last 6 of IMEI, or -99999
    imei           TEXT    CHECK (imei IS NULL OR length(imei) <= 14),
    cell           INTEGER NOT NULL,
    lac            INTEGER NOT NULL,
    event_type     TEXT    CHECK (event_type IS NULL OR length(event_type) = 1),
    event_ts       TEXT    NOT NULL,                       -- ISO-8601 'YYYY-MM-DD HH:MM:SS'
    source_file    TEXT    NOT NULL,                       -- lineage: file that supplied the row
    loaded_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_fact_imsi     ON fact_transaction (imsi);
CREATE INDEX IF NOT EXISTS ix_fact_event_ts ON fact_transaction (event_ts);

-- Rejected records, kept as raw text so that invalid values never fail the insert.
CREATE TABLE IF NOT EXISTS error_destination_output (
    error_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file   TEXT NOT NULL,                           -- original CSV file name
    line_number   INTEGER NOT NULL,                        -- line in the source file
    id            TEXT,
    imsi          TEXT,
    imei          TEXT,
    cell          TEXT,
    lac           TEXT,
    event_type    TEXT,
    event_ts      TEXT,
    tac           TEXT,
    snr           TEXT,
    error_column  TEXT NOT NULL,
    error_reason  TEXT NOT NULL,
    raw_record    TEXT NOT NULL,
    rejected_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Audit log: one row per processed file (also gives idempotency).
CREATE TABLE IF NOT EXISTS etl_file_log (
    file_name     TEXT NOT NULL,
    file_sha256   TEXT NOT NULL,
    rows_read     INTEGER NOT NULL,
    rows_loaded   INTEGER NOT NULL,
    rows_rejected INTEGER NOT NULL,
    processed_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (file_name, file_sha256)
);
