/*
Gold Layer: Daily Price Aggregations
Purpose: Roll up hourly/daily data into clean daily OHLCV summaries
Use Case: Portfolio analysis, daily performance tracking, trading strategies
*/

{{ config(
    materialized='table',
    tags=['gold', 'daily', 'prices']
) }}

WITH ordered_data AS (
    SELECT
        DATE(timestamp) as date,
        symbol,
        timestamp,
        open,
        high,
        low,
        close,
        volume,
        ROW_NUMBER() OVER (PARTITION BY DATE(timestamp), symbol ORDER BY timestamp ASC) as rn_asc,
        ROW_NUMBER() OVER (PARTITION BY DATE(timestamp), symbol ORDER BY timestamp DESC) as rn_desc
    FROM {{ ref('silver_crypto_prices_cleaned') }}
),

daily_aggregated AS (
    SELECT
        date,
        symbol,

        -- Open: first value of the day
        MAX(CASE WHEN rn_asc = 1 THEN open END) as open,

        -- High: maximum high of the day
        MAX(high) as high,

        -- Low: minimum low of the day
        MIN(low) as low,

        -- Close: last value of the day
        MAX(CASE WHEN rn_desc = 1 THEN close END) as close,

        -- Volume: sum of all volumes for the day
        SUM(volume) as volume,

        -- Metadata
        COUNT(*) as data_points,
        MIN(timestamp) as first_timestamp,
        MAX(timestamp) as last_timestamp

    FROM ordered_data
    GROUP BY date, symbol
),

with_metrics AS (
    SELECT
        date,
        symbol,
        open,
        high,
        low,
        close,
        volume,

        -- Daily price change
        close - open as price_change,
        ROUND(((close - open) / NULLIF(open, 0) * 100)::numeric, 2) as price_change_pct,

        -- Daily spread (volatility indicator)
        high - low as daily_spread,
        ROUND(((high - low) / NULLIF(low, 0) * 100)::numeric, 2) as spread_pct,

        -- Previous day close (for returns calculation)
        LAG(close) OVER (PARTITION BY symbol ORDER BY date) as prev_close,

        -- Metadata
        data_points,
        first_timestamp,
        last_timestamp,
        CURRENT_TIMESTAMP as dbt_updated_at

    FROM daily_aggregated
),

final AS (
    SELECT
        date,
        symbol,
        open,
        high,
        low,
        close,
        volume,
        price_change,
        price_change_pct,
        daily_spread,
        spread_pct,

        -- Daily return (vs previous day close)
        ROUND(((close - prev_close) / NULLIF(prev_close, 0) * 100)::numeric, 2) as daily_return_pct,

        -- Log return (for statistical analysis)
        ROUND(LN(close / NULLIF(prev_close, 0))::numeric, 4) as log_return,

        data_points,
        first_timestamp,
        last_timestamp,
        dbt_updated_at

    FROM with_metrics
)

SELECT * FROM final
ORDER BY symbol, date
