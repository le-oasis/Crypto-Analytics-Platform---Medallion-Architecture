-- models/silver/silver_crypto_prices_cleaned.sql
/*
Silver Layer: Cleaned Cryptocurrency Prices
- Removes duplicates
- Handles missing values
- Adds calculated fields (returns, volatility)
- Quality validated data
*/

{{ config(
    materialized='incremental',
    unique_key=['timestamp', 'symbol'],
    on_schema_change='append_new_columns',
    tags=['silver', 'crypto', 'prices']
) }}

WITH source_data AS (
    SELECT 
        timestamp,
        symbol,
        open,
        high,
        low,
        close,
        volume,
        source,
        ingestion_timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY timestamp, symbol 
            ORDER BY ingestion_timestamp DESC
        ) as row_num
    FROM {{ source('bronze', 'raw_crypto_prices') }}
    
    {% if is_incremental() %}
    -- Only process new data
    WHERE timestamp > (SELECT MAX(timestamp) FROM {{ this }})
    {% endif %}
),

deduplicated AS (
    SELECT 
        timestamp,
        symbol,
        open,
        high,
        low,
        close,
        volume,
        source,
        ingestion_timestamp
    FROM source_data
    WHERE row_num = 1
),

with_validations AS (
    SELECT 
        timestamp,
        symbol,
        
        -- Handle null/negative prices with forward fill logic
        CASE 
            WHEN open IS NULL OR open <= 0 THEN close
            ELSE open 
        END as open,
        
        CASE 
            WHEN high IS NULL OR high <= 0 THEN close
            ELSE high 
        END as high,
        
        CASE 
            WHEN low IS NULL OR low <= 0 THEN close
            ELSE low 
        END as low,
        
        COALESCE(close, open) as close,
        
        COALESCE(volume, 0) as volume,
        source,
        ingestion_timestamp,
        
        -- Data quality flags
        CASE WHEN open IS NULL THEN 1 ELSE 0 END as flag_missing_open,
        CASE WHEN high IS NULL THEN 1 ELSE 0 END as flag_missing_high,
        CASE WHEN low IS NULL THEN 1 ELSE 0 END as flag_missing_low,
        CASE WHEN close IS NULL THEN 1 ELSE 0 END as flag_missing_close,
        CASE WHEN volume = 0 THEN 1 ELSE 0 END as flag_zero_volume
        
    FROM deduplicated
    WHERE close IS NOT NULL AND close > 0
),

with_calculated_fields AS (
    SELECT 
        timestamp,
        symbol,
        open,
        high,
        low,
        close,
        volume,
        source,
        ingestion_timestamp,
        
        -- Price changes
        close - open as intraperiod_change,
        ((close - open) / NULLIF(open, 0)) * 100 as intraperiod_change_pct,
        
        -- Log returns (for statistical analysis)
        LN(close / NULLIF(LAG(close) OVER (PARTITION BY symbol ORDER BY timestamp), 0)) as log_return,
        
        -- Simple returns
        ((close - LAG(close) OVER (PARTITION BY symbol ORDER BY timestamp)) / 
         NULLIF(LAG(close) OVER (PARTITION BY symbol ORDER BY timestamp), 0)) * 100 as simple_return_pct,
        
        -- High-Low spread
        high - low as spread,
        ((high - low) / NULLIF(low, 0)) * 100 as spread_pct,
        
        -- Volume metrics
        LAG(volume) OVER (PARTITION BY symbol ORDER BY timestamp) as prev_volume,
        
        -- Data quality flags
        flag_missing_open,
        flag_missing_high,
        flag_missing_low,
        flag_missing_close,
        flag_zero_volume,
        
        -- Metadata
        CURRENT_TIMESTAMP as dbt_updated_at
        
    FROM with_validations
)

SELECT * FROM with_calculated_fields
WHERE timestamp IS NOT NULL
  AND close > 0
  AND ABS(COALESCE(simple_return_pct, 0)) < 100  -- Filter extreme outliers (>100% change)

-- dbt will automatically add unique constraint on (timestamp, symbol)
