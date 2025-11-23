"""
Technical Indicators for Crypto Price Prediction

Calculates various technical indicators from OHLCV data:
- Trend indicators (SMA, EMA, MACD)
- Momentum indicators (RSI, ROC, Williams %R)
- Volatility indicators (Bollinger Bands, ATR)
- Volume indicators (OBV, Volume SMA)
"""
import pandas as pd
import numpy as np
from typing import Optional
import sys
sys.path.append('..')
from ml.config import FEATURE_CONFIG


class TechnicalIndicators:
    """Calculate technical indicators from OHLCV data"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or FEATURE_CONFIG

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all technical indicators

        Args:
            df: DataFrame with columns: timestamp, open, high, low, close, volume

        Returns:
            DataFrame with all technical indicators added
        """
        df = df.copy()
        df = df.sort_values('timestamp').reset_index(drop=True)

        # Trend Indicators
        df = self._add_moving_averages(df)
        df = self._add_macd(df)

        # Momentum Indicators
        df = self._add_rsi(df)
        df = self._add_roc(df)
        df = self._add_williams_r(df)

        # Volatility Indicators
        df = self._add_bollinger_bands(df)
        df = self._add_atr(df)

        # Volume Indicators
        df = self._add_obv(df)
        df = self._add_volume_sma(df)

        # Price-based features
        df = self._add_price_features(df)

        # Lag features
        df = self._add_lag_features(df)

        return df

    def _add_moving_averages(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Simple and Exponential Moving Averages"""
        for window in self.config['sma_windows']:
            df[f'sma_{window}'] = df['close'].rolling(window=window).mean()
            df[f'close_to_sma_{window}'] = df['close'] / df[f'sma_{window}'] - 1

        for window in self.config['ema_windows']:
            df[f'ema_{window}'] = df['close'].ewm(span=window, adjust=False).mean()
            df[f'close_to_ema_{window}'] = df['close'] / df[f'ema_{window}'] - 1

        # Golden/Death Cross signals
        if 50 in self.config['sma_windows'] and 20 in self.config['sma_windows']:
            df['sma_20_50_ratio'] = df['sma_20'] / df['sma_50']
            df['golden_cross'] = (df['sma_20'] > df['sma_50']).astype(int)

        return df

    def _add_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add MACD indicator"""
        fast = self.config['macd_fast']
        slow = self.config['macd_slow']
        signal = self.config['macd_signal']

        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()

        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']

        # MACD crossover signals
        df['macd_crossover'] = np.where(
            (df['macd'] > df['macd_signal']) & (df['macd'].shift(1) <= df['macd_signal'].shift(1)),
            1,
            np.where(
                (df['macd'] < df['macd_signal']) & (df['macd'].shift(1) >= df['macd_signal'].shift(1)),
                -1,
                0
            )
        )

        return df

    def _add_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Relative Strength Index"""
        period = self.config['rsi_period']

        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # RSI zones
        df['rsi_oversold'] = (df['rsi'] < 30).astype(int)
        df['rsi_overbought'] = (df['rsi'] > 70).astype(int)

        return df

    def _add_roc(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Rate of Change"""
        period = self.config['roc_period']
        df['roc'] = ((df['close'] - df['close'].shift(period)) / df['close'].shift(period)) * 100
        return df

    def _add_williams_r(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Williams %R"""
        period = self.config['williams_r_period']

        highest_high = df['high'].rolling(window=period).max()
        lowest_low = df['low'].rolling(window=period).min()

        df['williams_r'] = ((highest_high - df['close']) / (highest_high - lowest_low)) * -100

        return df

    def _add_bollinger_bands(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Bollinger Bands"""
        period = self.config['bollinger_period']
        std_dev = self.config['bollinger_std']

        df['bb_middle'] = df['close'].rolling(window=period).mean()
        bb_std = df['close'].rolling(window=period).std()

        df['bb_upper'] = df['bb_middle'] + (bb_std * std_dev)
        df['bb_lower'] = df['bb_middle'] - (bb_std * std_dev)

        # Bollinger Band width and position
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

        return df

    def _add_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Average True Range"""
        period = self.config['atr_period']

        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=period).mean()

        # ATR as percentage of price
        df['atr_pct'] = df['atr'] / df['close'] * 100

        return df

    def _add_obv(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add On-Balance Volume"""
        obv = [0]
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.append(obv[-1] + df['volume'].iloc[i])
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.append(obv[-1] - df['volume'].iloc[i])
            else:
                obv.append(obv[-1])

        df['obv'] = obv
        df['obv_sma'] = df['obv'].rolling(window=20).mean()
        df['obv_trend'] = (df['obv'] > df['obv_sma']).astype(int)

        return df

    def _add_volume_sma(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Volume Moving Average"""
        period = self.config['volume_sma_period']
        df['volume_sma'] = df['volume'].rolling(window=period).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']

        return df

    def _add_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add price-based features"""
        # Daily returns
        df['daily_return'] = df['close'].pct_change()
        df['log_return'] = np.log(df['close'] / df['close'].shift(1))

        # Volatility
        df['volatility_5d'] = df['daily_return'].rolling(window=5).std()
        df['volatility_20d'] = df['daily_return'].rolling(window=20).std()

        # Price momentum
        df['momentum_5d'] = df['close'] / df['close'].shift(5) - 1
        df['momentum_10d'] = df['close'] / df['close'].shift(10) - 1
        df['momentum_20d'] = df['close'] / df['close'].shift(20) - 1

        # High-Low range
        df['hl_range'] = (df['high'] - df['low']) / df['close']

        # Close position in daily range
        df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])

        # Gap (open vs previous close)
        df['gap'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)

        return df

    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add lagged features for time series"""
        # Lag returns
        for lag in [1, 2, 3, 5, 7]:
            df[f'return_lag_{lag}'] = df['daily_return'].shift(lag)

        # Lag volume ratio
        for lag in [1, 2, 3]:
            df[f'volume_ratio_lag_{lag}'] = df['volume_ratio'].shift(lag)

        # Lag RSI
        df['rsi_lag_1'] = df['rsi'].shift(1)
        df['rsi_lag_3'] = df['rsi'].shift(3)

        return df


def calculate_features_for_symbol(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Calculate all features for a single symbol

    Args:
        df: DataFrame with OHLCV data for one symbol
        symbol: The cryptocurrency symbol

    Returns:
        DataFrame with all features calculated
    """
    ti = TechnicalIndicators()
    df_features = ti.calculate_all(df)
    df_features['symbol'] = symbol
    return df_features


def get_feature_columns() -> list:
    """Get list of all feature column names"""
    return [
        # Moving Averages
        'sma_5', 'sma_10', 'sma_20', 'sma_50',
        'ema_5', 'ema_10', 'ema_20', 'ema_50',
        'close_to_sma_5', 'close_to_sma_10', 'close_to_sma_20', 'close_to_sma_50',
        'close_to_ema_5', 'close_to_ema_10', 'close_to_ema_20', 'close_to_ema_50',
        'sma_20_50_ratio', 'golden_cross',

        # MACD
        'macd', 'macd_signal', 'macd_histogram', 'macd_crossover',

        # RSI
        'rsi', 'rsi_oversold', 'rsi_overbought', 'rsi_lag_1', 'rsi_lag_3',

        # Momentum
        'roc', 'williams_r',
        'momentum_5d', 'momentum_10d', 'momentum_20d',

        # Volatility
        'bb_width', 'bb_position', 'atr', 'atr_pct',
        'volatility_5d', 'volatility_20d',

        # Volume
        'obv_trend', 'volume_ratio',
        'volume_ratio_lag_1', 'volume_ratio_lag_2', 'volume_ratio_lag_3',

        # Price features
        'daily_return', 'log_return', 'hl_range', 'close_position', 'gap',
        'return_lag_1', 'return_lag_2', 'return_lag_3', 'return_lag_5', 'return_lag_7',
    ]
