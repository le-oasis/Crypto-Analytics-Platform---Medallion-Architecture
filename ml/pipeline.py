"""
Main ML Prediction Pipeline

Orchestrates the entire prediction workflow:
1. Load and prepare data
2. Calculate features
3. Train/update models
4. Generate predictions
5. Score results and update RL agent
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import logging
import os

from ml.config import SUPPORTED_SYMBOLS, FEATURE_CONFIG, RL_CONFIG
from ml.feature_engineering.technical_indicators import TechnicalIndicators
from ml.feature_engineering.fear_greed_index import FearGreedIndex
from ml.predictors.ensemble_predictor import EnsemblePredictor
from ml.rl_agent.scoring_agent import RLScoringAgent, get_scoring_agent
from ml.utils.database import MLDatabase, get_ml_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PredictionPipeline:
    """
    Main prediction pipeline orchestrator

    Handles the complete workflow from data loading to prediction scoring.
    """

    def __init__(self, db: Optional[MLDatabase] = None):
        self.db = db or get_ml_database()
        self.technical_indicators = TechnicalIndicators()
        self.fear_greed = FearGreedIndex()
        self.scoring_agent = get_scoring_agent()

        # Ensemble models per symbol
        self.models: Dict[str, EnsemblePredictor] = {}

        # Feature cache
        self._feature_cache: Dict[str, pd.DataFrame] = {}

    def initialize(self):
        """Initialize the pipeline"""
        logger.info("Initializing prediction pipeline...")

        # Initialize models for each symbol
        for symbol in SUPPORTED_SYMBOLS:
            self.models[symbol] = EnsemblePredictor(symbol)
            self.models[symbol].initialize_models()

            # Load RL agent state if exists
            agent_state = self.db.get_agent_state(symbol)
            if agent_state:
                self.models[symbol].update_weights(agent_state['weights'])
                logger.info(f"Loaded weights for {symbol}: {agent_state['weights']}")

        logger.info(f"Initialized {len(self.models)} models")

    def prepare_features(self, symbol: str, days: int = 365) -> pd.DataFrame:
        """
        Prepare features for a symbol

        Args:
            symbol: Cryptocurrency symbol
            days: Days of historical data to use

        Returns:
            DataFrame with all features calculated
        """
        # Get historical data
        df = self.db.get_historical_prices(symbol, days=days)

        if df.empty:
            logger.warning(f"No historical data for {symbol}")
            return pd.DataFrame()

        # Calculate technical indicators
        df_features = self.technical_indicators.calculate_all(df)

        # Add Fear & Greed Index
        df_features = self.fear_greed.add_fear_greed_features(df_features)

        # Cache features
        self._feature_cache[symbol] = df_features

        logger.info(f"Prepared {len(df_features)} rows of features for {symbol}")
        return df_features

    def train_models(self, symbol: str, force: bool = False) -> Dict[str, float]:
        """
        Train models for a symbol

        Args:
            symbol: Cryptocurrency symbol
            force: Force retraining even if recently trained

        Returns:
            Dictionary of training metrics
        """
        if symbol not in self.models:
            logger.error(f"Model not initialized for {symbol}")
            return {}

        # Get features
        if symbol in self._feature_cache:
            df = self._feature_cache[symbol]
        else:
            df = self.prepare_features(symbol)

        if df.empty:
            return {}

        # Prepare target (next day direction)
        target = (df['close'].shift(-1) > df['close']).astype(int)

        # Remove last row (no target)
        df = df.iloc[:-1]
        target = target.iloc[:-1]

        # Train ensemble
        metrics = self.models[symbol].train(df, target)

        logger.info(f"Trained models for {symbol}: {metrics}")
        return metrics

    def generate_prediction(self, symbol: str, prediction_date: date) -> Optional[Dict]:
        """
        Generate prediction for a symbol

        Args:
            symbol: Cryptocurrency symbol
            prediction_date: Date to predict for

        Returns:
            Dictionary with prediction details
        """
        if symbol not in self.models:
            logger.error(f"Model not initialized for {symbol}")
            return None

        model = self.models[symbol]

        if not model.is_trained:
            logger.warning(f"Model not trained for {symbol}, training now...")
            self.train_models(symbol)

        # Get latest features
        if symbol not in self._feature_cache:
            self.prepare_features(symbol)

        df = self._feature_cache.get(symbol)
        if df is None or df.empty:
            return None

        # Make prediction
        prediction = model.predict_single(df)

        # Get Fear & Greed
        fg = self.fear_greed.get_current()

        # Get reference price (latest close)
        latest_price = self.db.get_latest_price(symbol)
        reference_close = latest_price['close'] if latest_price else None
        reference_date = latest_price['timestamp'] if latest_price else None

        # Save prediction
        self.db.save_prediction(
            prediction_date=prediction_date,
            symbol=symbol,
            predicted_direction=prediction['prediction'],
            predicted_confidence=prediction['confidence'],
            model_predictions=prediction.get('model_predictions', {}),
            weights=prediction.get('weights', {}),
            fear_greed_value=fg['value'],
            fear_greed_classification=fg['classification'],
            reference_close=reference_close,
            reference_date=reference_date.date() if reference_date else None
        )

        prediction['fear_greed'] = fg
        prediction['reference_close'] = reference_close
        prediction['prediction_date'] = prediction_date

        logger.info(
            f"Generated prediction for {symbol} on {prediction_date}: "
            f"{prediction['direction']} ({prediction['confidence']:.1%})"
        )

        return prediction

    def generate_all_predictions(self, prediction_date: Optional[date] = None) -> List[Dict]:
        """
        Generate predictions for all symbols

        Args:
            prediction_date: Date to predict for (default: tomorrow)

        Returns:
            List of prediction dictionaries
        """
        if prediction_date is None:
            prediction_date = date.today() + timedelta(days=1)

        predictions = []
        for symbol in SUPPORTED_SYMBOLS:
            try:
                pred = self.generate_prediction(symbol, prediction_date)
                if pred:
                    predictions.append(pred)
            except Exception as e:
                logger.error(f"Error generating prediction for {symbol}: {e}")

        logger.info(f"Generated {len(predictions)} predictions for {prediction_date}")
        return predictions

    def score_predictions(self) -> List[Dict]:
        """
        Score pending predictions against actual results

        Returns:
            List of scored results
        """
        # Get predictions that need scoring
        pending = self.db.get_pending_predictions()

        if pending.empty:
            logger.info("No pending predictions to score")
            return []

        results = []
        for _, pred in pending.iterrows():
            try:
                result = self._score_single_prediction(pred)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error scoring prediction for {pred['symbol']}: {e}")

        # Update RL agent weights after scoring
        for symbol in pending['symbol'].unique():
            self._update_symbol_weights(symbol)

        logger.info(f"Scored {len(results)} predictions")
        return results

    def _score_single_prediction(self, pred: pd.Series) -> Optional[Dict]:
        """Score a single prediction"""
        symbol = pred['symbol']
        prediction_date = pred['prediction_date']

        # Get actual price data for the prediction date
        actual = self._get_actual_price(symbol, prediction_date)
        if actual is None:
            logger.warning(f"No actual data for {symbol} on {prediction_date}")
            return None

        # Calculate actual return
        reference_close = float(pred['reference_close'])
        actual_close = actual['close']
        actual_return = (actual_close - reference_close) / reference_close
        actual_direction = 1 if actual_return > 0 else 0

        # Check prediction
        predicted_direction = int(pred['predicted_direction'])
        direction_correct = predicted_direction == actual_direction

        # Score using RL agent
        result = self.scoring_agent.score_prediction(
            symbol=symbol,
            model='ensemble',
            predicted_direction=predicted_direction,
            predicted_confidence=float(pred['predicted_confidence']),
            actual_close=actual_close,
            previous_close=reference_close,
            prediction_date=datetime.combine(prediction_date, datetime.min.time())
        )

        # Check individual model predictions
        xgb_correct = None
        lgb_correct = None
        if pred.get('xgboost_direction') is not None:
            xgb_correct = int(pred['xgboost_direction']) == actual_direction
        if pred.get('lightgbm_direction') is not None:
            lgb_correct = int(pred['lightgbm_direction']) == actual_direction

        # Save result
        self.db.save_result(
            prediction_date=prediction_date,
            symbol=symbol,
            predicted_direction=predicted_direction,
            predicted_confidence=float(pred['predicted_confidence']),
            actual_direction=actual_direction,
            actual_open=actual['open'],
            actual_close=actual_close,
            actual_high=actual['high'],
            actual_low=actual['low'],
            actual_return=actual_return,
            direction_correct=direction_correct,
            score=result.score,
            reward=result.reward,
            xgboost_correct=xgb_correct,
            lightgbm_correct=lgb_correct
        )

        return {
            'symbol': symbol,
            'date': prediction_date,
            'predicted': 'up' if predicted_direction == 1 else 'down',
            'actual': 'up' if actual_direction == 1 else 'down',
            'correct': direction_correct,
            'actual_return': actual_return,
            'score': result.score,
            'reward': result.reward,
        }

    def _get_actual_price(self, symbol: str, target_date: date) -> Optional[Dict]:
        """Get actual OHLCV data for a specific date"""
        df = self.db.get_historical_prices(symbol, days=7)

        if df.empty:
            return None

        # Find the row for target date
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        row = df[df['date'] == target_date]

        if row.empty:
            return None

        row = row.iloc[0]
        return {
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row['volume']),
        }

    def _update_symbol_weights(self, symbol: str):
        """Update model weights for a symbol based on RL agent learning"""
        # Get updated weights from RL agent
        new_weights = self.scoring_agent.update_weights(symbol)

        # Update ensemble model
        if symbol in self.models:
            self.models[symbol].update_weights(new_weights)

        # Get performance summary
        perf = self.scoring_agent.get_performance_summary(symbol)

        # Save agent state
        self.db.save_agent_state(
            symbol=symbol,
            weights=new_weights,
            total_predictions=perf.get('total_predictions', 0),
            total_correct=perf.get('correct_predictions', 0),
            total_reward=perf.get('total_reward', 0),
            learning_rate=self.scoring_agent.learning_rate
        )

    def get_performance_summary(self) -> Dict:
        """Get overall performance summary"""
        summary = {
            'overall': self.scoring_agent.get_performance_summary(),
            'by_symbol': {},
        }

        for symbol in SUPPORTED_SYMBOLS:
            summary['by_symbol'][symbol] = {
                'performance': self.scoring_agent.get_performance_summary(symbol),
                'model_breakdown': self.scoring_agent.get_model_performance(symbol),
                'weights': self.scoring_agent.get_weights(symbol),
            }

        return summary

    def run_daily_pipeline(self):
        """
        Run the complete daily pipeline

        1. Score yesterday's predictions
        2. Retrain models with new data
        3. Generate tomorrow's predictions
        """
        logger.info("=" * 50)
        logger.info("Starting daily prediction pipeline")
        logger.info("=" * 50)

        # Step 1: Score pending predictions
        logger.info("Step 1: Scoring pending predictions...")
        results = self.score_predictions()
        logger.info(f"Scored {len(results)} predictions")

        # Step 2: Refresh features and retrain
        logger.info("Step 2: Refreshing features and retraining models...")
        for symbol in SUPPORTED_SYMBOLS:
            try:
                self.prepare_features(symbol)
                self.train_models(symbol)
            except Exception as e:
                logger.error(f"Error training {symbol}: {e}")

        # Step 3: Generate tomorrow's predictions
        tomorrow = date.today() + timedelta(days=1)
        logger.info(f"Step 3: Generating predictions for {tomorrow}...")
        predictions = self.generate_all_predictions(tomorrow)

        # Summary
        logger.info("=" * 50)
        logger.info("Pipeline complete!")
        logger.info(f"  - Scored: {len(results)} predictions")
        logger.info(f"  - Generated: {len(predictions)} new predictions")

        perf = self.scoring_agent.get_performance_summary()
        if perf['total_predictions'] > 0:
            logger.info(f"  - Overall accuracy: {perf['accuracy']:.1%}")
            logger.info(f"  - Total reward: {perf['total_reward']:.2f}")

        return {
            'scored': results,
            'predictions': predictions,
            'performance': perf,
        }


def run_pipeline():
    """Convenience function to run the daily pipeline"""
    pipeline = PredictionPipeline()
    pipeline.initialize()
    return pipeline.run_daily_pipeline()


if __name__ == "__main__":
    run_pipeline()
