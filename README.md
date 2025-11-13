# Crypto Analytics Platform - Medallion Architecture

A production-grade cryptocurrency analytics platform implementing the Medallion Architecture (Bronze, Silver, Gold) with automated data pipelines, quality validation, and interactive visualizations.

## Project Overview

This platform provides comprehensive cryptocurrency data ingestion, transformation, and analysis using industry-standard data engineering patterns. The architecture follows the medallion pattern with three distinct layers:

- **Bronze Layer**: Raw data ingestion from Yahoo Finance API (real-time + historical)
- **Silver Layer**: Cleaned and validated data with calculated metrics
- **Gold Layer**: Business-ready daily aggregations with performance analytics
- **Visualization Layer**: Interactive Streamlit dashboard with candlestick charts

## Architecture

The platform uses a modern data stack:

- **Orchestration**: Apache Airflow with LocalExecutor
- **Database**: PostgreSQL with schema separation (bronze, silver, silver_gold)
- **Transformation**: dbt (data build tool) for SQL transformations
- **Visualization**: Streamlit with Plotly for interactive dashboards
- **Deployment**: Docker Compose for containerized services
- **Data Quality**: Automated dbt tests and validation

## Quick Start

### Prerequisites

- Docker and Docker Compose
- At least 4GB RAM available for Docker
- 10GB free disk space

### Step 1: Installation

```bash
# Clone the repository
git clone <repository-url>
cd Crypto-Analytics-Platform---Medallion-Architecture

# Build and start all services
docker-compose build
docker-compose up -d

# Wait for initialization (approximately 60 seconds)
sleep 60
```

### Step 2: Access Services

Once services are running, you can access:

- **Airflow UI**: http://localhost:8080
  - Username: `admin`
  - Password: `admin`

- **Streamlit Dashboard**: http://localhost:8501
  - No authentication required

- **PostgreSQL**: `localhost:5432`
  - Database: `airflow`
  - Username: `airflow`
  - Password: `airflow`

### Step 3: Load Historical Data

Before viewing the dashboard, load historical cryptocurrency data from 2018-present:

#### 3a. Run Daily Historical Backfill (~15 minutes)

```bash
docker exec crypto-airflow-scheduler airflow dags trigger bronze_backfill_daily_historical
```

**Validate daily backfill:**

```bash
docker-compose exec postgres psql -U airflow -d airflow -c \
  "SELECT symbol, COUNT(*) as daily_records, MIN(timestamp) as earliest, MAX(timestamp) as latest
   FROM bronze.raw_crypto_prices
   WHERE source = 'yahoo_daily'
   GROUP BY symbol
   ORDER BY symbol;"
```

Expected output: ~1,800+ records per symbol (daily data from 2018-2025)

#### 3b. Run Hourly Historical Backfill (~20 minutes)

```bash
docker exec crypto-airflow-scheduler airflow dags trigger bronze_backfill_hourly_historical
```

**Validate hourly backfill:**

```bash
docker-compose exec postgres psql -U airflow -d airflow -c \
  "SELECT symbol, COUNT(*) as hourly_records, MIN(timestamp) as earliest, MAX(timestamp) as latest
   FROM bronze.raw_crypto_prices
   WHERE source = 'yahoo_hourly'
   GROUP BY symbol
   ORDER BY symbol;"
```

Expected output: ~15,000+ records per symbol (hourly data from 2018-2025)

#### 3c. Verify Total Bronze Data

```bash
docker-compose exec postgres psql -U airflow -d airflow -c \
  "SELECT source, COUNT(*) as total_records
   FROM bronze.raw_crypto_prices
   GROUP BY source;"
```

Expected output:
- `yahoo_daily`: ~18,000-19,000 total records
- `yahoo_hourly`: ~150,000-160,000 total records

### Step 4: Transform to Silver Layer

Process Bronze data into cleaned, validated Silver layer:

```bash
# Run Silver layer transformations
docker-compose exec dbt dbt run --models silver

# Run data quality tests (13 tests)
docker-compose exec dbt dbt test --models silver
```

**Validate Silver layer:**

```bash
docker-compose exec postgres psql -U airflow -d airflow -c \
  "SELECT symbol, COUNT(*) as records
   FROM silver.silver_crypto_prices_cleaned
   GROUP BY symbol
   ORDER BY symbol;"
```

Expected output: ~175,000+ total records across all symbols

### Step 5: Transform to Gold Layer

Create business-ready daily aggregations:

```bash
# Run Gold layer transformations
docker-compose exec dbt dbt run --models gold

# Run data quality tests (11 tests)
docker-compose exec dbt dbt test --models gold
```

**Validate Gold layer:**

```bash
docker-compose exec postgres psql -U airflow -d airflow -c \
  "SELECT symbol, COUNT(*) as daily_records,
          MIN(date) as earliest_date,
          MAX(date) as latest_date
   FROM silver_gold.gold_daily_prices
   GROUP BY symbol
   ORDER BY symbol;"
```

Expected output: ~2,400+ daily records per symbol

**View sample Gold data:**

```bash
docker-compose exec postgres psql -U airflow -d airflow -c \
  "SELECT date, symbol, open, high, low, close, volume, daily_return_pct
   FROM silver_gold.gold_daily_prices
   ORDER BY date DESC, symbol
   LIMIT 20;"
```

### Step 6: Access the Dashboard

Open your browser and navigate to **http://localhost:8501**

The Streamlit dashboard provides:

- **Current Prices**: Real-time price cards with daily returns
- **Single Asset Analysis**: Candlestick charts with volume, multiple timeframes (7D, 1M, 3M, 6M, 1Y, 2Y, ALL)
- **Compare Assets**: Multi-asset performance comparison with normalized returns
- **Interactive Features**: Zoom, pan, hover details on all charts

### Optional: Enable Live Data Updates

To enable hourly real-time data ingestion:

1. Access Airflow UI at http://localhost:8080
2. Locate the `bronze_yahoo_ingestion_dag`
3. Toggle the DAG to **ON**

The DAG will run every hour to fetch the latest cryptocurrency prices.

## Project Structure

```
Crypto-Analytics-Platform---Medallion-Architecture/
├── airflow/
│   ├── dags/                              # Airflow DAG definitions
│   │   ├── bronze_yahoo_ingestion_dag.py  # Hourly real-time ingestion
│   │   ├── bronze_backfill_daily.py       # Daily historical backfill
│   │   └── bronze_backfill_hourly.py      # Hourly historical backfill
│   ├── logs/                              # Airflow execution logs
│   └── plugins/                           # Custom Airflow plugins
├── dbt/
│   ├── models/
│   │   ├── bronze/                        # Source definitions
│   │   ├── silver/                        # Silver layer transformations
│   │   │   ├── silver_crypto_prices_cleaned.sql
│   │   │   └── schema.yml                 # Tests and documentation
│   │   └── gold/                          # Gold layer aggregations
│   │       ├── gold_daily_prices.sql      # Daily OHLCV aggregations
│   │       └── schema.yml                 # Tests and documentation
│   ├── profiles.yml                       # dbt database connection
│   └── dbt_project.yml                    # dbt project configuration
├── streamlit/
│   ├── app.py                             # Streamlit dashboard application
│   └── requirements.txt                   # Python visualization dependencies
├── docker/
│   ├── airflow.Dockerfile                 # Airflow container definition
│   ├── dbt.Dockerfile                     # dbt container definition
│   └── streamlit.Dockerfile               # Streamlit container definition
├── scripts/
│   └── init_db.sql                        # PostgreSQL schema initialization
├── docker-compose.yml                     # Multi-service orchestration
└── README.md                              # This file
```

## Data Pipeline

### Bronze Layer (Data Ingestion)

The Bronze layer ingests raw cryptocurrency data from Yahoo Finance API. Data is stored in the `bronze.raw_crypto_prices` table with the following schema:

**Schema:**
- `timestamp` (TIMESTAMPTZ) - Trading timestamp
- `symbol` (VARCHAR) - Cryptocurrency symbol (e.g., BTC-USD)
- `open`, `high`, `low`, `close` (NUMERIC) - OHLC price data
- `volume` (NUMERIC) - Trading volume
- `source` (VARCHAR) - Data source identifier (yahoo_daily, yahoo_hourly, yahoo_live)
- `ingestion_timestamp` (TIMESTAMPTZ) - When data was ingested

**Data Sources:**
- **Historical Daily**: 2018-2025 daily OHLCV data (~18,000 records)
- **Historical Hourly**: 2018-2025 hourly OHLCV data (~157,000 records)
- **Live Hourly**: Optional real-time updates every hour

**Total Bronze Records**: ~175,000 rows across 10 cryptocurrency symbols

### Silver Layer (Data Cleaning)

The Silver layer (`silver.silver_crypto_prices_cleaned`) applies data quality rules and calculates derived metrics:

**Transformations:**
- Deduplication (removes duplicate timestamp + symbol combinations)
- Null value handling with data quality flags
- Price return calculations (simple and logarithmic)
- Price spread calculations
- Return percentage validations

**Calculated Metrics:**
- `price_return_pct`: Percentage change from previous record
- `log_return`: Logarithmic return for statistical analysis
- `spread`: Difference between high and low prices
- `spread_pct`: Spread as percentage of low price

**Data Quality:** 13 automated tests ensuring data integrity

**Total Silver Records**: ~175,000 cleaned records

### Gold Layer (Business Analytics)

The Gold layer (`silver_gold.gold_daily_prices`) provides business-ready daily aggregations optimized for analysis and visualization.

**Aggregation Logic:**
- Aggregates hourly/daily data into single daily OHLCV records
- Uses window functions to properly select first open and last close of each day
- Calculates comprehensive performance metrics

**Daily Metrics:**
- `open`: First price of the trading day
- `high`: Maximum price during the day
- `low`: Minimum price during the day
- `close`: Last price of the trading day
- `volume`: Total trading volume for the day
- `price_change_pct`: Intraday price change (open to close)
- `daily_return_pct`: Return vs previous day's close
- `log_return`: Logarithmic return for statistical modeling
- `daily_spread`: High - Low price range
- `spread_pct`: Volatility indicator

**Data Quality:** 11 automated tests including:
- Not null constraints on critical columns
- Price validation (positive values)
- Return percentage range validation (-100% to 1000%)
- Volume validation (non-negative)

**Total Gold Records**: ~24,800 daily aggregated records (one per symbol per day)

### Tracked Cryptocurrencies

- BTC-USD (Bitcoin)
- ETH-USD (Ethereum)
- XRP-USD (Ripple)
- ADA-USD (Cardano)
- DOGE-USD (Dogecoin)
- BNB-USD (Binance Coin)
- DOT-USD (Polkadot)
- LTC-USD (Litecoin)
- LINK-USD (Chainlink)
- MATIC-USD (Polygon)

## Dashboard Features

The Streamlit dashboard (http://localhost:8501) provides professional-grade cryptocurrency analytics with interactive visualizations.

### Current Prices Panel

Real-time price cards displaying:
- Current price for each cryptocurrency
- Daily return percentage with color-coded indicators
- Summary table with OHLC data and volume

### Single Asset Analysis Tab

**Candlestick Charts:**
- Professional OHLC candlestick visualization
- Green candles for positive days, red for negative days
- Volume bars synchronized with price movements
- Interactive features: zoom, pan, hover for details

**Timeframe Selection:**
- 7D (7 days)
- 1M (1 month / 30 days)
- 3M (3 months / 90 days)
- 6M (6 months / 180 days)
- 1Y (1 year / 365 days)
- 2Y (2 years / 730 days)
- ALL (complete historical data)

**Performance Metrics:**
- Period High/Low prices
- Average Daily Return
- Volatility (Standard Deviation)
- Total Return for selected period

### Compare Assets Tab

**Multi-Asset Comparison:**
- Select multiple cryptocurrencies to compare
- Normalized performance chart showing % change from start date
- Direct comparison of relative performance

**Performance Summary Table:**
- Start and end prices for each asset
- Total return percentage
- Average daily return
- Volatility metrics

**Interactive Controls:**
- Adjustable comparison timeframe (7-365 days)
- Multi-select dropdown for asset selection
- Real-time chart updates

### Dashboard Controls

- **Auto-refresh**: Optional 60-second automatic data refresh
- **Manual Refresh**: Button to clear cache and reload data
- **Last Updated**: Timestamp showing when data was last refreshed
- **Responsive Design**: Optimized for various screen sizes

## Configuration

All configurations are automated via environment variables in `docker-compose.yml`. No manual setup is required.

### Key Configurations

**Database Connection:**
- Auto-configured via `AIRFLOW_CONN_POSTGRES_DEFAULT`
- Connection string: `postgresql://airflow:airflow@postgres:5432/airflow`
- Schema separation: `bronze`, `silver`, `silver_gold`

**Airflow:**
- Admin user: Auto-created during initialization (`admin` / `admin`)
- Executor: LocalExecutor for single-node deployment
- DAGs folder: `./airflow/dags` (auto-scanned)

**dbt:**
- Profile: Auto-configured in `dbt/profiles.yml`
- Target: `dev` (default)
- Models directory: `dbt/models/`

**Streamlit:**
- Port: 8501
- Database connection: Direct PostgreSQL connection to `postgres:5432`
- Cache TTL: 60 seconds for latest prices, 300 seconds for historical data

**Services:**
- PostgreSQL: Port 5432
- Airflow Webserver: Port 8080
- Streamlit Dashboard: Port 8501

## Development

### Adding New DAGs

Place new DAG files in `airflow/dags/` directory. Airflow will automatically detect and load them.

**Example DAG structure:**
```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

with DAG(
    'my_custom_dag',
    start_date=datetime(2025, 1, 1),
    schedule_interval='@hourly',
    catchup=False
) as dag:
    # Your tasks here
    pass
```

### Adding dbt Models

Create new SQL files in `dbt/models/` following the naming convention:

**Naming Convention:**
- Bronze: `bronze_*.sql` (source definitions)
- Silver: `silver_*.sql` (cleaned data)
- Gold: `gold_*.sql` (business aggregations)

**Example Gold Model:**
```sql
{{ config(
    materialized='table',
    tags=['gold', 'my_model']
) }}

SELECT
    date,
    symbol,
    -- Your aggregations here
FROM {{ ref('silver_crypto_prices_cleaned') }}
GROUP BY date, symbol
```

**Add tests in `schema.yml`:**
```yaml
models:
  - name: gold_my_model
    description: "Description of your model"
    columns:
      - name: date
        tests:
          - not_null
          - unique
```

**Run your new model:**
```bash
# Run specific model
docker-compose exec dbt dbt run --models gold_my_model

# Run with tests
docker-compose exec dbt dbt run --models gold_my_model
docker-compose exec dbt dbt test --models gold_my_model
```

### Modifying the Dashboard

The Streamlit dashboard is in `streamlit/app.py`. To make changes:

1. Edit `streamlit/app.py`
2. Restart the Streamlit container:
```bash
docker-compose restart streamlit
```

**Hot reload (for development):**
```bash
# Run Streamlit with hot reload
docker-compose exec streamlit streamlit run /app/app.py --server.runOnSave=true
```

### Running Tests

```bash
# Run all dbt tests
docker-compose exec dbt dbt test

# Run tests for specific layer
docker-compose exec dbt dbt test --models silver
docker-compose exec dbt dbt test --models gold

# Check Airflow DAG integrity
docker-compose exec airflow-webserver airflow dags list

# Test database connection
docker-compose exec postgres psql -U airflow -d airflow -c "SELECT version();"
```

## Maintenance

### Stopping Services

```bash
docker-compose down
```

### Complete Reset

```bash
docker-compose down -v
docker-compose up -d
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f airflow-scheduler
```

## Data Quality

The platform includes comprehensive automated data quality checks across all layers:

**Silver Layer Tests (13 tests):**
- Not null constraints on critical columns
- Price validation (positive values)
- Return percentage range validation (-100% to 1000%)
- Timestamp uniqueness per symbol
- Volume validation (non-negative)

**Gold Layer Tests (11 tests):**
- Not null constraints on OHLCV data
- Price range validation
- Daily return validation
- Volume non-negative validation
- Data completeness checks

All tests run automatically with dbt transformations and must pass before data propagates to downstream layers.

## Technology Stack

### Core Technologies

- **Apache Airflow 2.7.3**: Workflow orchestration and DAG management
- **PostgreSQL 14**: Relational database with multi-schema architecture
- **dbt 1.6.0**: Data transformation and testing framework
- **Python 3.10**: Data processing and API integration
- **Docker & Docker Compose**: Containerization and service orchestration

### Visualization & Analytics

- **Streamlit 1.28.0**: Interactive web dashboard framework
- **Plotly 5.17.0**: Advanced charting library for candlestick charts
- **Pandas 2.1.0**: Data manipulation and analysis
- **NumPy 1.25.2**: Numerical computing

### Data Sources

- **Yahoo Finance API**: Real-time and historical cryptocurrency data via `yfinance` library

### Database Architecture

- **Schema Separation**:
  - `bronze`: Raw ingested data
  - `silver`: Cleaned and validated data
  - `silver_gold`: Business-ready aggregations

### Deployment

- **LocalExecutor**: Single-node Airflow deployment
- **Docker Compose**: Multi-container orchestration
- **Volume Mounts**: Persistent data storage and hot-reload development

## Troubleshooting

### Dashboard Shows "No Data Available"

**Solution:** Ensure you've run the complete data pipeline:
```bash
# 1. Check Bronze data exists
docker-compose exec postgres psql -U airflow -d airflow -c \
  "SELECT COUNT(*) FROM bronze.raw_crypto_prices;"

# 2. Run Silver transformation if needed
docker-compose exec dbt dbt run --models silver

# 3. Run Gold transformation if needed
docker-compose exec dbt dbt run --models gold

# 4. Restart Streamlit
docker-compose restart streamlit
```

### Airflow DAG Not Running

**Check DAG status:**
```bash
docker-compose exec airflow-scheduler airflow dags list
```

**View DAG logs:**
```bash
docker-compose logs -f airflow-scheduler
```

**Manually trigger DAG:**
```bash
docker exec crypto-airflow-scheduler airflow dags trigger <dag_id>
```

### dbt Connection Issues

**Test connection:**
```bash
docker-compose exec dbt dbt debug
```

**Check PostgreSQL is running:**
```bash
docker-compose ps postgres
```

### Streamlit Not Loading

**Check container status:**
```bash
docker-compose ps streamlit
```

**View Streamlit logs:**
```bash
docker-compose logs -f streamlit
```

**Restart Streamlit:**
```bash
docker-compose restart streamlit
```

### Database Connection Refused

**Ensure PostgreSQL is healthy:**
```bash
docker-compose exec postgres pg_isready -U airflow
```

**Check database connection from Airflow:**
```bash
docker-compose exec airflow-webserver airflow connections get postgres_default
```

### Clear Cache and Reset

**Clear dbt cache:**
```bash
docker-compose exec dbt dbt clean
```

**Clear Streamlit cache:**
Access the dashboard and click the "🔄 Refresh Data" button in the sidebar.

**Complete reset (WARNING: Deletes all data):**
```bash
docker-compose down -v
docker-compose build
docker-compose up -d
# Re-run historical backfills and transformations
```

## Production Considerations

For production deployment, consider the following enhancements:

### Security

1. **Update default passwords** in `docker-compose.yml`:
   - PostgreSQL password
   - Airflow admin password

2. **Generate Fernet key** for Airflow connection encryption:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

3. **Configure external secret management** (AWS Secrets Manager, HashiCorp Vault)

4. **Enable SSL/TLS** for database and web connections

### Scalability

1. **Switch to CeleryExecutor** for distributed task execution
2. **Add Redis/RabbitMQ** as message broker
3. **Configure external metadata database** (separate from data warehouse)
4. **Implement connection pooling** (PgBouncer)

### Monitoring & Alerting

1. **Set up monitoring**:
   - Airflow task failure alerts
   - Database performance metrics
   - Dashboard availability monitoring

2. **Configure alerting**:
   - Email/Slack notifications for DAG failures
   - Data quality test failures
   - System resource alerts

### Backup & Recovery

1. **Database backups**:
   - Automated PostgreSQL backups
   - Point-in-time recovery configuration

2. **Data retention policies**:
   - Archive old Bronze layer data
   - Maintain Gold layer for analysis

### Resource Allocation

1. **Review resource limits** in `docker-compose.yml`
2. **Configure Airflow parallelism** settings
3. **Optimize PostgreSQL** memory and connection settings
4. **Enable Streamlit caching** for production load

## Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA INGESTION (Bronze Layer)                │
│  Yahoo Finance API → Airflow DAGs → PostgreSQL bronze schema     │
│  • Daily Historical: 2018-2025 (~18K records)                    │
│  • Hourly Historical: 2018-2025 (~157K records)                  │
│  • Live Hourly: Optional real-time updates                       │
│  Total: ~175K raw OHLCV records                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                 DATA CLEANING (Silver Layer)                     │
│  dbt transformations → silver schema                             │
│  • Deduplication                                                 │
│  • Null handling                                                 │
│  • Return calculations                                           │
│  • 13 data quality tests                                         │
│  Total: ~175K cleaned records                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              BUSINESS AGGREGATIONS (Gold Layer)                  │
│  dbt transformations → silver_gold schema                        │
│  • Daily OHLCV aggregations                                      │
│  • Performance metrics                                           │
│  • Volatility indicators                                         │
│  • 11 data quality tests                                         │
│  Total: ~24.8K daily aggregated records                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    VISUALIZATION (Streamlit)                     │
│  Plotly charts + Streamlit UI → http://localhost:8501           │
│  • Real-time price cards                                         │
│  • Candlestick charts with volume                                │
│  • Multi-asset comparison                                        │
│  • Performance analytics                                         │
└─────────────────────────────────────────────────────────────────┘
```

## Current Platform Status

✅ **Fully Operational** - All components are production-ready

**Implemented Features:**
- ✅ Bronze Layer: Historical + live data ingestion (2018-2025)
- ✅ Silver Layer: Data cleaning and validation with 13 tests
- ✅ Gold Layer: Daily aggregations with 11 tests
- ✅ Interactive Dashboard: Candlestick charts and comparisons
- ✅ Automated Testing: 24 dbt tests across layers
- ✅ Docker Deployment: Full containerized setup

**Data Metrics:**
- 10 cryptocurrencies tracked
- ~175,000 Bronze records (2018-2025)
- ~175,000 Silver records (cleaned)
- ~24,800 Gold records (daily aggregations)
- 7+ years of historical data

**Services Running:**
- PostgreSQL database on port 5432
- Airflow webserver on port 8080
- Streamlit dashboard on port 8501

## License

MIT License

## Contact

For questions or issues, please open an issue in the repository.

## Acknowledgments

Built with modern data engineering best practices:
- Medallion Architecture pattern
- dbt for transformation and testing
- Airflow for orchestration
- Docker for reproducible deployments
