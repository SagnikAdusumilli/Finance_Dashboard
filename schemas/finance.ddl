-- Canonical DuckDB schema extracted from data/finance.db.
-- Schema only: no transaction data, balances, or sync checkpoints.
-- Apply to an empty DuckDB database. Preserve source names and types verbatim.

CREATE TABLE Transaction_raw (
    date DATE,
    "Name" VARCHAR,
    withdrawl DOUBLE,
    income DOUBLE,
    Category VARCHAR,
    Account_Name VARCHAR,
    transaction_type VARCHAR,
    file_source VARCHAR,
    loaded_at TIMESTAMP DEFAULT(CURRENT_TIMESTAMP)
);

CREATE TABLE Transaction_silver (
    date DATE,
    "Name" VARCHAR,
    amount DOUBLE,
    Category VARCHAR,
    Account_Name VARCHAR,
    transaction_type VARCHAR,
    file_source VARCHAR,
    loaded_at TIMESTAMP DEFAULT(CURRENT_TIMESTAMP)
);

CREATE TABLE account_balances (
    snapshot_date DATE,
    asset_id INTEGER,
    asset_name VARCHAR,
    asset_type VARCHAR,
    include_in_projection BOOLEAN,
    balance DOUBLE,
    row_hash VARCHAR,
    PRIMARY KEY(snapshot_date, asset_id)
);

CREATE TABLE account_contributions (
    snap_date DATE,
    asset_id INTEGER,
    monthly_contribution_amnt DOUBLE,
    PRIMARY KEY(snap_date, asset_id)
);

-- older legacy table used while using manual csv Ingestion
CREATE TABLE file_manifest (
    file_name VARCHAR PRIMARY KEY,
    row_count INTEGER,
    loaded_at TIMESTAMP DEFAULT(CURRENT_TIMESTAMP)
);

-- new logging table when using API runs
CREATE TABLE IF NOT EXISTS ingestion_run (
    run_id UUID PRIMARY KEY DEFAULT uuid(),

    pipeline_name VARCHAR NOT NULL,
    source_type VARCHAR NOT NULL,
    run_mode VARCHAR NOT NULL,

    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    status VARCHAR NOT NULL,

    records_added INTEGER DEFAULT 0,
    records_modified INTEGER DEFAULT 0,
    records_removed INTEGER DEFAULT 0,
    pages_fetched INTEGER DEFAULT 0,

    error_message VARCHAR
);

-- table to store cursor
CREATE TABLE IF NOT EXISTS plaid_sync_state (
    environment VARCHAR NOT NULL,
    item_id VARCHAR NOT NULL,

    cursor VARCHAR,
    last_successful_sync TIMESTAMP,

    PRIMARY KEY (environment, item_id)
);

-- staging table for api return
CREATE TABLE IF NOT EXISTS plaid_transactions (
    environment VARCHAR NOT NULL,
    item_id VARCHAR NOT NULL,
    transaction_id VARCHAR NOT NULL,

    account_id VARCHAR NOT NULL,
    date DATE,
    amount DECIMAL(18, 2),
    iso_currency_code VARCHAR,
    description VARCHAR,

    pending BOOLEAN DEFAULT FALSE,
    pending_transaction_id VARCHAR,

    raw_json JSON,

    is_removed BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (environment, item_id, transaction_id)
);
