-- ==========================================================
-- ML/RL Prediction System - Database Tables
-- Creates tables for storing predictions, scores, and model performance
-- ==========================================================

-- Ensure gold schema exists
CREATE SCHEMA IF NOT EXISTS gold;

-- ==========================================================
-- 1. Daily Predictions Table
-- Stores predictions made for each day
-- ==========================================================
CREATE TABLE IF NOT EXISTS gold.daily_predictions (
    id SERIAL PRIMARY KEY,
    prediction_date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,

    -- Ensemble prediction
    predicted_direction INTEGER NOT NULL,  -- 1 = up, 0 = down
    predicted_confidence NUMERIC(5, 4),    -- 0-1 confidence score

    -- Individual model predictions
    xgboost_direction INTEGER,
    xgboost_confidence NUMERIC(5, 4),
    lightgbm_direction INTEGER,
    lightgbm_confidence NUMERIC(5, 4),

    -- Model weights at prediction time
    xgboost_weight NUMERIC(5, 4),
    lightgbm_weight NUMERIC(5, 4),

    -- External signals
    fear_greed_value INTEGER,
    fear_greed_classification VARCHAR(50),

    -- Reference prices (at prediction time)
    reference_close NUMERIC(20, 8),        -- Previous day's close
    reference_date DATE,                    -- Date of reference price

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    model_version VARCHAR(50) DEFAULT '1.0',

    UNIQUE (prediction_date, symbol)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_predictions_date
    ON gold.daily_predictions (prediction_date DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_symbol
    ON gold.daily_predictions (symbol);

-- ==========================================================
-- 2. Prediction Results Table
-- Stores actual results and scores after market close
-- ==========================================================
CREATE TABLE IF NOT EXISTS gold.prediction_results (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER REFERENCES gold.daily_predictions(id),
    prediction_date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,

    -- Prediction recap
    predicted_direction INTEGER NOT NULL,
    predicted_confidence NUMERIC(5, 4),

    -- Actual results
    actual_direction INTEGER NOT NULL,     -- 1 = up, 0 = down
    actual_open NUMERIC(20, 8),
    actual_close NUMERIC(20, 8),
    actual_high NUMERIC(20, 8),
    actual_low NUMERIC(20, 8),
    actual_return NUMERIC(10, 6),          -- Percentage return

    -- Scoring
    direction_correct BOOLEAN NOT NULL,
    score NUMERIC(5, 4),                   -- 0-1 combined score
    reward NUMERIC(10, 6),                 -- RL reward value

    -- Individual model scores
    xgboost_correct BOOLEAN,
    lightgbm_correct BOOLEAN,

    -- Metadata
    scored_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (prediction_date, symbol)
);

-- Index for result lookups
CREATE INDEX IF NOT EXISTS idx_results_date
    ON gold.prediction_results (prediction_date DESC);
CREATE INDEX IF NOT EXISTS idx_results_symbol
    ON gold.prediction_results (symbol);

-- ==========================================================
-- 3. Model Performance Table
-- Tracks rolling model performance metrics
-- ==========================================================
CREATE TABLE IF NOT EXISTS gold.model_performance (
    id SERIAL PRIMARY KEY,
    calculation_date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    model_name VARCHAR(50) NOT NULL,

    -- Performance metrics (rolling 30 days)
    total_predictions INTEGER,
    correct_predictions INTEGER,
    accuracy NUMERIC(5, 4),
    avg_confidence NUMERIC(5, 4),
    avg_reward NUMERIC(10, 6),
    total_reward NUMERIC(10, 6),

    -- Current weight assigned by RL agent
    current_weight NUMERIC(5, 4),

    -- Streak tracking
    current_streak INTEGER,                -- Positive = wins, negative = losses
    best_streak INTEGER,
    worst_streak INTEGER,

    -- Metadata
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (calculation_date, symbol, model_name)
);

CREATE INDEX IF NOT EXISTS idx_performance_date
    ON gold.model_performance (calculation_date DESC);

-- ==========================================================
-- 4. RL Agent State Table
-- Persists RL agent weights and learning state
-- ==========================================================
CREATE TABLE IF NOT EXISTS gold.rl_agent_state (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,

    -- Current weights
    weights JSONB NOT NULL,                -- {"xgboost": 0.4, "lightgbm": 0.3, ...}

    -- Cumulative stats
    total_predictions INTEGER DEFAULT 0,
    total_correct INTEGER DEFAULT 0,
    total_reward NUMERIC(15, 6) DEFAULT 0,

    -- Learning state
    learning_rate NUMERIC(5, 4),
    last_update TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (symbol)
);

-- ==========================================================
-- 5. Feature Snapshots Table (Optional)
-- Stores computed features for reproducibility
-- ==========================================================
CREATE TABLE IF NOT EXISTS gold.feature_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,

    -- Store features as JSON for flexibility
    features JSONB NOT NULL,

    -- Key indicators (denormalized for quick access)
    rsi NUMERIC(10, 4),
    macd NUMERIC(20, 8),
    sma_20 NUMERIC(20, 8),
    fear_greed INTEGER,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (snapshot_date, symbol)
);

CREATE INDEX IF NOT EXISTS idx_features_date
    ON gold.feature_snapshots (snapshot_date DESC);

-- ==========================================================
-- Views for Dashboard
-- ==========================================================

-- Today's predictions vs yesterday's results
CREATE OR REPLACE VIEW gold.v_prediction_dashboard AS
SELECT
    p.prediction_date,
    p.symbol,
    p.predicted_direction,
    CASE WHEN p.predicted_direction = 1 THEN 'UP' ELSE 'DOWN' END as predicted_label,
    p.predicted_confidence,
    p.fear_greed_value,
    p.reference_close,
    r.actual_direction,
    CASE WHEN r.actual_direction = 1 THEN 'UP' ELSE 'DOWN' END as actual_label,
    r.actual_close,
    r.actual_return,
    r.direction_correct,
    r.score,
    r.reward
FROM gold.daily_predictions p
LEFT JOIN gold.prediction_results r
    ON p.prediction_date = r.prediction_date
    AND p.symbol = r.symbol
ORDER BY p.prediction_date DESC, p.symbol;

-- Rolling accuracy by symbol
CREATE OR REPLACE VIEW gold.v_rolling_accuracy AS
SELECT
    symbol,
    COUNT(*) as total_predictions,
    SUM(CASE WHEN direction_correct THEN 1 ELSE 0 END) as correct,
    ROUND(AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END) * 100, 2) as accuracy_pct,
    ROUND(AVG(score) * 100, 2) as avg_score,
    SUM(reward) as total_reward
FROM gold.prediction_results
WHERE prediction_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY symbol
ORDER BY accuracy_pct DESC;

-- Model comparison
CREATE OR REPLACE VIEW gold.v_model_comparison AS
SELECT
    symbol,
    'xgboost' as model,
    COUNT(*) as predictions,
    SUM(CASE WHEN xgboost_correct THEN 1 ELSE 0 END) as correct,
    ROUND(AVG(CASE WHEN xgboost_correct THEN 1.0 ELSE 0.0 END) * 100, 2) as accuracy
FROM gold.prediction_results
WHERE prediction_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY symbol
UNION ALL
SELECT
    symbol,
    'lightgbm' as model,
    COUNT(*) as predictions,
    SUM(CASE WHEN lightgbm_correct THEN 1 ELSE 0 END) as correct,
    ROUND(AVG(CASE WHEN lightgbm_correct THEN 1.0 ELSE 0.0 END) * 100, 2) as accuracy
FROM gold.prediction_results
WHERE prediction_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY symbol
ORDER BY symbol, model;

-- ==========================================================
-- Helpful Comments
-- ==========================================================
COMMENT ON TABLE gold.daily_predictions IS 'Stores daily crypto price direction predictions from ML models';
COMMENT ON TABLE gold.prediction_results IS 'Stores actual results and scores comparing predictions to reality';
COMMENT ON TABLE gold.model_performance IS 'Rolling performance metrics for each model';
COMMENT ON TABLE gold.rl_agent_state IS 'Persists the RL agent learning state and weights';
