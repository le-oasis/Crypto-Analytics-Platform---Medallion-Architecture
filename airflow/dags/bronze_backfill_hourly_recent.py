"""
Recent Hourly Data Backfill DAG
Loads hourly cryptocurrency data for the last 730 days (2 years).
This respects Yahoo Finance's limit of 730 days for hourly data.
Run this DAG once manually to populate recent hourly data for ML models.
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
    'DOGE-USD',   # Dogecoin
    'BNB-USD',   # Binance Coin
    'DOT-USD',   # Polkadot
    'LTC-USD',   # Litecoin
    'LINK-USD'   # Chainlink
]

# Recent hourly data configuration (last 729 days to be safe)
START_DATE = (datetime.now() - timedelta(days=729)).strftime('%Y-%m-%d')
END_DATE = datetime.now().strftime('%Y-%m-%d')
INTERVAL = '1h'  # Hourly data

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'bronze_backfill_hourly_recent',
    default_args=default_args,
    description='One-time backfill of hourly crypto data for last 2 years (730 days)',
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['bronze', 'backfill', 'hourly', 'recent']
)


def fetch_hourly_recent_data(**context):
    """
    Fetch recent hourly cryptocurrency data from Yahoo Finance.
    Fetches last 729 days to respect Yahoo Finance 730-day limit.
    """
    logger = logging.getLogger(__name__)
    all_data = []

    logger.info(f"Starting hourly recent backfill from {START_DATE} to {END_DATE}")
    logger.info(f"Fetching {len(CRYPTO_SYMBOLS)} symbols with hourly ({INTERVAL}) interval")
    logger.info(f"This respects Yahoo Finance's 730-day limit for hourly data")

    # Process each symbol
    for symbol in CRYPTO_SYMBOLS:
        try:
            logger.info(f"Fetching {symbol} from {START_DATE} to {END_DATE}")

            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=START_DATE,
                end=END_DATE,
                interval=INTERVAL
            )

            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                continue

            # Add symbol and metadata
            df['symbol'] = symbol
            df['source'] = 'yahoo_finance_hourly'
            df['interval'] = '1h'
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

            # Convert timestamps to strings for JSON serialization
            df['timestamp'] = df['timestamp'].astype(str)

            # Convert to records
            records = df.to_dict('records')
            all_data.extend(records)

            logger.info(f"✓ {symbol}: {len(records)} hourly records fetched")

        except Exception as e:
            logger.error(f"Error fetching {symbol}: {str(e)}")
            continue

    logger.info(f"=" * 60)
    logger.info(f"Total hourly records fetched: {len(all_data)}")
    logger.info(f"=" * 60)

    # Push to XCom for next task
    context['ti'].xcom_push(key='hourly_recent_data', value=all_data)

    return len(all_data)


def validate_hourly_data(**context):
    """
    Validate fetched hourly recent data.
    """
    logger = logging.getLogger(__name__)
    data = context['ti'].xcom_pull(key='hourly_recent_data', task_ids='fetch_hourly_recent_data')

    if not data:
        raise ValueError("No hourly recent data to validate")

    df = pd.DataFrame(data)

    # Validation checks
    checks = {
        'total_records': len(df),
        'symbols_found': df['symbol'].nunique(),
        'date_range_start': df['timestamp'].min(),
        'date_range_end': df['timestamp'].max(),
        'null_prices': df['close'].isnull().sum(),
        'negative_prices': (df['close'] < 0).sum(),
    }

    logger.info("=" * 60)
    logger.info("Hourly Recent Data Validation Results:")
    logger.info("-" * 60)
    for check, value in checks.items():
        logger.info(f"  {check}: {value}")
    logger.info("=" * 60)

    # Quality checks
    if checks['symbols_found'] < 5:
        raise ValueError(f"Only {checks['symbols_found']} symbols found, expected {len(CRYPTO_SYMBOLS)}")

    if checks['total_records'] < 10000:
        logger.warning(f"Low record count: {checks['total_records']}")

    return checks


def load_hourly_to_bronze(**context):
    """
    Load validated hourly recent data into Bronze layer.
    """
    logger = logging.getLogger(__name__)
    data = context['ti'].xcom_pull(key='hourly_recent_data', task_ids='fetch_hourly_recent_data')

    if not data:
        raise ValueError("No hourly data to load")

    pg_hook = PostgresHook(postgres_conn_id='postgres_default')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()

    # Batch size for inserts
    BATCH_SIZE = 1000
    total_inserted = 0
    total_duplicates = 0

    logger.info(f"Loading {len(data)} hourly records to Bronze in batches of {BATCH_SIZE}")

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
    logger.info("Hourly Recent Backfill Complete!")
    logger.info(f"  Total inserted: {total_inserted}")
    logger.info(f"  Duplicates skipped: {total_duplicates}")
    logger.info(f"  Total processed: {len(data)}")
    logger.info("=" * 60)

    return {
        'inserted': total_inserted,
        'duplicates': total_duplicates,
        'total': len(data)
    }


def verify_hourly_data(**context):
    """
    Verify Bronze layer has hourly recent data.
    """
    logger = logging.getLogger(__name__)
    pg_hook = PostgresHook(postgres_conn_id='postgres_default')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()

    # Check hourly data coverage
    cursor.execute("""
        SELECT
            symbol,
            COUNT(*) as record_count,
            MIN(timestamp) as earliest_date,
            MAX(timestamp) as latest_date
        FROM bronze.raw_crypto_prices
        WHERE source = 'yahoo_finance_hourly'
        GROUP BY symbol
        ORDER BY symbol
    """)

    results = cursor.fetchall()

    logger.info("=" * 80)
    logger.info("Bronze Layer Hourly Data Coverage:")
    logger.info("-" * 80)
    logger.info(f"{'Symbol':<12} {'Records':<12} {'Earliest':<20} {'Latest':<20}")
    logger.info("-" * 80)

    for row in results:
        symbol, count, earliest, latest = row
        logger.info(f"{symbol:<12} {count:<12} {str(earliest):<20} {str(latest):<20}")

    logger.info("=" * 80)

    cursor.close()
    conn.close()

    return True


# Define tasks
fetch_task = PythonOperator(
    task_id='fetch_hourly_recent_data',
    python_callable=fetch_hourly_recent_data,
    dag=dag
)

validate_task = PythonOperator(
    task_id='validate_hourly_data',
    python_callable=validate_hourly_data,
    dag=dag
)

load_task = PythonOperator(
    task_id='load_hourly_to_bronze',
    python_callable=load_hourly_to_bronze,
    dag=dag
)

verify_task = PythonOperator(
    task_id='verify_hourly_data',
    python_callable=verify_hourly_data,
    dag=dag
)

# Task flow
fetch_task >> validate_task >> load_task >> verify_task
