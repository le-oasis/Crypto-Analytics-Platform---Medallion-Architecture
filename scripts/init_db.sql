-- ==========================================================
-- 🪣 Crypto Analytics Platform - Database Initialization (Yahoo Finance Only)
-- Initializes schemas and bronze tables for Yahoo Finance ingestion
-- ==========================================================

-- 1️⃣ Create base schemas (Bronze = raw, Silver = cleaned, Gold = aggregated)
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- ==========================================================
-- 🥉 Bronze Layer Table (Yahoo Finance)
-- ==========================================================

-- Raw price data from Yahoo Finance (15-minute interval)
CREATE TABLE IF NOT EXISTS bronze.raw_crypto_prices (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open NUMERIC(20, 8),
    high NUMERIC(20, 8),
    low NUMERIC(20, 8),
    close NUMERIC(20, 8),
    volume NUMERIC(20, 2),
    source VARCHAR(50) DEFAULT 'yahoo_finance',
    ingestion_timestamp TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (timestamp, symbol, source)
);

-- Indexes for fast queries and deduping
CREATE INDEX IF NOT EXISTS idx_bronze_prices_timestamp
    ON bronze.raw_crypto_prices (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_bronze_prices_symbol
    ON bronze.raw_crypto_prices (symbol);

-- ==========================================================
-- 🧠 MLflow (optional for experiments)
-- ==========================================================
CREATE SCHEMA IF NOT EXISTS mlflow;

-- ==========================================================
-- ✅ Verification Queries
-- ==========================================================
-- SELECT COUNT(*) FROM bronze.raw_crypto_prices;
-- SELECT symbol, MAX(timestamp) FROM bronze.raw_crypto_prices GROUP BY symbol;
