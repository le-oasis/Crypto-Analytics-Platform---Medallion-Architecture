"""
ML Prediction Pipeline DAG

Daily workflow that:
1. Scores yesterday's predictions against actual results
2. Updates RL agent weights based on performance
3. Retrains models with latest data
4. Generates predictions for tomorrow

Schedule: Daily at 00:30 UTC (after market data is available)
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import logging
import sys

# Add ml module to path
sys.path.insert(0, '/opt/airflow')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default args
default_args = {
    'owner': 'crypto-analytics',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# DAG definition
dag = DAG(
    'ml_prediction_pipeline',
    default_args=default_args,
    description='Daily ML prediction pipeline - predict, score, learn',
    schedule_interval='30 0 * * *',  # 00:30 UTC daily
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['ml', 'prediction', 'rl'],
)


def initialize_ml_tables():
    """Initialize ML database tables if not exists"""
    from ml.utils.database import get_ml_database

    db = get_ml_database()
    db.initialize_tables()
    logger.info("ML tables initialized")


def score_pending_predictions(**context):
    """Score predictions from previous days"""
    from ml.pipeline import PredictionPipeline

    pipeline = PredictionPipeline()
    pipeline.initialize()

    results = pipeline.score_predictions()

    # Push results to XCom
    context['task_instance'].xcom_push(key='scored_count', value=len(results))
    context['task_instance'].xcom_push(key='scored_results', value=results)

    logger.info(f"Scored {len(results)} predictions")
    return results


def update_rl_weights(**context):
    """Update RL agent weights based on scoring results"""
    from ml.rl_agent.scoring_agent import get_scoring_agent
    from ml.config import SUPPORTED_SYMBOLS

    agent = get_scoring_agent()

    for symbol in SUPPORTED_SYMBOLS:
        new_weights = agent.update_weights(symbol)
        logger.info(f"Updated weights for {symbol}: {new_weights}")

    # Get overall performance
    perf = agent.get_performance_summary()
    context['task_instance'].xcom_push(key='overall_accuracy', value=perf.get('accuracy', 0))

    return perf


def refresh_features(**context):
    """Refresh feature calculations for all symbols"""
    from ml.pipeline import PredictionPipeline
    from ml.config import SUPPORTED_SYMBOLS

    pipeline = PredictionPipeline()

    features_prepared = 0
    for symbol in SUPPORTED_SYMBOLS:
        try:
            df = pipeline.prepare_features(symbol)
            if not df.empty:
                features_prepared += 1
                logger.info(f"Prepared {len(df)} feature rows for {symbol}")
        except Exception as e:
            logger.error(f"Error preparing features for {symbol}: {e}")

    context['task_instance'].xcom_push(key='features_prepared', value=features_prepared)
    return features_prepared


def train_models(**context):
    """Train/retrain prediction models"""
    from ml.pipeline import PredictionPipeline
    from ml.config import SUPPORTED_SYMBOLS

    pipeline = PredictionPipeline()
    pipeline.initialize()

    # First refresh features
    for symbol in SUPPORTED_SYMBOLS:
        pipeline.prepare_features(symbol)

    # Train models
    training_results = {}
    for symbol in SUPPORTED_SYMBOLS:
        try:
            metrics = pipeline.train_models(symbol)
            training_results[symbol] = metrics
            logger.info(f"Trained models for {symbol}: accuracy={metrics.get('accuracy', 0):.3f}")
        except Exception as e:
            logger.error(f"Error training models for {symbol}: {e}")
            training_results[symbol] = {'error': str(e)}

    context['task_instance'].xcom_push(key='training_results', value=training_results)
    return training_results


def generate_predictions(**context):
    """Generate predictions for tomorrow"""
    from ml.pipeline import PredictionPipeline
    from datetime import date, timedelta

    pipeline = PredictionPipeline()
    pipeline.initialize()

    # Prepare features first
    from ml.config import SUPPORTED_SYMBOLS
    for symbol in SUPPORTED_SYMBOLS:
        pipeline.prepare_features(symbol)
        pipeline.train_models(symbol)

    # Generate predictions for tomorrow
    tomorrow = date.today() + timedelta(days=1)
    predictions = pipeline.generate_all_predictions(tomorrow)

    # Summary
    pred_summary = []
    for pred in predictions:
        pred_summary.append({
            'symbol': pred['symbol'],
            'direction': pred['direction'],
            'confidence': f"{pred['confidence']:.1%}",
        })

    context['task_instance'].xcom_push(key='predictions', value=pred_summary)
    context['task_instance'].xcom_push(key='prediction_count', value=len(predictions))

    logger.info(f"Generated {len(predictions)} predictions for {tomorrow}")
    return predictions


def log_pipeline_summary(**context):
    """Log pipeline execution summary"""
    ti = context['task_instance']

    scored_count = ti.xcom_pull(task_ids='score_predictions', key='scored_count') or 0
    accuracy = ti.xcom_pull(task_ids='update_rl_weights', key='overall_accuracy') or 0
    pred_count = ti.xcom_pull(task_ids='generate_predictions', key='prediction_count') or 0
    predictions = ti.xcom_pull(task_ids='generate_predictions', key='predictions') or []

    logger.info("=" * 60)
    logger.info("ML PREDICTION PIPELINE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Predictions scored: {scored_count}")
    logger.info(f"Overall accuracy: {accuracy:.1%}")
    logger.info(f"New predictions generated: {pred_count}")
    logger.info("")
    logger.info("Tomorrow's Predictions:")
    for pred in predictions:
        logger.info(f"  {pred['symbol']}: {pred['direction'].upper()} ({pred['confidence']})")
    logger.info("=" * 60)


# Task definitions
init_tables = PythonOperator(
    task_id='init_ml_tables',
    python_callable=initialize_ml_tables,
    dag=dag,
)

score_predictions = PythonOperator(
    task_id='score_predictions',
    python_callable=score_pending_predictions,
    dag=dag,
)

update_weights = PythonOperator(
    task_id='update_rl_weights',
    python_callable=update_rl_weights,
    dag=dag,
)

refresh_feats = PythonOperator(
    task_id='refresh_features',
    python_callable=refresh_features,
    dag=dag,
)

train = PythonOperator(
    task_id='train_models',
    python_callable=train_models,
    dag=dag,
)

predict = PythonOperator(
    task_id='generate_predictions',
    python_callable=generate_predictions,
    dag=dag,
)

summary = PythonOperator(
    task_id='log_summary',
    python_callable=log_pipeline_summary,
    dag=dag,
)

# Task dependencies
# init_tables >> score_predictions >> update_weights >> refresh_feats >> train >> predict >> summary
init_tables >> score_predictions >> update_weights
update_weights >> refresh_feats >> train >> predict >> summary
