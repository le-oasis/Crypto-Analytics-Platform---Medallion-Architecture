"""
Bronze Layer Ingestion DAG
Fetches raw cryptocurrency data from multiple sources and stores in bronze layer
Runs every 15 minutes to capture near real-time price data
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sensors.external_task import ExternalTaskSensor
import yfinance as yf
import requests
import pandas as pd
import json

# Default arguments
default_args = {
    'owner': 'crypto-analytics',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
}

# DAG definition
dag = DAG(
    'bronze_ingestion_dag',
    default_args=default_args,
    description='Ingest raw crypto data into Bronze layer',
    schedule_interval='*/15 * * * *',  # Every 15 minutes
    catchup=False,
    max_active_runs=1,
    tags=['bronze', 'ingestion', 'crypto']
)

# Coins to track
CRYPTO_SYMBOLS = [
    'BTC-USD', 'ETH-USD', 'XRP-USD', 'ADA-USD', 
    'DOGE-USD', 'BNB-USD', 'DOT-USD', 'LTC-USD',
    'LINK-USD', 'MATIC-USD'
]

def fetch_yahoo_finance_data(**context):
    """
    Fetch cryptocurrency data from Yahoo Finance API
    """
    execution_date = context['execution_date']
    
    all_data = []
    
    for symbol in CRYPTO_SYMBOLS:
        try:
            # Fetch historical data using your preferred method
            ticker = yf.Ticker(symbol)
            df = ticker.history(period='1d', interval='15m')
            
            if not df.empty:
                # Flatten multi-index columns if present
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                
                df['symbol'] = symbol
                df['source'] = 'yahoo_finance'
                df['ingestion_timestamp'] = datetime.now()
                df['execution_date'] = execution_date
                df.reset_index(inplace=True)
                
                # Rename columns to match our schema
                df.rename(columns={
                    'Date': 'timestamp',
                    'Datetime': 'timestamp'
                }, inplace=True)
                
                all_data.append(df)
                print(f"✓ Fetched {len(df)} records for {symbol}")
        except Exception as e:
            print(f"✗ Error fetching {symbol}: {str(e)}")
    
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Push to XCom for next task
        context['task_instance'].xcom_push(
            key='yahoo_finance_data',
            value=combined_df.to_json(orient='records', date_format='iso')
        )
        
        print(f"✓ Total records fetched: {len(combined_df)}")
        return len(combined_df)
    else:
        raise ValueError("No data fetched from Yahoo Finance")


def fetch_coingecko_data(**context):
    """
    Fetch additional market data from CoinGecko API
    """
    execution_date = context['execution_date']
    
    # CoinGecko coin IDs
    coin_ids = {
        'BTC-USD': 'bitcoin',
        'ETH-USD': 'ethereum',
        'XRP-USD': 'ripple',
        'ADA-USD': 'cardano',
        'DOGE-USD': 'dogecoin',
        'BNB-USD': 'binancecoin',
        'DOT-USD': 'polkadot',
        'LTC-USD': 'litecoin',
        'LINK-USD': 'chainlink',
        'MATIC-USD': 'matic-network'
    }
    
    all_data = []
    
    for symbol, coin_id in coin_ids.items():
        try:
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            params = {
                'localization': 'false',
                'tickers': 'false',
                'community_data': 'false',
                'developer_data': 'false'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            market_data = {
                'symbol': symbol,
                'coin_id': coin_id,
                'market_cap': data['market_data']['market_cap'].get('usd'),
                'total_volume': data['market_data']['total_volume'].get('usd'),
                'circulating_supply': data['market_data'].get('circulating_supply'),
                'total_supply': data['market_data'].get('total_supply'),
                'ath': data['market_data']['ath'].get('usd'),
                'atl': data['market_data']['atl'].get('usd'),
                'price_change_24h': data['market_data'].get('price_change_24h'),
                'price_change_percentage_24h': data['market_data'].get('price_change_percentage_24h'),
                'timestamp': datetime.now().isoformat(),
                'source': 'coingecko',
                'execution_date': execution_date.isoformat()
            }
            
            all_data.append(market_data)
            print(f"✓ Fetched market data for {symbol}")
            
        except Exception as e:
            print(f"✗ Error fetching {symbol} from CoinGecko: {str(e)}")
    
    if all_data:
        context['task_instance'].xcom_push(
            key='coingecko_data',
            value=json.dumps(all_data)
        )
        print(f"✓ Total market data records: {len(all_data)}")
        return len(all_data)
    else:
        print("⚠ No data fetched from CoinGecko")
        return 0


def validate_data_quality(**context):
    """
    Validate data quality before inserting into bronze layer
    """
    ti = context['task_instance']
    
    # Get data from previous tasks
    yahoo_data_json = ti.xcom_pull(task_ids='fetch_yahoo_finance', key='yahoo_finance_data')
    coingecko_data_json = ti.xcom_pull(task_ids='fetch_coingecko', key='coingecko_data')
    
    issues = []
    
    # Validate Yahoo Finance data
    if yahoo_data_json:
        yahoo_df = pd.read_json(yahoo_data_json)
        
        # Check for nulls in critical columns
        critical_cols = ['timestamp', 'symbol', 'Close', 'Volume']
        for col in critical_cols:
            null_count = yahoo_df[col].isnull().sum()
            if null_count > 0:
                issues.append(f"⚠ {null_count} null values in {col}")
        
        # Check for negative prices
        if (yahoo_df['Close'] < 0).any():
            issues.append("⚠ Negative prices detected")
        
        # Check for outliers (prices that differ by >50% from previous)
        for symbol in yahoo_df['symbol'].unique():
            symbol_df = yahoo_df[yahoo_df['symbol'] == symbol].sort_values('timestamp')
            price_change_pct = symbol_df['Close'].pct_change().abs()
            if (price_change_pct > 0.5).any():
                issues.append(f"⚠ Extreme price change detected for {symbol}")
        
        print(f"✓ Yahoo Finance validation: {len(yahoo_df)} records")
    
    # Validate CoinGecko data
    if coingecko_data_json:
        coingecko_data = json.loads(coingecko_data_json)
        print(f"✓ CoinGecko validation: {len(coingecko_data)} records")
    
    if issues:
        print("Data quality issues detected:")
        for issue in issues:
            print(f"  {issue}")
        # Continue anyway - just log warnings
    else:
        print("✓ All data quality checks passed")
    
    return len(issues)


def write_to_bronze_layer(**context):
    """
    Write validated data to PostgreSQL bronze layer
    """
    ti = context['task_instance']
    pg_hook = PostgresHook(postgres_conn_id='postgres_default')
    
    # Get data from XCom
    yahoo_data_json = ti.xcom_pull(task_ids='fetch_yahoo_finance', key='yahoo_finance_data')
    coingecko_data_json = ti.xcom_pull(task_ids='fetch_coingecko', key='coingecko_data')
    
    records_inserted = 0
    
    # Insert Yahoo Finance data
    if yahoo_data_json:
        yahoo_df = pd.read_json(yahoo_data_json)
        
        # Prepare data for insertion
        yahoo_df['timestamp'] = pd.to_datetime(yahoo_df['timestamp'])
        
        insert_query = """
        INSERT INTO bronze.raw_crypto_prices 
        (timestamp, symbol, open, high, low, close, volume, source, ingestion_timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (timestamp, symbol, source) DO NOTHING
        """
        
        for _, row in yahoo_df.iterrows():
            pg_hook.run(
                insert_query,
                parameters=(
                    row['timestamp'],
                    row['symbol'],
                    row.get('Open'),
                    row.get('High'),
                    row.get('Low'),
                    row['Close'],
                    row.get('Volume'),
                    row['source'],
                    row['ingestion_timestamp']
                )
            )
            records_inserted += 1
        
        print(f"✓ Inserted {records_inserted} price records into bronze.raw_crypto_prices")
    
    # Insert CoinGecko data
    if coingecko_data_json:
        coingecko_data = json.loads(coingecko_data_json)
        
        insert_query = """
        INSERT INTO bronze.raw_market_data 
        (timestamp, symbol, coin_id, market_cap, total_volume, circulating_supply, 
         total_supply, ath, atl, price_change_24h, price_change_percentage_24h, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (timestamp, symbol) DO NOTHING
        """
        
        for record in coingecko_data:
            pg_hook.run(
                insert_query,
                parameters=(
                    record['timestamp'],
                    record['symbol'],
                    record['coin_id'],
                    record.get('market_cap'),
                    record.get('total_volume'),
                    record.get('circulating_supply'),
                    record.get('total_supply'),
                    record.get('ath'),
                    record.get('atl'),
                    record.get('price_change_24h'),
                    record.get('price_change_percentage_24h'),
                    record['source']
                )
            )
            records_inserted += 1
        
        print(f"✓ Inserted {len(coingecko_data)} market records into bronze.raw_market_data")
    
    return records_inserted


def check_data_freshness(**context):
    """
    Ensure we have fresh data in bronze layer
    """
    pg_hook = PostgresHook(postgres_conn_id='postgres_default')
    
    # Check latest timestamp
    query = """
    SELECT 
        MAX(timestamp) as latest_timestamp,
        COUNT(*) as record_count,
        COUNT(DISTINCT symbol) as symbol_count
    FROM bronze.raw_crypto_prices
    WHERE timestamp > NOW() - INTERVAL '1 hour'
    """
    
    result = pg_hook.get_first(query)
    
    if result:
        latest_timestamp, record_count, symbol_count = result
        print(f"✓ Latest data timestamp: {latest_timestamp}")
        print(f"✓ Records in last hour: {record_count}")
        print(f"✓ Unique symbols: {symbol_count}")
        
        # Alert if data is too old
        if latest_timestamp:
            age_minutes = (datetime.now() - latest_timestamp).total_seconds() / 60
            if age_minutes > 30:
                print(f"⚠ WARNING: Data is {age_minutes:.1f} minutes old")
        
        return True
    else:
        raise ValueError("No data found in bronze layer")


# Task definitions
task_fetch_yahoo = PythonOperator(
    task_id='fetch_yahoo_finance',
    python_callable=fetch_yahoo_finance_data,
    dag=dag,
)

task_fetch_coingecko = PythonOperator(
    task_id='fetch_coingecko',
    python_callable=fetch_coingecko_data,
    dag=dag,
)

task_validate = PythonOperator(
    task_id='validate_data_quality',
    python_callable=validate_data_quality,
    dag=dag,
)

task_write_bronze = PythonOperator(
    task_id='write_to_bronze_layer',
    python_callable=write_to_bronze_layer,
    dag=dag,
)

task_check_freshness = PythonOperator(
    task_id='check_data_freshness',
    python_callable=check_data_freshness,
    dag=dag,
)

# Create bronze tables if they don't exist
task_create_tables = PostgresOperator(
    task_id='create_bronze_tables',
    postgres_conn_id='postgres_default',
    sql="""
    CREATE SCHEMA IF NOT EXISTS bronze;
    
    CREATE TABLE IF NOT EXISTS bronze.raw_crypto_prices (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP NOT NULL,
        symbol VARCHAR(20) NOT NULL,
        open NUMERIC(20, 8),
        high NUMERIC(20, 8),
        low NUMERIC(20, 8),
        close NUMERIC(20, 8),
        volume NUMERIC(20, 2),
        source VARCHAR(50),
        ingestion_timestamp TIMESTAMP DEFAULT NOW(),
        UNIQUE(timestamp, symbol, source)
    );
    
    CREATE TABLE IF NOT EXISTS bronze.raw_market_data (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP NOT NULL,
        symbol VARCHAR(20) NOT NULL,
        coin_id VARCHAR(50),
        market_cap NUMERIC(20, 2),
        total_volume NUMERIC(20, 2),
        circulating_supply NUMERIC(20, 2),
        total_supply NUMERIC(20, 2),
        ath NUMERIC(20, 8),
        atl NUMERIC(20, 8),
        price_change_24h NUMERIC(20, 8),
        price_change_percentage_24h NUMERIC(10, 4),
        source VARCHAR(50),
        UNIQUE(timestamp, symbol)
    );
    
    CREATE INDEX IF NOT EXISTS idx_prices_timestamp ON bronze.raw_crypto_prices(timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_prices_symbol ON bronze.raw_crypto_prices(symbol);
    CREATE INDEX IF NOT EXISTS idx_market_timestamp ON bronze.raw_market_data(timestamp DESC);
    """,
    dag=dag,
)

# Task dependencies
task_create_tables >> [task_fetch_yahoo, task_fetch_coingecko]
[task_fetch_yahoo, task_fetch_coingecko] >> task_validate
task_validate >> task_write_bronze
task_write_bronze >> task_check_freshness
