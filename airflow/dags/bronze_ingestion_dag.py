"""
Bronze Layer Ingestion DAG (Yahoo Finance Only)
Fetches raw cryptocurrency data from Yahoo Finance and loads into the bronze layer.
Runs every 15 minutes to capture near real-time price data.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import yfinance as yf
import pandas as pd

# ==========================================================
# Default configuration
# ==========================================================
default_args = {
    'owner': 'crypto-analytics',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=3),
}

dag = DAG(
    'bronze_yahoo_ingestion_dag',
    default_args=default_args,
    description='Fetch and load Yahoo Finance crypto data into the Bronze layer',
    schedule_interval='*/15 * * * *',  # every 15 minutes
    catchup=False,
    max_active_runs=1,
    tags=['bronze', 'yahoo_finance', 'crypto'],
)

# ==========================================================
# Parameters
# ==========================================================
CRYPTO_SYMBOLS = [
    'BTC-USD', 'ETH-USD', 'XRP-USD', 'ADA-USD',
    'DOGE-USD', 'BNB-USD', 'DOT-USD', 'LTC-USD',
    'LINK-USD', 'MATIC-USD'
]


# ==========================================================
# Task 1: Fetch data from Yahoo Finance
# ==========================================================
def fetch_yahoo_finance_data(**context):
    execution_date = context['execution_date']
    all_data = []

    for symbol in CRYPTO_SYMBOLS:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period='1d', interval='15m')

            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)

                df['symbol'] = symbol
                df['source'] = 'yahoo_finance'
                df['ingestion_timestamp'] = datetime.utcnow()
                df.reset_index(inplace=True)

                # Normalize timestamp column
                df.rename(columns={'Datetime': 'timestamp', 'Date': 'timestamp'}, inplace=True)
                df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)

                all_data.append(df)
                print(f"✓ Fetched {len(df)} records for {symbol}")

        except Exception as e:
            print(f"✗ Error fetching {symbol}: {str(e)}")

    if not all_data:
        raise ValueError("No data fetched from Yahoo Finance")

    combined_df = pd.concat(all_data, ignore_index=True)
    print(f"✅ Total records fetched: {len(combined_df)}")

    # Push to XCom for downstream tasks
    context['task_instance'].xcom_push(
        key='yahoo_finance_data',
        value=combined_df.to_json(orient='records', date_format='iso')
    )


# ==========================================================
# Task 2: Validate data quality
# ==========================================================
def validate_data_quality(**context):
    ti = context['task_instance']
    yahoo_data_json = ti.xcom_pull(task_ids='fetch_yahoo_finance_data', key='yahoo_finance_data')

    df = pd.read_json(yahoo_data_json)

    issues = []
    critical_cols = ['timestamp', 'symbol', 'Close', 'Volume']

    for col in critical_cols:
        null_count = df[col].isnull().sum()
        if null_count > 0:
            issues.append(f"{null_count} null values in {col}")

    if (df['Close'] < 0).any():
        issues.append("Negative prices detected")

    if issues:
        print("⚠ Data quality warnings:")
        for issue in issues:
            print(" -", issue)
    else:
        print("✅ All data quality checks passed")

    return len(issues)


# ==========================================================
# Task 3: Load data into Bronze table
# ==========================================================
def load_to_bronze(**context):
    ti = context['task_instance']
    yahoo_data_json = ti.xcom_pull(task_ids='fetch_yahoo_finance_data', key='yahoo_finance_data')

    df = pd.read_json(yahoo_data_json)
    pg_hook = PostgresHook(postgres_conn_id='postgres_default')

    insert_query = """
        INSERT INTO bronze.raw_crypto_prices 
        (timestamp, symbol, open, high, low, close, volume, source, ingestion_timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (timestamp, symbol, source) DO NOTHING;
    """

    records_inserted = 0
    for _, row in df.iterrows():
        pg_hook.run(
            insert_query,
            parameters=(
                row['timestamp'],
                row['symbol'],
                row.get('Open'),
                row.get('High'),
                row.get('Low'),
                row.get('Close'),
                row.get('Volume'),
                row['source'],
                row['ingestion_timestamp']
            )
        )
        records_inserted += 1

    print(f"✅ Inserted {records_inserted} records into bronze.raw_crypto_prices")
    return records_inserted


# ==========================================================
# Task 4: Check recent freshness
# ==========================================================
def check_data_freshness(**context):
    pg_hook = PostgresHook(postgres_conn_id='postgres_default')
    query = """
        SELECT 
            MAX(timestamp) as latest_timestamp,
            COUNT(*) as record_count,
            COUNT(DISTINCT symbol) as symbol_count
        FROM bronze.raw_crypto_prices
        WHERE timestamp > NOW() - INTERVAL '1 hour';
    """

    result = pg_hook.get_first(query)
    if result:
        latest_timestamp, record_count, symbol_count = result
        print(f"✓ Latest timestamp: {latest_timestamp}")
        print(f"✓ Rows (1h): {record_count}, Unique symbols: {symbol_count}")

        if latest_timestamp:
            age_min = (datetime.utcnow() - latest_timestamp).total_seconds() / 60
            if age_min > 30:
                print(f"⚠ Data is stale ({age_min:.1f} minutes old)")
        return True
    else:
        raise ValueError("No records found in bronze.raw_crypto_prices")


# ==========================================================
# Task definitions
# ==========================================================
task_fetch = PythonOperator(
    task_id='fetch_yahoo_finance_data',
    python_callable=fetch_yahoo_finance_data,
    dag=dag,
)

task_validate = PythonOperator(
    task_id='validate_data_quality',
    python_callable=validate_data_quality,
    dag=dag,
)

task_load = PythonOperator(
    task_id='load_to_bronze',
    python_callable=load_to_bronze,
    dag=dag,
)

task_freshness = PythonOperator(
    task_id='check_data_freshness',
    python_callable=check_data_freshness,
    dag=dag,
)

# ==========================================================
# Task dependencies
# ==========================================================
task_fetch >> task_validate >> task_load >> task_freshness
