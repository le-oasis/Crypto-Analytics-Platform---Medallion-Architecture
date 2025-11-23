"""
Configuration for the ML/RL Prediction System
"""
import os
from datetime import timedelta

# Database Configuration
DATABASE_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'postgres'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
    'database': os.getenv('POSTGRES_DB', 'airflow'),
    'user': os.getenv('POSTGRES_USER', 'airflow'),
    'password': os.getenv('POSTGRES_PASSWORD', 'airflow'),
}

def get_db_connection_string():
    """Get PostgreSQL connection string"""
    return f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"

# Supported Cryptocurrencies
SUPPORTED_SYMBOLS = [
    'BTC-USD', 'ETH-USD', 'XRP-USD', 'ADA-USD', 'DOGE-USD',
    'BNB-USD', 'DOT-USD', 'LTC-USD', 'LINK-USD', 'MATIC-USD'
]

# Feature Engineering Configuration
FEATURE_CONFIG = {
    # Moving Average Windows
    'sma_windows': [5, 10, 20, 50],
    'ema_windows': [5, 10, 20, 50],

    # Technical Indicators
    'rsi_period': 14,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'bollinger_period': 20,
    'bollinger_std': 2,
    'atr_period': 14,

    # Momentum
    'roc_period': 10,
    'williams_r_period': 14,

    # Volume
    'volume_sma_period': 20,

    # Lookback for features
    'feature_lookback_days': 60,
}

# Model Configuration
MODEL_CONFIG = {
    # XGBoost
    'xgboost': {
        'n_estimators': 100,
        'max_depth': 6,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
    },

    # LightGBM
    'lightgbm': {
        'n_estimators': 100,
        'max_depth': 6,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'verbose': -1,
    },

    # LSTM
    'lstm': {
        'sequence_length': 30,
        'hidden_size': 64,
        'num_layers': 2,
        'dropout': 0.2,
        'learning_rate': 0.001,
        'epochs': 50,
        'batch_size': 32,
    },

    # Training
    'train_test_split': 0.8,
    'validation_split': 0.1,
    'min_training_samples': 100,
}

# RL Agent Configuration
RL_CONFIG = {
    # Initial model weights (equal weighting)
    'initial_weights': {
        'xgboost': 0.4,
        'lightgbm': 0.3,
        'lstm': 0.3,
    },

    # Learning parameters
    'learning_rate': 0.1,  # How fast to adjust weights
    'min_weight': 0.05,    # Minimum weight for any model
    'max_weight': 0.8,     # Maximum weight for any model

    # Scoring
    'direction_weight': 0.6,   # Weight for direction accuracy
    'magnitude_weight': 0.4,   # Weight for magnitude accuracy

    # Reward scaling
    'correct_direction_reward': 1.0,
    'wrong_direction_penalty': -1.0,
    'magnitude_bonus_threshold': 0.02,  # 2% threshold for bonus

    # Performance tracking
    'rolling_window': 30,  # Days to track rolling performance
}

# Prediction Configuration
PREDICTION_CONFIG = {
    # What to predict
    'target': 'next_day_return',  # or 'next_day_direction', 'next_day_close'

    # Confidence thresholds
    'high_confidence_threshold': 0.7,
    'low_confidence_threshold': 0.3,

    # Ensemble method
    'ensemble_method': 'weighted_average',  # or 'voting', 'stacking'
}

# Fear & Greed Index API
FEAR_GREED_CONFIG = {
    'api_url': 'https://api.alternative.me/fng/',
    'cache_duration': timedelta(hours=1),
}

# Model Storage
MODEL_STORAGE = {
    'base_path': '/opt/ml/models',
    'backup_path': '/opt/ml/models/backup',
}
