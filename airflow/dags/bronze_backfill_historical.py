"""
Historical Data Backfill DAG
Loads cryptocurrency data from 2018-01-01 to present into Bronze layer.
Run this DAG once manually to populate historical data for ML model training.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import yfinance as yf
import pandas as pd
import logging

# Cryptocurrency symbols to track
CRYPTO_SYMBOLS = [
    'BTC-USD',   # Bitcoin
    'ETH-USD',   # Ethereum
    'XRP-USD',   # Ripple
    'ADA-USD',   # Cardano
    'DOGE-USD',  # Dogecoin
    'BNB-USD',   # Binance Coin
    'DOT-USD',   # Polkadot
    'LTC-USD',   # Litecoin
    'LINK-USD'   # Chainlink
]

# Historical data configuration
START_DATE = '2018-01-01'
INTERVAL = '1h'  # Hourly data to avoid API rate limits

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'bronze_backfill_historical',
    default_args=default_args,
    description='One-time backfill of historical crypto data from 2018 to present',
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['bronze', 'backfill', 'historical']
)


def fetch_historical_data(**context):
    """
    Fetch historical cryptocurrency data from Yahoo Finance (2018-present).
    Processes data in yearly batches to avoid memory issues.
    """
    logger = logging.getLogger(__name__)
    all_data = []

    # Calculate end date (today)
    end_date = datetime.now().strftime('%Y-%m-%d')

    logger.info(f"Starting historical backfill from {START_DATE} to {end_date}")
    logger.info(f"Fetching {len(CRYPTO_SYMBOLS)} symbols with {INTERVAL} interval")

    # Process each symbol
    for symbol in CRYPTO_SYMBOLS:
        try:
            logger.info(f"Fetching {symbol} from {START_DATE} to {end_date}")

            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=START_DATE,
                end=end_date,
                interval=INTERVAL
            )

            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                continue

            # Add symbol and metadata
            df['symbol'] = symbol
            df['source'] = 'yahoo_finance_historical'
            df.reset_index(inplace=True)

            # Rename columns to match our schema
            df.rename(columns={
                'Datetime': 'timestamp',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            }, inplace=True)

            # Select only needed columns
            df = df[['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'source']]

            # Convert to records
            records = df.to_dict('records')
            all_data.extend(records)

            logger.info(f"✓ {symbol}: {len(records)} records fetched")

        except Exception as e:
            logger.error(f"Error fetching {symbol}: {str(e)}")
            continue

    logger.info(f"Total records fetched: {len(all_data)}")

    # Push to XCom for next task
    context['ti'].xcom_push(key='historical_data', value=all_data)

    return len(all_data)


def validate_historical_data(**context):
    """
    Validate fetched historical data before loading to Bronze.
    """
    logger = logging.getLogger(__name__)
    data = context['ti'].xcom_pull(key='historical_data', task_ids='fetch_historical_data')

    if not data:
        raise ValueError("No historical data to validate")

    df = pd.DataFrame(data)

    # Validation checks
    checks = {
        'total_records': len(df),
        'symbols_found': df['symbol'].nunique(),
        'date_range_start': df['timestamp'].min(),
        'date_range_end': df['timestamp'].max(),
        'null_prices': df['close'].isnull().sum(),
        'negative_prices': (df['close'] < 0).sum(),
        'zero_volumes': (df['volume'] == 0).sum()
    }

    logger.info("Historical Data Validation Results:")
    for check, value in checks.items():
        logger.info(f"  {check}: {value}")

    # Quality checks
    if checks['symbols_found'] < 5:
        raise ValueError(f"Only {checks['symbols_found']} symbols found, expected {len(CRYPTO_SYMBOLS)}")

    if checks['total_records'] < 10000:
        logger.warning(f"Low record count: {checks['total_records']}")

    return checks


def load_historical_to_bronze(**context):
    """
    Load validated historical data into Bronze layer.
    Uses batch inserts for performance.
    """
    logger = logging.getLogger(__name__)
    data = context['ti'].xcom_pull(key='historical_data', task_ids='fetch_historical_data')

    if not data:
        raise ValueError("No data to load")

    pg_hook = PostgresHook(postgres_conn_id='postgres_default')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()

    # Batch size for inserts
    BATCH_SIZE = 1000
    total_inserted = 0
    total_duplicates = 0

    logger.info(f"Loading {len(data)} records to Bronze in batches of {BATCH_SIZE}")

    # Process in batches
    for i in range(0, len(data), BATCH_SIZE):
        batch = data[i:i+BATCH_SIZE]

        for record in batch:
            try:
                cursor.execute("""
                    INSERT INTO bronze.raw_crypto_prices
                    (timestamp, symbol, open, high, low, close, volume, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (timestamp, symbol, source) DO NOTHING
                """, (
                    record['timestamp'],
                    record['symbol'],
                    record['open'],
                    record['high'],
                    record['low'],
                    record['close'],
                    record['volume'],
                    record['source']
                ))

                if cursor.rowcount > 0:
                    total_inserted += 1
                else:
                    total_duplicates += 1

            except Exception as e:
                logger.error(f"Error inserting record: {e}")
                continue

        # Commit batch
        conn.commit()
        logger.info(f"Batch {i//BATCH_SIZE + 1}: Inserted {total_inserted} records so far")

    cursor.close()
    conn.close()

    logger.info("=" * 60)
    logger.info("Historical Backfill Complete!")
    logger.info(f"  Total inserted: {total_inserted}")
    logger.info(f"  Duplicates skipped: {total_duplicates}")
    logger.info(f"  Total processed: {len(data)}")
    logger.info("=" * 60)

    return {
        'inserted': total_inserted,
        'duplicates': total_duplicates,
        'total': len(data)
    }


def check_bronze_data_completeness(**context):
    """
    Verify Bronze layer has expected historical data coverage.
    """
    logger = logging.getLogger(__name__)
    pg_hook = PostgresHook(postgres_conn_id='postgres_default')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()

    # Check data coverage by symbol
    cursor.execute("""
        SELECT
            symbol,
            COUNT(*) as record_count,
            MIN(timestamp) as earliest_date,
            MAX(timestamp) as latest_date,
            MAX(timestamp) - MIN(timestamp) as date_range
        FROM bronze.raw_crypto_prices
        WHERE source IN ('yahoo_finance', 'yahoo_finance_historical')
        GROUP BY symbol
        ORDER BY symbol
    """)

    results = cursor.fetchall()

    logger.info("=" * 80)
    logger.info("Bronze Layer Data Coverage:")
    logger.info("-" * 80)
    logger.info(f"{'Symbol':<12} {'Records':<12} {'Earliest':<20} {'Latest':<20}")
    logger.info("-" * 80)

    for row in results:
        symbol, count, earliest, latest, date_range = row
        logger.info(f"{symbol:<12} {count:<12} {str(earliest):<20} {str(latest):<20}")

    logger.info("=" * 80)

    cursor.close()
    conn.close()

    return True


# Define task dependencies
fetch_task = PythonOperator(
    task_id='fetch_historical_data',
    python_callable=fetch_historical_data,
    dag=dag
)

validate_task = PythonOperator(
    task_id='validate_historical_data',
    python_callable=validate_historical_data,
    dag=dag
)

load_task = PythonOperator(
    task_id='load_historical_to_bronze',
    python_callable=load_historical_to_bronze,
    dag=dag
)

check_task = PythonOperator(
    task_id='check_data_completeness',
    python_callable=check_bronze_data_completeness,
    dag=dag
)

# Task flow
fetch_task >> validate_task >> load_task >> check_task
