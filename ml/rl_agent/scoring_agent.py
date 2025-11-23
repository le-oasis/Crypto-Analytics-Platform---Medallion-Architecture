"""
RL Scoring Agent

Reinforcement Learning agent that:
1. Scores predictions against actual results
2. Learns which models perform best
3. Adjusts ensemble weights based on performance
4. Tracks historical performance metrics
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import json

from ml.config import RL_CONFIG, SUPPORTED_SYMBOLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """Single prediction result"""
    date: datetime
    symbol: str
    model: str
    predicted_direction: int  # 1 = up, 0 = down
    predicted_confidence: float
    actual_direction: int
    actual_return: float
    score: float
    reward: float


class RLScoringAgent:
    """
    Reinforcement Learning agent for scoring predictions and adjusting model weights

    Uses a simple reward-based learning approach:
    - Correct direction predictions get positive reward
    - Wrong direction predictions get negative reward
    - Magnitude of actual move affects bonus/penalty
    - Weights are adjusted using exponential moving average
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or RL_CONFIG
        self.learning_rate = self.config['learning_rate']

        # Model weights per symbol
        self.weights: Dict[str, Dict[str, float]] = {}
        for symbol in SUPPORTED_SYMBOLS:
            self.weights[symbol] = self.config['initial_weights'].copy()

        # Performance tracking
        self.prediction_history: List[PredictionResult] = []
        self.daily_scores: Dict[str, List[float]] = {s: [] for s in SUPPORTED_SYMBOLS}
        self.model_scores: Dict[str, Dict[str, List[float]]] = {
            s: {m: [] for m in self.config['initial_weights'].keys()}
            for s in SUPPORTED_SYMBOLS
        }

        # Cumulative metrics
        self.total_predictions = 0
        self.correct_predictions = 0
        self.total_reward = 0.0

    def score_prediction(
        self,
        symbol: str,
        model: str,
        predicted_direction: int,
        predicted_confidence: float,
        actual_close: float,
        previous_close: float,
        prediction_date: datetime
    ) -> PredictionResult:
        """
        Score a single prediction against actual results

        Args:
            symbol: Cryptocurrency symbol
            model: Model name that made the prediction
            predicted_direction: 1 for up, 0 for down
            predicted_confidence: Model's confidence score
            actual_close: Actual closing price
            previous_close: Previous day's closing price
            prediction_date: Date the prediction was for

        Returns:
            PredictionResult with score and reward
        """
        # Calculate actual values
        actual_return = (actual_close - previous_close) / previous_close
        actual_direction = 1 if actual_return > 0 else 0

        # Direction score
        direction_correct = predicted_direction == actual_direction
        direction_score = 1.0 if direction_correct else 0.0

        # Magnitude component
        magnitude = abs(actual_return)
        magnitude_threshold = self.config['magnitude_bonus_threshold']

        if direction_correct:
            # Reward for correct direction
            reward = self.config['correct_direction_reward']
            # Bonus for large moves predicted correctly
            if magnitude > magnitude_threshold:
                reward *= (1 + magnitude / magnitude_threshold)
            # Confidence bonus
            reward *= (0.5 + 0.5 * predicted_confidence)
        else:
            # Penalty for wrong direction
            reward = self.config['wrong_direction_penalty']
            # Larger penalty for confident wrong predictions
            reward *= (0.5 + 0.5 * predicted_confidence)
            # Larger penalty for missing big moves
            if magnitude > magnitude_threshold:
                reward *= (1 + magnitude / magnitude_threshold)

        # Combined score (0-1 scale)
        score = (
            self.config['direction_weight'] * direction_score +
            self.config['magnitude_weight'] * min(1.0, magnitude / 0.1)  # Cap at 10% move
        )

        result = PredictionResult(
            date=prediction_date,
            symbol=symbol,
            model=model,
            predicted_direction=predicted_direction,
            predicted_confidence=predicted_confidence,
            actual_direction=actual_direction,
            actual_return=actual_return,
            score=score,
            reward=reward
        )

        # Track results
        self.prediction_history.append(result)
        self.total_predictions += 1
        if direction_correct:
            self.correct_predictions += 1
        self.total_reward += reward

        # Update model scores
        if symbol in self.model_scores and model in self.model_scores[symbol]:
            self.model_scores[symbol][model].append(reward)

        logger.info(
            f"Scored {symbol}/{model}: pred={predicted_direction}, "
            f"actual={actual_direction}, return={actual_return:.2%}, "
            f"correct={direction_correct}, reward={reward:.3f}"
        )

        return result

    def update_weights(self, symbol: str) -> Dict[str, float]:
        """
        Update model weights based on recent performance

        Uses exponential moving average of rewards to adjust weights.

        Args:
            symbol: Cryptocurrency symbol

        Returns:
            Updated weights dictionary
        """
        if symbol not in self.weights:
            return self.config['initial_weights'].copy()

        rolling_window = self.config['rolling_window']
        current_weights = self.weights[symbol]

        # Calculate recent performance for each model
        model_performance = {}
        for model_name in current_weights.keys():
            scores = self.model_scores.get(symbol, {}).get(model_name, [])
            if scores:
                # Use recent scores
                recent = scores[-rolling_window:]
                avg_score = np.mean(recent) if recent else 0
            else:
                avg_score = 0
            model_performance[model_name] = avg_score

        # Convert to weight adjustments
        # Models with positive avg score get weight increase
        # Models with negative avg score get weight decrease
        new_weights = {}
        for model_name, current_weight in current_weights.items():
            perf = model_performance.get(model_name, 0)

            # Weight adjustment based on performance
            adjustment = self.learning_rate * perf

            # Apply adjustment
            new_weight = current_weight + adjustment

            # Apply constraints
            new_weight = max(self.config['min_weight'], new_weight)
            new_weight = min(self.config['max_weight'], new_weight)

            new_weights[model_name] = new_weight

        # Normalize to sum to 1
        total = sum(new_weights.values())
        if total > 0:
            new_weights = {k: v/total for k, v in new_weights.items()}
        else:
            new_weights = self.config['initial_weights'].copy()

        # Update stored weights
        self.weights[symbol] = new_weights

        logger.info(f"Updated weights for {symbol}: {new_weights}")
        return new_weights

    def get_weights(self, symbol: str) -> Dict[str, float]:
        """Get current weights for a symbol"""
        return self.weights.get(symbol, self.config['initial_weights'].copy())

    def get_performance_summary(self, symbol: Optional[str] = None) -> Dict:
        """
        Get performance summary

        Args:
            symbol: Optional symbol to filter by

        Returns:
            Dictionary with performance metrics
        """
        if symbol:
            history = [p for p in self.prediction_history if p.symbol == symbol]
        else:
            history = self.prediction_history

        if not history:
            return {
                'total_predictions': 0,
                'accuracy': 0,
                'avg_reward': 0,
                'total_reward': 0
            }

        correct = sum(1 for p in history if p.predicted_direction == p.actual_direction)
        total = len(history)

        return {
            'total_predictions': total,
            'correct_predictions': correct,
            'accuracy': correct / total if total > 0 else 0,
            'avg_reward': np.mean([p.reward for p in history]),
            'total_reward': sum(p.reward for p in history),
            'avg_confidence': np.mean([p.predicted_confidence for p in history]),
            'avg_actual_return': np.mean([abs(p.actual_return) for p in history]),
        }

    def get_model_performance(self, symbol: str) -> Dict[str, Dict]:
        """Get performance breakdown by model for a symbol"""
        model_perf = {}

        for model_name in self.config['initial_weights'].keys():
            history = [
                p for p in self.prediction_history
                if p.symbol == symbol and p.model == model_name
            ]

            if history:
                correct = sum(1 for p in history if p.predicted_direction == p.actual_direction)
                model_perf[model_name] = {
                    'total': len(history),
                    'correct': correct,
                    'accuracy': correct / len(history),
                    'avg_reward': np.mean([p.reward for p in history]),
                    'current_weight': self.weights[symbol].get(model_name, 0),
                }
            else:
                model_perf[model_name] = {
                    'total': 0,
                    'correct': 0,
                    'accuracy': 0,
                    'avg_reward': 0,
                    'current_weight': self.weights[symbol].get(model_name, 0),
                }

        return model_perf

    def get_recent_predictions(
        self,
        symbol: Optional[str] = None,
        days: int = 7
    ) -> List[Dict]:
        """
        Get recent prediction results

        Args:
            symbol: Optional symbol filter
            days: Number of days to look back

        Returns:
            List of prediction result dictionaries
        """
        cutoff = datetime.now() - timedelta(days=days)

        results = []
        for p in self.prediction_history:
            if p.date >= cutoff:
                if symbol is None or p.symbol == symbol:
                    results.append({
                        'date': p.date.isoformat(),
                        'symbol': p.symbol,
                        'model': p.model,
                        'predicted': 'up' if p.predicted_direction == 1 else 'down',
                        'actual': 'up' if p.actual_direction == 1 else 'down',
                        'correct': p.predicted_direction == p.actual_direction,
                        'confidence': p.predicted_confidence,
                        'actual_return': p.actual_return,
                        'reward': p.reward,
                    })

        return sorted(results, key=lambda x: x['date'], reverse=True)

    def save_state(self, filepath: str):
        """Save agent state to file"""
        state = {
            'weights': self.weights,
            'model_scores': {
                s: {m: list(scores) for m, scores in models.items()}
                for s, models in self.model_scores.items()
            },
            'total_predictions': self.total_predictions,
            'correct_predictions': self.correct_predictions,
            'total_reward': self.total_reward,
            'history_count': len(self.prediction_history),
        }

        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)

        logger.info(f"Saved agent state to {filepath}")

    def load_state(self, filepath: str):
        """Load agent state from file"""
        try:
            with open(filepath, 'r') as f:
                state = json.load(f)

            self.weights = state.get('weights', self.weights)
            self.model_scores = state.get('model_scores', self.model_scores)
            self.total_predictions = state.get('total_predictions', 0)
            self.correct_predictions = state.get('correct_predictions', 0)
            self.total_reward = state.get('total_reward', 0.0)

            logger.info(f"Loaded agent state from {filepath}")
        except Exception as e:
            logger.error(f"Error loading agent state: {e}")


# Singleton instance for use across the application
_scoring_agent: Optional[RLScoringAgent] = None


def get_scoring_agent() -> RLScoringAgent:
    """Get or create the singleton scoring agent"""
    global _scoring_agent
    if _scoring_agent is None:
        _scoring_agent = RLScoringAgent()
    return _scoring_agent
