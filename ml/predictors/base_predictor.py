"""
Base Predictor Class

Abstract base class for all prediction models.
Provides common interface for training, prediction, and evaluation.
"""
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import logging
import joblib
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BasePredictor(ABC):
    """Abstract base class for crypto price predictors"""

    def __init__(self, symbol: str, model_name: str):
        self.symbol = symbol
        self.model_name = model_name
        self.model = None
        self.is_trained = False
        self.training_date = None
        self.feature_columns = []
        self.metrics = {}

    @abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """
        Train the model

        Args:
            X: Feature DataFrame
            y: Target Series

        Returns:
            Dictionary of training metrics
        """
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Make predictions

        Args:
            X: Feature DataFrame

        Returns:
            Tuple of (predictions, confidence_scores)
        """
        pass

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Get prediction probabilities (for classification)

        Args:
            X: Feature DataFrame

        Returns:
            Array of probabilities
        """
        # Default implementation returns confidence from predict
        _, confidence = self.predict(X)
        return confidence

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare features for prediction

        Args:
            df: Raw DataFrame with all columns

        Returns:
            DataFrame with only feature columns, cleaned
        """
        if not self.feature_columns:
            raise ValueError("Feature columns not set. Train the model first.")

        # Select only feature columns that exist
        available_cols = [c for c in self.feature_columns if c in df.columns]
        X = df[available_cols].copy()

        # Handle missing values
        X = X.fillna(method='ffill').fillna(method='bfill').fillna(0)

        # Handle infinities
        X = X.replace([np.inf, -np.inf], 0)

        return X

    def prepare_target(self, df: pd.DataFrame, target_type: str = 'direction') -> pd.Series:
        """
        Prepare target variable

        Args:
            df: DataFrame with close prices
            target_type: 'direction' (1/0) or 'return' (continuous)

        Returns:
            Series with target values
        """
        # Next day return
        next_return = df['close'].shift(-1) / df['close'] - 1

        if target_type == 'direction':
            # Binary: 1 = up, 0 = down
            return (next_return > 0).astype(int)
        else:
            return next_return

    def evaluate(self, y_true: pd.Series, y_pred: np.ndarray) -> Dict[str, float]:
        """
        Evaluate model performance

        Args:
            y_true: Actual values
            y_pred: Predicted values

        Returns:
            Dictionary of evaluation metrics
        """
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

        # Convert to binary if needed
        y_true_binary = (y_true > 0).astype(int) if y_true.dtype != int else y_true
        y_pred_binary = (y_pred > 0.5).astype(int) if y_pred.max() <= 1 else (y_pred > 0).astype(int)

        metrics = {
            'accuracy': accuracy_score(y_true_binary, y_pred_binary),
            'precision': precision_score(y_true_binary, y_pred_binary, zero_division=0),
            'recall': recall_score(y_true_binary, y_pred_binary, zero_division=0),
            'f1': f1_score(y_true_binary, y_pred_binary, zero_division=0),
        }

        # Direction accuracy (most important for trading)
        correct_direction = (y_true_binary == y_pred_binary).sum()
        metrics['direction_accuracy'] = correct_direction / len(y_true)

        return metrics

    def save(self, path: str) -> str:
        """
        Save model to disk

        Args:
            path: Directory to save model

        Returns:
            Full path to saved model
        """
        os.makedirs(path, exist_ok=True)
        filename = f"{self.model_name}_{self.symbol}_{datetime.now().strftime('%Y%m%d')}.joblib"
        filepath = os.path.join(path, filename)

        model_data = {
            'model': self.model,
            'symbol': self.symbol,
            'model_name': self.model_name,
            'feature_columns': self.feature_columns,
            'training_date': self.training_date,
            'metrics': self.metrics,
            'is_trained': self.is_trained,
        }

        joblib.dump(model_data, filepath)
        logger.info(f"Model saved to {filepath}")
        return filepath

    def load(self, filepath: str) -> bool:
        """
        Load model from disk

        Args:
            filepath: Path to saved model

        Returns:
            True if loaded successfully
        """
        try:
            model_data = joblib.load(filepath)
            self.model = model_data['model']
            self.symbol = model_data['symbol']
            self.model_name = model_data['model_name']
            self.feature_columns = model_data['feature_columns']
            self.training_date = model_data['training_date']
            self.metrics = model_data['metrics']
            self.is_trained = model_data['is_trained']
            logger.info(f"Model loaded from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False

    def get_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            'model_name': self.model_name,
            'symbol': self.symbol,
            'is_trained': self.is_trained,
            'training_date': self.training_date,
            'num_features': len(self.feature_columns),
            'metrics': self.metrics,
        }
