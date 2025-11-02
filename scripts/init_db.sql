-- Create schemas
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- Create bronze tables
CREATE TABLE IF NOT EXISTS bronze.raw_crypto_prices (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open NUMERIC(20, 8),
    high NUMERIC(20, 8),
    low NUMERIC(20, 8),
    close NUMERIC(20, 8),
    volume NUMERIC(20, 2),
    source VARCHAR(50),
    ingestion_timestamp TIMESTAMP DEFAULT NOW(),
    UNIQUE(timestamp, symbol, source)
);

CREATE TABLE IF NOT EXISTS bronze.raw_market_data (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    coin_id VARCHAR(50),
    market_cap NUMERIC(20, 2),
    total_volume NUMERIC(20, 2),
    circulating_supply NUMERIC(20, 2),
    total_supply NUMERIC(20, 2),
    ath NUMERIC(20, 8),
    atl NUMERIC(20, 8),
    price_change_24h NUMERIC(20, 8),
    price_change_percentage_24h NUMERIC(10, 4),
    source VARCHAR(50),
    UNIQUE(timestamp, symbol)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_prices_timestamp ON bronze.raw_crypto_prices(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_prices_symbol ON bronze.raw_crypto_prices(symbol);
CREATE INDEX IF NOT EXISTS idx_market_timestamp ON bronze.raw_market_data(timestamp DESC);

-- Create MLflow database
CREATE DATABASE IF NOT EXISTS mlflow;