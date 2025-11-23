"""
Fear & Greed Index Integration

Fetches the Crypto Fear & Greed Index from alternative.me API
This is a key sentiment indicator for crypto markets.
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FEAR_GREED_API_URL = "https://api.alternative.me/fng/"


class FearGreedIndex:
    """Fetch and process Fear & Greed Index data"""

    def __init__(self):
        self.api_url = FEAR_GREED_API_URL
        self._cache = {}
        self._cache_timestamp = None
        self._cache_duration = timedelta(hours=1)

    def get_current(self) -> Dict[str, Any]:
        """
        Get current Fear & Greed Index value

        Returns:
            Dict with value, classification, and timestamp
        """
        try:
            response = requests.get(f"{self.api_url}?limit=1", timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'data' in data and len(data['data']) > 0:
                fng = data['data'][0]
                return {
                    'value': int(fng['value']),
                    'classification': fng['value_classification'],
                    'timestamp': datetime.fromtimestamp(int(fng['timestamp'])),
                    'time_until_update': fng.get('time_until_update', None)
                }
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed Index: {e}")

        return {
            'value': None,
            'classification': 'Unknown',
            'timestamp': datetime.now(),
            'time_until_update': None
        }

    def get_historical(self, days: int = 365) -> pd.DataFrame:
        """
        Get historical Fear & Greed Index data

        Args:
            days: Number of days of history to fetch

        Returns:
            DataFrame with columns: date, value, classification
        """
        try:
            response = requests.get(f"{self.api_url}?limit={days}", timeout=30)
            response.raise_for_status()
            data = response.json()

            if 'data' in data:
                records = []
                for item in data['data']:
                    records.append({
                        'date': datetime.fromtimestamp(int(item['timestamp'])).date(),
                        'fear_greed_value': int(item['value']),
                        'fear_greed_classification': item['value_classification']
                    })

                df = pd.DataFrame(records)
                df['date'] = pd.to_datetime(df['date'])
                return df.sort_values('date').reset_index(drop=True)

        except Exception as e:
            logger.error(f"Error fetching historical Fear & Greed data: {e}")

        return pd.DataFrame()

    def classify_value(self, value: int) -> str:
        """
        Classify Fear & Greed value

        Args:
            value: Fear & Greed Index value (0-100)

        Returns:
            Classification string
        """
        if value is None:
            return 'Unknown'
        elif value <= 25:
            return 'Extreme Fear'
        elif value <= 45:
            return 'Fear'
        elif value <= 55:
            return 'Neutral'
        elif value <= 75:
            return 'Greed'
        else:
            return 'Extreme Greed'

    def add_fear_greed_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Fear & Greed features to a DataFrame

        Args:
            df: DataFrame with a 'date' or 'timestamp' column

        Returns:
            DataFrame with fear_greed_value and derived features
        """
        # Get historical data
        historical_fg = self.get_historical(days=730)

        if historical_fg.empty:
            logger.warning("Could not fetch Fear & Greed data, using neutral values")
            df['fear_greed_value'] = 50
            df['fear_greed_classification'] = 'Neutral'
        else:
            # Ensure date column
            if 'date' not in df.columns and 'timestamp' in df.columns:
                df['date'] = pd.to_datetime(df['timestamp']).dt.date
                df['date'] = pd.to_datetime(df['date'])

            # Merge with historical data
            df = df.merge(
                historical_fg[['date', 'fear_greed_value', 'fear_greed_classification']],
                on='date',
                how='left'
            )

            # Forward fill missing values
            df['fear_greed_value'] = df['fear_greed_value'].ffill().bfill()

        # Add derived features
        df['fg_extreme_fear'] = (df['fear_greed_value'] <= 25).astype(int)
        df['fg_fear'] = ((df['fear_greed_value'] > 25) & (df['fear_greed_value'] <= 45)).astype(int)
        df['fg_neutral'] = ((df['fear_greed_value'] > 45) & (df['fear_greed_value'] <= 55)).astype(int)
        df['fg_greed'] = ((df['fear_greed_value'] > 55) & (df['fear_greed_value'] <= 75)).astype(int)
        df['fg_extreme_greed'] = (df['fear_greed_value'] > 75).astype(int)

        # Moving averages of Fear & Greed
        df['fg_sma_7'] = df['fear_greed_value'].rolling(window=7, min_periods=1).mean()
        df['fg_sma_30'] = df['fear_greed_value'].rolling(window=30, min_periods=1).mean()

        # Fear & Greed momentum
        df['fg_change_1d'] = df['fear_greed_value'].diff(1)
        df['fg_change_7d'] = df['fear_greed_value'].diff(7)

        return df


def get_fear_greed_summary() -> Dict[str, Any]:
    """Get a summary of current Fear & Greed status"""
    fg = FearGreedIndex()
    current = fg.get_current()

    # Get recent history for context
    historical = fg.get_historical(days=30)

    summary = {
        'current_value': current['value'],
        'current_classification': current['classification'],
        'timestamp': current['timestamp'],
    }

    if not historical.empty:
        summary['avg_7d'] = historical.tail(7)['fear_greed_value'].mean()
        summary['avg_30d'] = historical['fear_greed_value'].mean()
        summary['min_30d'] = historical['fear_greed_value'].min()
        summary['max_30d'] = historical['fear_greed_value'].max()
        summary['trend'] = 'Up' if current['value'] > summary['avg_7d'] else 'Down'

    return summary


if __name__ == "__main__":
    # Test the Fear & Greed Index fetcher
    fg = FearGreedIndex()

    print("Current Fear & Greed Index:")
    current = fg.get_current()
    print(f"  Value: {current['value']}")
    print(f"  Classification: {current['classification']}")
    print(f"  Timestamp: {current['timestamp']}")

    print("\nHistorical Data (last 7 days):")
    hist = fg.get_historical(days=7)
    print(hist)

    print("\nSummary:")
    summary = get_fear_greed_summary()
    for k, v in summary.items():
        print(f"  {k}: {v}")
