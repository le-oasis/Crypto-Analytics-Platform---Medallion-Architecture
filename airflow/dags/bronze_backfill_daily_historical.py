"""
Historical Daily Data Backfill DAG
Loads daily cryptocurrency data from 2018 to 2 years ago.
This avoids Yahoo Finance's 730-day limit for hourly data.
Run this DAG once manually to populate long-term historical data.
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

# Historical daily data configuration
START_DATE = '2018-01-01'
# End date: 730 days ago (where hourly data starts)
END_DATE = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
INTERVAL = '1d'  # Daily data

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'bronze_backfill_daily_historical',
    default_args=default_args,
    description='One-time backfill of daily crypto data from 2018 to 2 years ago',
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['bronze', 'backfill', 'historical', 'daily']
)


def fetch_daily_historical_data(**context):
    """
    Fetch daily historical cryptocurrency data from Yahoo Finance.
    Fetches from 2018 to 730 days ago (to avoid overlap with hourly data).
    """
    logger = logging.getLogger(__name__)
    all_data = []

    logger.info(f"Starting daily historical backfill from {START_DATE} to {END_DATE}")
    logger.info(f"Fetching {len(CRYPTO_SYMBOLS)} symbols with daily ({INTERVAL}) interval")

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
            df['source'] = 'yahoo_finance_daily'
            df['interval'] = '1d'
            df.reset_index(inplace=True)

            # Rename columns to match our schema
            df.rename(columns={
                'Date': 'timestamp',
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

            logger.info(f"✓ {symbol}: {len(records)} daily records fetched")

        except Exception as e:
            logger.error(f"Error fetching {symbol}: {str(e)}")
            continue

    logger.info(f"=" * 60)
    logger.info(f"Total daily records fetched: {len(all_data)}")
    logger.info(f"=" * 60)

    # Push to XCom for next task
    context['ti'].xcom_push(key='daily_historical_data', value=all_data)

    return len(all_data)


def validate_daily_data(**context):
    """
    Validate fetched daily historical data.
    """
    logger = logging.getLogger(__name__)
    data = context['ti'].xcom_pull(key='daily_historical_data', task_ids='fetch_daily_historical_data')

    if not data:
        raise ValueError("No daily historical data to validate")

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
    logger.info("Daily Historical Data Validation Results:")
    logger.info("-" * 60)
    for check, value in checks.items():
        logger.info(f"  {check}: {value}")
    logger.info("=" * 60)

    # Quality checks
    if checks['symbols_found'] < 5:
        raise ValueError(f"Only {checks['symbols_found']} symbols found, expected {len(CRYPTO_SYMBOLS)}")

    if checks['total_records'] < 1000:
        logger.warning(f"Low record count: {checks['total_records']}")

    return checks


def load_daily_to_bronze(**context):
    """
    Load validated daily historical data into Bronze layer.
    """
    logger = logging.getLogger(__name__)
    data = context['ti'].xcom_pull(key='daily_historical_data', task_ids='fetch_daily_historical_data')

    if not data:
        raise ValueError("No daily data to load")

    pg_hook = PostgresHook(postgres_conn_id='postgres_default')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()

    # Batch size for inserts
    BATCH_SIZE = 1000
    total_inserted = 0
    total_duplicates = 0

    logger.info(f"Loading {len(data)} daily records to Bronze in batches of {BATCH_SIZE}")

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
    logger.info("Daily Historical Backfill Complete!")
    logger.info(f"  Total inserted: {total_inserted}")
    logger.info(f"  Duplicates skipped: {total_duplicates}")
    logger.info(f"  Total processed: {len(data)}")
    logger.info("=" * 60)

    return {
        'inserted': total_inserted,
        'duplicates': total_duplicates,
        'total': len(data)
    }


def verify_daily_data(**context):
    """
    Verify Bronze layer has daily historical data.
    """
    logger = logging.getLogger(__name__)
    pg_hook = PostgresHook(postgres_conn_id='postgres_default')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()

    # Check daily data coverage
    cursor.execute("""
        SELECT
            symbol,
            COUNT(*) as record_count,
            MIN(timestamp) as earliest_date,
            MAX(timestamp) as latest_date
        FROM bronze.raw_crypto_prices
        WHERE source = 'yahoo_finance_daily'
        GROUP BY symbol
        ORDER BY symbol
    """)

    results = cursor.fetchall()

    logger.info("=" * 80)
    logger.info("Bronze Layer Daily Data Coverage:")
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
    task_id='fetch_daily_historical_data',
    python_callable=fetch_daily_historical_data,
    dag=dag
)

validate_task = PythonOperator(
    task_id='validate_daily_data',
    python_callable=validate_daily_data,
    dag=dag
)

load_task = PythonOperator(
    task_id='load_daily_to_bronze',
    python_callable=load_daily_to_bronze,
    dag=dag
)

verify_task = PythonOperator(
    task_id='verify_daily_data',
    python_callable=verify_daily_data,
    dag=dag
)

# Task flow
fetch_task >> validate_task >> load_task >> verify_task
