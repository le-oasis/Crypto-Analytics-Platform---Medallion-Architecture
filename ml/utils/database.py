"""
Database Utilities for ML Pipeline

Handles all database operations for predictions, results, and model state.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
import logging
import json
from sqlalchemy import create_engine, text
from contextlib import contextmanager

from ml.config import get_db_connection_string, SUPPORTED_SYMBOLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MLDatabase:
    """Database operations for ML prediction system"""

    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or get_db_connection_string()
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            self._engine = create_engine(self.connection_string)
        return self._engine

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = self.engine.connect()
        try:
            yield conn
        finally:
            conn.close()

    def initialize_tables(self):
        """Create ML tables if they don't exist"""
        with open('scripts/init_ml_tables.sql', 'r') as f:
            sql = f.read()

        with self.get_connection() as conn:
            conn.execute(text(sql))
            conn.commit()
        logger.info("ML tables initialized")

    # ==================== Price Data ====================

    def get_historical_prices(
        self,
        symbol: str,
        days: int = 365,
        source: str = 'gold'
    ) -> pd.DataFrame:
        """
        Get historical price data for a symbol

        Args:
            symbol: Cryptocurrency symbol
            days: Number of days of history
            source: 'gold' for daily aggregated, 'silver' for cleaned hourly

        Returns:
            DataFrame with OHLCV data
        """
        if source == 'gold':
            query = """
                SELECT
                    date as timestamp,
                    symbol,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    daily_return_pct
                FROM silver_gold.gold_daily_prices
                WHERE symbol = :symbol
                    AND date >= CURRENT_DATE - :days * INTERVAL '1 day'
                ORDER BY date ASC
            """
        else:
            query = """
                SELECT
                    timestamp,
                    symbol,
                    open,
                    high,
                    low,
                    close,
                    volume
                FROM silver.silver_crypto_prices_cleaned
                WHERE symbol = :symbol
                    AND timestamp >= CURRENT_DATE - :days * INTERVAL '1 day'
                ORDER BY timestamp ASC
            """

        with self.get_connection() as conn:
            df = pd.read_sql(
                text(query),
                conn,
                params={'symbol': symbol, 'days': days}
            )

        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        return df

    def get_latest_price(self, symbol: str) -> Optional[Dict]:
        """Get the most recent price for a symbol"""
        query = """
            SELECT
                date as timestamp,
                symbol,
                open,
                high,
                low,
                close,
                volume
            FROM silver_gold.gold_daily_prices
            WHERE symbol = :symbol
            ORDER BY date DESC
            LIMIT 1
        """

        with self.get_connection() as conn:
            result = conn.execute(text(query), {'symbol': symbol}).fetchone()

        if result:
            return {
                'timestamp': result[0],
                'symbol': result[1],
                'open': float(result[2]) if result[2] else None,
                'high': float(result[3]) if result[3] else None,
                'low': float(result[4]) if result[4] else None,
                'close': float(result[5]) if result[5] else None,
                'volume': float(result[6]) if result[6] else None,
            }
        return None

    # ==================== Predictions ====================

    def save_prediction(
        self,
        prediction_date: date,
        symbol: str,
        predicted_direction: int,
        predicted_confidence: float,
        model_predictions: Dict[str, Dict],
        weights: Dict[str, float],
        fear_greed_value: Optional[int] = None,
        fear_greed_classification: Optional[str] = None,
        reference_close: Optional[float] = None,
        reference_date: Optional[date] = None
    ):
        """Save a prediction to the database"""
        query = """
            INSERT INTO gold.daily_predictions (
                prediction_date, symbol,
                predicted_direction, predicted_confidence,
                xgboost_direction, xgboost_confidence,
                lightgbm_direction, lightgbm_confidence,
                xgboost_weight, lightgbm_weight,
                fear_greed_value, fear_greed_classification,
                reference_close, reference_date
            ) VALUES (
                :prediction_date, :symbol,
                :predicted_direction, :predicted_confidence,
                :xgboost_direction, :xgboost_confidence,
                :lightgbm_direction, :lightgbm_confidence,
                :xgboost_weight, :lightgbm_weight,
                :fear_greed_value, :fear_greed_classification,
                :reference_close, :reference_date
            )
            ON CONFLICT (prediction_date, symbol)
            DO UPDATE SET
                predicted_direction = EXCLUDED.predicted_direction,
                predicted_confidence = EXCLUDED.predicted_confidence,
                xgboost_direction = EXCLUDED.xgboost_direction,
                xgboost_confidence = EXCLUDED.xgboost_confidence,
                lightgbm_direction = EXCLUDED.lightgbm_direction,
                lightgbm_confidence = EXCLUDED.lightgbm_confidence,
                xgboost_weight = EXCLUDED.xgboost_weight,
                lightgbm_weight = EXCLUDED.lightgbm_weight,
                fear_greed_value = EXCLUDED.fear_greed_value,
                fear_greed_classification = EXCLUDED.fear_greed_classification,
                reference_close = EXCLUDED.reference_close,
                reference_date = EXCLUDED.reference_date
        """

        xgb = model_predictions.get('xgboost', {})
        lgb = model_predictions.get('lightgbm', {})

        params = {
            'prediction_date': prediction_date,
            'symbol': symbol,
            'predicted_direction': predicted_direction,
            'predicted_confidence': predicted_confidence,
            'xgboost_direction': xgb.get('prediction'),
            'xgboost_confidence': xgb.get('confidence'),
            'lightgbm_direction': lgb.get('prediction'),
            'lightgbm_confidence': lgb.get('confidence'),
            'xgboost_weight': weights.get('xgboost'),
            'lightgbm_weight': weights.get('lightgbm'),
            'fear_greed_value': fear_greed_value,
            'fear_greed_classification': fear_greed_classification,
            'reference_close': reference_close,
            'reference_date': reference_date,
        }

        with self.get_connection() as conn:
            conn.execute(text(query), params)
            conn.commit()

        logger.info(f"Saved prediction for {symbol} on {prediction_date}")

    def get_prediction(self, prediction_date: date, symbol: str) -> Optional[Dict]:
        """Get a prediction for a specific date and symbol"""
        query = """
            SELECT *
            FROM gold.daily_predictions
            WHERE prediction_date = :prediction_date
                AND symbol = :symbol
        """

        with self.get_connection() as conn:
            result = conn.execute(
                text(query),
                {'prediction_date': prediction_date, 'symbol': symbol}
            ).fetchone()

        if result:
            return dict(result._mapping)
        return None

    def get_pending_predictions(self) -> pd.DataFrame:
        """Get predictions that haven't been scored yet"""
        query = """
            SELECT p.*
            FROM gold.daily_predictions p
            LEFT JOIN gold.prediction_results r
                ON p.prediction_date = r.prediction_date
                AND p.symbol = r.symbol
            WHERE r.id IS NULL
                AND p.prediction_date < CURRENT_DATE
            ORDER BY p.prediction_date
        """

        with self.get_connection() as conn:
            return pd.read_sql(text(query), conn)

    # ==================== Results ====================

    def save_result(
        self,
        prediction_date: date,
        symbol: str,
        predicted_direction: int,
        predicted_confidence: float,
        actual_direction: int,
        actual_open: float,
        actual_close: float,
        actual_high: float,
        actual_low: float,
        actual_return: float,
        direction_correct: bool,
        score: float,
        reward: float,
        xgboost_correct: Optional[bool] = None,
        lightgbm_correct: Optional[bool] = None
    ):
        """Save a prediction result to the database"""
        # Get prediction ID
        pred = self.get_prediction(prediction_date, symbol)
        prediction_id = pred['id'] if pred else None

        query = """
            INSERT INTO gold.prediction_results (
                prediction_id, prediction_date, symbol,
                predicted_direction, predicted_confidence,
                actual_direction, actual_open, actual_close,
                actual_high, actual_low, actual_return,
                direction_correct, score, reward,
                xgboost_correct, lightgbm_correct
            ) VALUES (
                :prediction_id, :prediction_date, :symbol,
                :predicted_direction, :predicted_confidence,
                :actual_direction, :actual_open, :actual_close,
                :actual_high, :actual_low, :actual_return,
                :direction_correct, :score, :reward,
                :xgboost_correct, :lightgbm_correct
            )
            ON CONFLICT (prediction_date, symbol)
            DO UPDATE SET
                actual_direction = EXCLUDED.actual_direction,
                actual_close = EXCLUDED.actual_close,
                actual_return = EXCLUDED.actual_return,
                direction_correct = EXCLUDED.direction_correct,
                score = EXCLUDED.score,
                reward = EXCLUDED.reward,
                scored_at = NOW()
        """

        params = {
            'prediction_id': prediction_id,
            'prediction_date': prediction_date,
            'symbol': symbol,
            'predicted_direction': predicted_direction,
            'predicted_confidence': predicted_confidence,
            'actual_direction': actual_direction,
            'actual_open': actual_open,
            'actual_close': actual_close,
            'actual_high': actual_high,
            'actual_low': actual_low,
            'actual_return': actual_return,
            'direction_correct': direction_correct,
            'score': score,
            'reward': reward,
            'xgboost_correct': xgboost_correct,
            'lightgbm_correct': lightgbm_correct,
        }

        with self.get_connection() as conn:
            conn.execute(text(query), params)
            conn.commit()

        logger.info(f"Saved result for {symbol} on {prediction_date}: correct={direction_correct}")

    def get_results(
        self,
        symbol: Optional[str] = None,
        days: int = 30
    ) -> pd.DataFrame:
        """Get prediction results"""
        query = """
            SELECT *
            FROM gold.prediction_results
            WHERE prediction_date >= CURRENT_DATE - :days * INTERVAL '1 day'
        """

        if symbol:
            query += " AND symbol = :symbol"

        query += " ORDER BY prediction_date DESC"

        params = {'days': days, 'symbol': symbol} if symbol else {'days': days}

        with self.get_connection() as conn:
            return pd.read_sql(text(query), conn, params=params)

    # ==================== RL Agent State ====================

    def save_agent_state(
        self,
        symbol: str,
        weights: Dict[str, float],
        total_predictions: int,
        total_correct: int,
        total_reward: float,
        learning_rate: float
    ):
        """Save RL agent state"""
        query = """
            INSERT INTO gold.rl_agent_state (
                symbol, weights,
                total_predictions, total_correct, total_reward,
                learning_rate, last_update, updated_at
            ) VALUES (
                :symbol, :weights,
                :total_predictions, :total_correct, :total_reward,
                :learning_rate, NOW(), NOW()
            )
            ON CONFLICT (symbol)
            DO UPDATE SET
                weights = EXCLUDED.weights,
                total_predictions = EXCLUDED.total_predictions,
                total_correct = EXCLUDED.total_correct,
                total_reward = EXCLUDED.total_reward,
                learning_rate = EXCLUDED.learning_rate,
                last_update = NOW(),
                updated_at = NOW()
        """

        params = {
            'symbol': symbol,
            'weights': json.dumps(weights),
            'total_predictions': total_predictions,
            'total_correct': total_correct,
            'total_reward': total_reward,
            'learning_rate': learning_rate,
        }

        with self.get_connection() as conn:
            conn.execute(text(query), params)
            conn.commit()

    def get_agent_state(self, symbol: str) -> Optional[Dict]:
        """Get RL agent state for a symbol"""
        query = """
            SELECT *
            FROM gold.rl_agent_state
            WHERE symbol = :symbol
        """

        with self.get_connection() as conn:
            result = conn.execute(text(query), {'symbol': symbol}).fetchone()

        if result:
            data = dict(result._mapping)
            data['weights'] = json.loads(data['weights']) if isinstance(data['weights'], str) else data['weights']
            return data
        return None

    # ==================== Dashboard Queries ====================

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get all data needed for the prediction dashboard"""

        # Today's predictions
        today_query = """
            SELECT *
            FROM gold.daily_predictions
            WHERE prediction_date = CURRENT_DATE
            ORDER BY symbol
        """

        # Yesterday's results
        yesterday_query = """
            SELECT
                p.symbol,
                p.predicted_direction,
                p.predicted_confidence,
                p.fear_greed_value,
                r.actual_direction,
                r.actual_return,
                r.direction_correct,
                r.score,
                r.reward
            FROM gold.daily_predictions p
            LEFT JOIN gold.prediction_results r
                ON p.prediction_date = r.prediction_date
                AND p.symbol = r.symbol
            WHERE p.prediction_date = CURRENT_DATE - INTERVAL '1 day'
            ORDER BY p.symbol
        """

        # Rolling accuracy
        accuracy_query = """
            SELECT
                symbol,
                COUNT(*) as total,
                SUM(CASE WHEN direction_correct THEN 1 ELSE 0 END) as correct,
                ROUND(AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy,
                SUM(reward) as total_reward
            FROM gold.prediction_results
            WHERE prediction_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY symbol
            ORDER BY accuracy DESC
        """

        # Recent predictions
        recent_query = """
            SELECT
                p.prediction_date,
                p.symbol,
                CASE WHEN p.predicted_direction = 1 THEN 'UP' ELSE 'DOWN' END as predicted,
                ROUND(p.predicted_confidence * 100, 1) as confidence,
                CASE WHEN r.actual_direction = 1 THEN 'UP' ELSE 'DOWN' END as actual,
                ROUND(r.actual_return * 100, 2) as return_pct,
                r.direction_correct as correct
            FROM gold.daily_predictions p
            LEFT JOIN gold.prediction_results r
                ON p.prediction_date = r.prediction_date
                AND p.symbol = r.symbol
            WHERE p.prediction_date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY p.prediction_date DESC, p.symbol
        """

        with self.get_connection() as conn:
            today_predictions = pd.read_sql(text(today_query), conn)
            yesterday_results = pd.read_sql(text(yesterday_query), conn)
            accuracy = pd.read_sql(text(accuracy_query), conn)
            recent = pd.read_sql(text(recent_query), conn)

        return {
            'today_predictions': today_predictions,
            'yesterday_results': yesterday_results,
            'rolling_accuracy': accuracy,
            'recent_predictions': recent,
        }


# Singleton instance
_db: Optional[MLDatabase] = None


def get_ml_database() -> MLDatabase:
    """Get or create the singleton database instance"""
    global _db
    if _db is None:
        _db = MLDatabase()
    return _db
