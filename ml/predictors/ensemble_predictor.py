"""
Ensemble Predictor

Combines multiple models with weighted voting.
Weights are adjusted by the RL agent based on performance.
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional, List
from datetime import datetime
import logging

from ml.predictors.base_predictor import BasePredictor
from ml.predictors.xgboost_predictor import XGBoostPredictor
from ml.predictors.lightgbm_predictor import LightGBMPredictor
from ml.config import MODEL_CONFIG, RL_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnsemblePredictor(BasePredictor):
    """
    Ensemble predictor combining multiple models

    Uses weighted averaging of predictions where weights
    are dynamically adjusted by the RL scoring agent.
    """

    def __init__(self, symbol: str, weights: Optional[Dict[str, float]] = None):
        super().__init__(symbol, 'ensemble')
        self.weights = weights or RL_CONFIG['initial_weights'].copy()
        self.models: Dict[str, BasePredictor] = {}
        self.model_metrics: Dict[str, Dict] = {}

    def initialize_models(self):
        """Initialize all sub-models"""
        self.models = {
            'xgboost': XGBoostPredictor(self.symbol),
            'lightgbm': LightGBMPredictor(self.symbol),
        }
        logger.info(f"Initialized {len(self.models)} models for {self.symbol}")

    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """
        Train all models in the ensemble

        Args:
            X: Feature DataFrame
            y: Target Series

        Returns:
            Dictionary of ensemble metrics
        """
        if not self.models:
            self.initialize_models()

        # Train each model
        for name, model in self.models.items():
            logger.info(f"Training {name} for {self.symbol}...")
            metrics = model.train(X, y)
            self.model_metrics[name] = metrics

        # Calculate ensemble metrics
        self.metrics = self._calculate_ensemble_metrics(X, y)
        self.is_trained = True
        self.training_date = datetime.now()

        return self.metrics

    def _calculate_ensemble_metrics(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """Calculate metrics for the ensemble prediction"""
        # Get ensemble predictions
        y_pred, _ = self.predict(X)

        # Remove NaN targets
        mask = ~y.isna()
        y_clean = y[mask].values
        y_pred_clean = y_pred[mask]

        if len(y_clean) == 0:
            return {}

        return self.evaluate(pd.Series(y_clean), y_pred_clean)

    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Make weighted ensemble predictions

        Args:
            X: Feature DataFrame

        Returns:
            Tuple of (predictions, confidence_scores)
        """
        if not self.models:
            raise ValueError("Models not initialized. Call initialize_models() first.")

        predictions_list = []
        confidence_list = []
        weight_list = []

        for name, model in self.models.items():
            if model.is_trained:
                try:
                    pred, conf = model.predict(X)
                    predictions_list.append(pred)
                    confidence_list.append(conf)
                    weight_list.append(self.weights.get(name, 0))
                except Exception as e:
                    logger.warning(f"Error predicting with {name}: {e}")

        if not predictions_list:
            # Return neutral prediction if no models available
            return np.zeros(len(X)), np.zeros(len(X))

        # Stack predictions
        predictions_array = np.vstack(predictions_list)
        confidence_array = np.vstack(confidence_list)
        weights = np.array(weight_list)

        # Normalize weights
        weights = weights / weights.sum()

        # Weighted average
        weighted_pred = np.average(predictions_array, axis=0, weights=weights)
        weighted_conf = np.average(confidence_array, axis=0, weights=weights)

        # Convert to binary (threshold at 0.5)
        final_pred = (weighted_pred > 0.5).astype(int)

        return final_pred, weighted_conf

    def predict_single(self, X: pd.DataFrame) -> Dict:
        """
        Make prediction for a single day with detailed breakdown

        Args:
            X: Feature DataFrame (last row will be used)

        Returns:
            Dictionary with prediction details and model breakdown
        """
        X_latest = X.tail(1)

        # Get individual model predictions
        model_predictions = {}
        for name, model in self.models.items():
            if model.is_trained:
                pred = model.predict_single(X_latest)
                pred['weight'] = self.weights.get(name, 0)
                model_predictions[name] = pred

        # Get ensemble prediction
        predictions, confidence = self.predict(X_latest)

        return {
            'prediction': int(predictions[0]),
            'direction': 'up' if predictions[0] == 1 else 'down',
            'confidence': float(confidence[0]),
            'model': 'ensemble',
            'symbol': self.symbol,
            'weights': self.weights.copy(),
            'model_predictions': model_predictions
        }

    def update_weights(self, new_weights: Dict[str, float]):
        """
        Update model weights (called by RL agent)

        Args:
            new_weights: Dictionary of model_name -> weight
        """
        # Validate weights
        total = sum(new_weights.values())
        if abs(total - 1.0) > 0.01:
            # Normalize
            new_weights = {k: v/total for k, v in new_weights.items()}

        # Apply min/max constraints
        for name in new_weights:
            new_weights[name] = max(RL_CONFIG['min_weight'],
                                   min(RL_CONFIG['max_weight'], new_weights[name]))

        # Re-normalize after constraints
        total = sum(new_weights.values())
        self.weights = {k: v/total for k, v in new_weights.items()}

        logger.info(f"Updated ensemble weights for {self.symbol}: {self.weights}")

    def get_model_performance(self) -> Dict[str, Dict]:
        """Get performance metrics for each model"""
        return {
            name: {
                'metrics': model.metrics,
                'weight': self.weights.get(name, 0),
                'is_trained': model.is_trained
            }
            for name, model in self.models.items()
        }

    def save_all(self, path: str):
        """Save ensemble and all sub-models"""
        import os

        # Save ensemble metadata
        self.save(path)

        # Save each model
        for name, model in self.models.items():
            model_path = os.path.join(path, name)
            model.save(model_path)

    def load_all(self, path: str):
        """Load ensemble and all sub-models"""
        import os

        # Initialize models first
        self.initialize_models()

        # Load each model
        for name, model in self.models.items():
            model_path = os.path.join(path, name)
            # Find latest model file
            if os.path.exists(model_path):
                files = [f for f in os.listdir(model_path) if f.endswith('.joblib')]
                if files:
                    latest = sorted(files)[-1]
                    model.load(os.path.join(model_path, latest))
