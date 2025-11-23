"""
ML/RL Prediction System for Crypto Analytics Platform

This module provides:
- Technical indicator feature engineering
- XGBoost and LightGBM price direction predictors
- Ensemble model with adaptive weighting
- RL scoring agent that learns from prediction results
- Database utilities for storing predictions and scores
- Main pipeline orchestrator for daily predictions
"""

from ml.config import SUPPORTED_SYMBOLS, FEATURE_CONFIG, MODEL_CONFIG, RL_CONFIG

__version__ = "1.0.0"
__all__ = [
    "SUPPORTED_SYMBOLS",
    "FEATURE_CONFIG",
    "MODEL_CONFIG",
    "RL_CONFIG",
]
