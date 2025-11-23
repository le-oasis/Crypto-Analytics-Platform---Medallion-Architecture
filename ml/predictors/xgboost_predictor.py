"""
XGBoost Predictor

Gradient boosting model for crypto price direction prediction.
Good for capturing non-linear relationships in tabular data.
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime
import logging

from ml.predictors.base_predictor import BasePredictor
from ml.config import MODEL_CONFIG
from ml.feature_engineering.technical_indicators import get_feature_columns

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class XGBoostPredictor(BasePredictor):
    """XGBoost-based price direction predictor"""

    def __init__(self, symbol: str, config: Optional[Dict] = None):
        super().__init__(symbol, 'xgboost')
        self.config = config or MODEL_CONFIG['xgboost']
        self.feature_columns = get_feature_columns()
        self.feature_importance = {}

    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """
        Train XGBoost model

        Args:
            X: Feature DataFrame
            y: Target Series (binary direction)

        Returns:
            Dictionary of training metrics
        """
        try:
            from xgboost import XGBClassifier
            from sklearn.model_selection import train_test_split
        except ImportError:
            logger.error("XGBoost not installed. Run: pip install xgboost")
            return {}

        # Prepare features
        X_clean = self.prepare_features(X)

        # Remove NaN targets
        mask = ~y.isna()
        X_clean = X_clean[mask]
        y_clean = y[mask]

        if len(X_clean) < MODEL_CONFIG['min_training_samples']:
            logger.warning(f"Not enough samples for training: {len(X_clean)}")
            return {}

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_clean, y_clean,
            test_size=1 - MODEL_CONFIG['train_test_split'],
            shuffle=False  # Keep temporal order
        )

        # Initialize and train model
        self.model = XGBClassifier(
            n_estimators=self.config['n_estimators'],
            max_depth=self.config['max_depth'],
            learning_rate=self.config['learning_rate'],
            subsample=self.config['subsample'],
            colsample_bytree=self.config['colsample_bytree'],
            random_state=self.config['random_state'],
            use_label_encoder=False,
            eval_metric='logloss',
            verbosity=0
        )

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )

        # Store feature importance
        self.feature_importance = dict(zip(
            X_clean.columns,
            self.model.feature_importances_
        ))

        # Evaluate
        y_pred = self.model.predict(X_test)
        self.metrics = self.evaluate(y_test, y_pred)

        # Add training info
        self.metrics['train_samples'] = len(X_train)
        self.metrics['test_samples'] = len(X_test)
        self.is_trained = True
        self.training_date = datetime.now()

        logger.info(f"XGBoost trained for {self.symbol}: accuracy={self.metrics['accuracy']:.3f}")
        return self.metrics

    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Make predictions

        Args:
            X: Feature DataFrame

        Returns:
            Tuple of (predictions, confidence_scores)
        """
        if not self.is_trained or self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        X_clean = self.prepare_features(X)

        # Get predictions and probabilities
        predictions = self.model.predict(X_clean)
        probabilities = self.model.predict_proba(X_clean)

        # Confidence is the probability of the predicted class
        confidence = np.max(probabilities, axis=1)

        return predictions, confidence

    def predict_single(self, X: pd.DataFrame) -> Dict:
        """
        Make prediction for a single day

        Args:
            X: Feature DataFrame (last row will be used)

        Returns:
            Dictionary with prediction details
        """
        if not self.is_trained:
            return {
                'prediction': None,
                'direction': 'unknown',
                'confidence': 0,
                'model': self.model_name
            }

        # Use last row
        X_latest = X.tail(1)
        predictions, confidence = self.predict(X_latest)

        return {
            'prediction': int(predictions[0]),
            'direction': 'up' if predictions[0] == 1 else 'down',
            'confidence': float(confidence[0]),
            'model': self.model_name,
            'symbol': self.symbol
        }

    def get_top_features(self, n: int = 10) -> Dict[str, float]:
        """Get top N most important features"""
        if not self.feature_importance:
            return {}

        sorted_features = sorted(
            self.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return dict(sorted_features[:n])
