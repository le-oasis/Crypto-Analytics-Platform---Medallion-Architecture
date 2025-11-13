# Crypto Analytics Platform - Medallion Architecture

A production-grade cryptocurrency analytics platform implementing the Medallion Architecture (Bronze, Silver, Gold) with automated data pipelines and quality validation.

## Project Overview

This platform provides real-time cryptocurrency data ingestion, transformation, and analysis using industry-standard data engineering patterns. The architecture follows the medallion pattern with three distinct layers:

- **Bronze Layer**: Raw data ingestion from Yahoo Finance API
- **Silver Layer**: Cleaned and validated data with calculated metrics
- **Gold Layer**: Business-ready aggregations and analytics (planned)

## Architecture

The platform uses a modern data stack:

- **Orchestration**: Apache Airflow with LocalExecutor
- **Database**: PostgreSQL with schema separation (bronze, silver, gold)
- **Transformation**: dbt (data build tool) for SQL transformations
- **Deployment**: Docker Compose for containerized services
- **Data Quality**: Automated dbt tests and validation

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.10+ (for local development)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd crypto-analytics-platform

# Build and start services
docker-compose build
docker-compose up -d

# Wait for initialization (approximately 30 seconds)
sleep 30
```

### Access Services

- Airflow UI: http://localhost:8080
  - Username: `admin`
  - Password: `admin`

- PostgreSQL: `localhost:5432`
  - Database: `airflow`
  - Username: `airflow`
  - Password: `airflow`

### Running the Pipeline

1. Access Airflow UI at http://localhost:8080
2. Locate the `bronze_yahoo_ingestion_dag`
3. Enable the DAG (toggle to ON)
4. Trigger the DAG manually or wait for scheduled execution

The DAG runs every 15 minutes and ingests data for 10 cryptocurrency symbols.

### Data Transformation

Run dbt transformations to process Bronze data into Silver layer:

```bash
# Test dbt connection
docker-compose exec dbt dbt debug

# Run transformations
docker-compose exec dbt dbt run --models silver

# Run data quality tests
docker-compose exec dbt dbt test --models silver
```

### Verify Data

Check the Bronze layer:

```bash
docker-compose exec postgres psql -U airflow -d airflow -c \
  "SELECT symbol, COUNT(*) FROM bronze.raw_crypto_prices GROUP BY symbol;"
```

Check the Silver layer:

```bash
docker-compose exec postgres psql -U airflow -d airflow -c \
  "SELECT symbol, COUNT(*) FROM silver.silver_crypto_prices_cleaned GROUP BY symbol;"
```

## Project Structure

```
crypto-analytics-platform/
├── airflow/
│   └── dags/              # Airflow DAG definitions
├── dbt/
│   ├── models/            # dbt transformation models
│   │   ├── bronze/        # Source definitions
│   │   └── silver/        # Silver layer transformations
│   ├── profiles.yml       # dbt database connection
│   └── dbt_project.yml    # dbt project configuration
├── docker/                # Dockerfiles for services
├── scripts/               # Database initialization scripts
├── docker-compose.yml     # Service orchestration
└── requirements.txt       # Python dependencies
```

## Data Pipeline

### Bronze Layer (Data Ingestion)

The Bronze layer ingests raw cryptocurrency data from Yahoo Finance API every 15 minutes. Data is stored in the `bronze.raw_crypto_prices` table with the following schema:

- timestamp (TIMESTAMPTZ)
- symbol (VARCHAR)
- open, high, low, close (NUMERIC)
- volume (NUMERIC)
- source (VARCHAR)
- ingestion_timestamp (TIMESTAMPTZ)

### Silver Layer (Data Cleaning)

The Silver layer applies data quality rules and calculates derived metrics:

- Deduplication
- Null value handling
- Price return calculations (simple and logarithmic)
- Spread calculations
- Data quality flags

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

## Configuration

All configurations are automated via environment variables in `docker-compose.yml`. No manual setup is required.

Key configurations:

- Database connection: Auto-configured via `AIRFLOW_CONN_POSTGRES_DEFAULT`
- Admin user: Auto-created during initialization
- Database schemas: Auto-created from `scripts/init_db.sql`

## Development

### Adding New DAGs

Place new DAG files in `airflow/dags/` directory. Airflow will automatically detect and load them.

### Adding dbt Models

Create new SQL files in `dbt/models/` following the naming convention:
- Bronze: `bronze_*.sql`
- Silver: `silver_*.sql`
- Gold: `gold_*.sql`

### Running Tests

```bash
# Run dbt tests
docker-compose exec dbt dbt test

# Check Airflow DAG integrity
docker-compose exec airflow-webserver airflow dags list
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

The platform includes automated data quality checks:

- Not null constraints on critical columns
- Price validation (positive values)
- Return percentage range validation
- Timestamp uniqueness
- Data freshness monitoring

All tests run automatically with dbt transformations.

## Technology Stack

- **Apache Airflow 2.7.3**: Workflow orchestration
- **PostgreSQL 14**: Relational database
- **dbt 1.6.0**: Data transformation
- **Python 3.10**: Data processing
- **Docker**: Containerization

## Production Considerations

For production deployment:

1. Update default passwords in `docker-compose.yml`
2. Generate and configure a Fernet key for connection encryption
3. Configure external secret management
4. Set up monitoring and alerting
5. Configure backup and disaster recovery
6. Review and adjust resource allocations

## License

MIT License

## Contact

For questions or issues, please open an issue in the repository.
