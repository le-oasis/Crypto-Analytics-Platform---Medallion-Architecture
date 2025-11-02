# 🚀 Crypto Analytics Platform - Medallion Architecture

## 📊 Project Overview

A production-grade cryptocurrency analytics platform implementing the **Medallion Architecture** (Bronze → Silver → Gold) with orchestrated data pipelines, ML-based price prediction, and interactive visualizations.

### Business Goals
1. **Real-time Crypto Monitoring**: Track Bitcoin, Ethereum, and altcoins with live price data
2. **Portfolio Optimization**: Calculate optimal portfolio weights using Sharpe Ratio maximization
3. **Price Prediction**: ML models to forecast cryptocurrency prices
4. **Risk Analysis**: Volatility tracking, correlation analysis, and technical indicators
5. **Automated Reporting**: Daily dashboards with actionable insights

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                             │
│  • Yahoo Finance API  • CoinGecko API  • Binance API            │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                           │
│                    Apache Airflow (DAGs)                         │
│  • Ingestion DAG  • Transformation DAG  • ML Training DAG       │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MEDALLION ARCHITECTURE                        │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │    BRONZE    │───▶│    SILVER    │───▶│     GOLD     │     │
│  │  Raw Data    │    │  Cleaned &   │    │  Business    │     │
│  │  Lake        │    │  Validated   │    │  Aggregates  │     │
│  └──────────────┘    └──────────────┘    └──────────────┘     │
│                                                                  │
│  Storage: PostgreSQL / DuckDB / Delta Lake                      │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TRANSFORMATION LAYER (dbt)                     │
│  • Data Quality Tests  • Feature Engineering  • Aggregations   │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ML PIPELINE                                 │
│  • LSTM/Prophet Models  • Sharpe Ratio Optimizer               │
│  • Technical Indicators  • Model Registry (MLflow)             │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       BI LAYER                                   │
│  • Streamlit Dashboard  • Plotly/Dash  • Metabase              │
│  • Real-time Monitoring  • Alerts & Notifications              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
crypto-analytics-platform/
├── docker/
│   ├── docker-compose.yml          # All services orchestration
│   ├── airflow.Dockerfile
│   ├── dbt.Dockerfile
│   └── streamlit.Dockerfile
│
├── airflow/
│   ├── dags/
│   │   ├── bronze_ingestion_dag.py      # Raw data ingestion (15min intervals)
│   │   ├── silver_transformation_dag.py  # Data cleaning & validation
│   │   ├── gold_aggregation_dag.py      # Business metrics
│   │   ├── ml_training_dag.py           # Model training & prediction
│   │   └── portfolio_optimization_dag.py # Sharpe ratio calculation
│   ├── plugins/
│   │   ├── operators/
│   │   │   ├── crypto_api_operator.py
│   │   │   └── model_training_operator.py
│   │   └── sensors/
│   │       └── data_quality_sensor.py
│   └── config/
│       └── connections.json
│
├── dbt/
│   ├── models/
│   │   ├── bronze/
│   │   │   ├── bronze_btc_raw.sql
│   │   │   ├── bronze_eth_raw.sql
│   │   │   └── schema.yml
│   │   ├── silver/
│   │   │   ├── silver_crypto_cleaned.sql
│   │   │   ├── silver_technical_indicators.sql   # SMA, EMA, Bollinger
│   │   │   ├── silver_returns.sql                # Log returns, volatility
│   │   │   └── schema.yml
│   │   └── gold/
│   │       ├── gold_crypto_metrics.sql           # Daily aggregates
│   │       ├── gold_portfolio_weights.sql        # Optimized weights
│   │       ├── gold_correlation_matrix.sql
│   │       ├── gold_price_predictions.sql
│   │       └── schema.yml
│   ├── macros/
│   │   ├── calculate_returns.sql
│   │   ├── bollinger_bands.sql
│   │   └── technical_indicators.sql
│   ├── tests/
│   │   └── data_quality_tests.sql
│   └── dbt_project.yml
│
├── ml/
│   ├── models/
│   │   ├── price_prediction/
│   │   │   ├── lstm_model.py
│   │   │   ├── prophet_model.py
│   │   │   └── ensemble_model.py
│   │   ├── portfolio_optimization/
│   │   │   ├── sharpe_optimizer.py
│   │   │   └── monte_carlo.py
│   │   └── feature_engineering/
│   │       └── technical_features.py
│   ├── training/
│   │   └── train_pipeline.py
│   ├── inference/
│   │   └── predict_pipeline.py
│   └── mlflow/
│       └── mlruns/
│
├── src/
│   ├── ingestion/
│   │   ├── yahoo_finance_client.py
│   │   ├── coingecko_client.py
│   │   └── binance_client.py
│   ├── transformation/
│   │   ├── data_cleaner.py
│   │   └── validators.py
│   └── utils/
│       ├── config.py
│       ├── logger.py
│       └── database.py
│
├── streamlit/
│   ├── app.py                      # Main dashboard
│   ├── pages/
│   │   ├── 1_📈_Live_Prices.py
│   │   ├── 2_💼_Portfolio_Optimizer.py
│   │   ├── 3_🔮_Price_Predictions.py
│   │   ├── 4_📊_Technical_Analysis.py
│   │   └── 5_🔗_Correlation_Matrix.py
│   ├── components/
│   │   ├── charts.py
│   │   └── metrics.py
│   └── config.toml
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── data_quality/
│
├── config/
│   ├── config.yaml
│   ├── db_schema.sql
│   └── secrets.env.example
│
├── scripts/
│   ├── setup_db.sh
│   ├── init_airflow.sh
│   └── seed_historical_data.py
│
├── notebooks/
│   ├── exploratory/
│   │   ├── Bitcoin_Analysis.ipynb       # Your original analysis
│   │   ├── Sharpe_Ratio_Research.ipynb
│   │   └── Correlation_Study.ipynb
│   └── experiments/
│       └── model_experiments.ipynb
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
│
├── docker-compose.yml
├── requirements.txt
├── Makefile
└── README.md
```

---

## 🎯 Medallion Architecture Deep Dive

### 🥉 Bronze Layer (Raw Data Lake)
**Purpose**: Store raw, immutable data exactly as received from sources

**Data Sources**:
- Yahoo Finance API (yfinance)
- CoinGecko API (real-time prices, market cap)
- Binance API (order book, trading volume)

**Tables**:
```sql
bronze.raw_crypto_prices
  - timestamp, symbol, open, high, low, close, volume, source_api
  
bronze.raw_market_data
  - timestamp, symbol, market_cap, circulating_supply, total_volume

bronze.raw_orderbook
  - timestamp, symbol, bids, asks, spread
```

**Ingestion Frequency**:
- Real-time: Every 1 minute (WebSocket for critical coins)
- Batch: Every 15 minutes (REST API for all coins)
- Historical: Daily backfill

---

### 🥈 Silver Layer (Cleaned & Validated)
**Purpose**: Cleaned, deduplicated, validated data with business logic applied

**dbt Models**:
```sql
silver.crypto_prices_cleaned
  - Removes duplicates, handles missing values
  - Type validation, outlier detection
  - Adds calculated fields: log_return, price_change_pct

silver.technical_indicators
  - SMA (20, 50, 200 day)
  - EMA (12, 26 day)
  - RSI, MACD, Bollinger Bands
  - Volatility metrics

silver.returns_and_risk
  - Daily returns
  - Rolling volatility (30, 60, 90 day)
  - Cumulative returns
  - Drawdown analysis
```

**Data Quality Tests** (dbt tests):
- Not null checks on critical columns
- Accepted value ranges (price > 0)
- Freshness checks (data < 1 hour old)
- Relationship integrity

---

### 🥇 Gold Layer (Business Metrics)
**Purpose**: Aggregated, business-ready data for analytics and ML

**Tables**:
```sql
gold.daily_crypto_metrics
  - Daily OHLCV aggregates
  - Volume-weighted average price
  - Daily returns, volatility
  
gold.portfolio_weights_optimized
  - Optimal allocation weights (Sharpe ratio maximization)
  - Risk metrics, expected returns
  - Rebalancing recommendations

gold.price_predictions
  - Next-day, 7-day, 30-day forecasts
  - Confidence intervals
  - Model metadata (accuracy, MAE, RMSE)

gold.correlation_matrix
  - Pairwise crypto correlations
  - Rolling correlation windows
  - Network analysis metrics
```

---

## 🌊 Airflow DAGs

### 1. **Bronze Ingestion DAG** (`bronze_ingestion_dag.py`)
```python
Schedule: */15 * * * *  (Every 15 minutes)

Tasks:
  1. fetch_yahoo_finance_data
  2. fetch_coingecko_data
  3. validate_api_response
  4. write_to_bronze_layer
  5. data_quality_check
  6. trigger_silver_dag
```

### 2. **Silver Transformation DAG** (`silver_transformation_dag.py`)
```python
Schedule: Triggered by Bronze DAG

Tasks:
  1. dbt_run_silver_models
  2. calculate_technical_indicators
  3. compute_returns_volatility
  4. run_dbt_tests
  5. trigger_gold_dag
```

### 3. **Gold Aggregation DAG** (`gold_aggregation_dag.py`)
```python
Schedule: Triggered by Silver DAG

Tasks:
  1. dbt_run_gold_models
  2. calculate_daily_metrics
  3. update_correlation_matrix
  4. generate_portfolio_weights
  5. refresh_dashboard_cache
```

### 4. **ML Training DAG** (`ml_training_dag.py`)
```python
Schedule: 0 2 * * *  (Daily at 2 AM)

Tasks:
  1. prepare_training_data
  2. train_lstm_model
  3. train_prophet_model
  4. evaluate_models
  5. register_best_model_mlflow
  6. generate_predictions
```

### 5. **Portfolio Optimization DAG** (`portfolio_optimization_dag.py`)
```python
Schedule: 0 0 * * MON  (Weekly on Monday)

Tasks:
  1. fetch_historical_returns
  2. calculate_covariance_matrix
  3. run_monte_carlo_simulation
  4. optimize_sharpe_ratio
  5. generate_rebalancing_report
  6. send_email_notification
```

---

## 🎨 BI Layer & Visualization Options

### Option 1: **Streamlit** (Recommended for Rapid Development)
✅ **Pros**: 
- Python-native, easy integration with pandas/plotly
- Real-time updates, custom ML model integration
- Fast prototyping, great for data scientists

**Dashboard Structure**:
```python
# Main App: Real-time Crypto Monitor
streamlit/app.py
  - Live price tickers
  - Interactive candlestick charts (Plotly)
  - Portfolio value tracking
  - Alert notifications

# Page 1: Portfolio Optimizer
  - Monte Carlo simulation visualization
  - Efficient frontier plot
  - Sharpe ratio maximization results
  - Rebalancing recommendations

# Page 2: Price Predictions
  - LSTM vs Prophet comparison
  - Confidence interval bands
  - Model performance metrics
  - Feature importance charts

# Page 3: Technical Analysis
  - Bollinger Bands overlay
  - RSI & MACD indicators
  - Volume analysis
  - Support/resistance levels

# Page 4: Correlation Heatmap
  - Interactive correlation matrix
  - Network graph visualization
  - Time-series correlation trends
```

### Option 2: **Plotly Dash** (Interactive Web Apps)
✅ **Pros**:
- More control over layout and callbacks
- Better for complex interactions
- Production-ready with Dash Enterprise

### Option 3: **Metabase** (Self-Service BI)
✅ **Pros**:
- No-code dashboard builder
- Great for business users
- SQL-based, connects to PostgreSQL

### Option 4: **Apache Superset** (Open-Source BI)
✅ **Pros**:
- Enterprise-grade dashboards
- Advanced filtering and drill-downs
- SQL Lab for ad-hoc queries

### Option 5: **Grafana** (Real-Time Monitoring)
✅ **Pros**:
- Best for time-series data
- Alerting and notifications
- Great for ops monitoring

---

## 🧰 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Orchestration** | Apache Airflow | DAG scheduling, workflow management |
| **Data Transformation** | dbt (Data Build Tool) | SQL transformations, testing, documentation |
| **Database** | PostgreSQL / DuckDB | OLTP + OLAP workloads |
| **Data Lake** | MinIO / S3 | Raw data storage (optional) |
| **ML Framework** | TensorFlow/PyTorch, Prophet | Price prediction models |
| **ML Ops** | MLflow | Model registry, experiment tracking |
| **API Clients** | yfinance, ccxt, requests | Data ingestion |
| **BI/Viz** | Streamlit + Plotly | Interactive dashboards |
| **Containerization** | Docker + Docker Compose | Environment consistency |
| **CI/CD** | GitHub Actions | Automated testing & deployment |
| **Monitoring** | Prometheus + Grafana (optional) | System health monitoring |

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.10+
- PostgreSQL 14+ (or use Docker)

### 1. Clone & Setup
```bash
git clone https://github.com/yourusername/crypto-analytics-platform.git
cd crypto-analytics-platform

# Copy environment variables
cp config/secrets.env.example config/secrets.env
# Edit secrets.env with your API keys

# Build Docker containers
docker-compose build

# Initialize Airflow database
docker-compose run airflow-init

# Start all services
docker-compose up -d
```

### 2. Access Services
- **Airflow UI**: http://localhost:8080 (user: admin, pass: admin)
- **Streamlit Dashboard**: http://localhost:8501
- **MLflow UI**: http://localhost:5000
- **PostgreSQL**: localhost:5432

### 3. Seed Historical Data
```bash
docker-compose exec airflow python /scripts/seed_historical_data.py
```

### 4. Trigger Initial DAGs
```bash
# Via Airflow UI or CLI
docker-compose exec airflow airflow dags trigger bronze_ingestion_dag
```

---

## 📊 Key Features

### 1. Real-Time Price Tracking
- Live Bitcoin, Ethereum, and top 20 altcoins
- 15-minute candlestick charts
- Volume-weighted average price (VWAP)

### 2. Portfolio Optimization
- Monte Carlo simulation (10,000+ iterations)
- Sharpe Ratio maximization
- Risk-adjusted return calculations
- Weekly rebalancing recommendations

### 3. Price Prediction Models
- **LSTM Neural Network**: Deep learning for time-series
- **Facebook Prophet**: Trend + seasonality decomposition
- **Ensemble Model**: Combines multiple predictions
- Rolling 7-day, 30-day forecasts

### 4. Technical Analysis
- **Indicators**: SMA, EMA, RSI, MACD, Bollinger Bands
- **Volatility**: Historical volatility, GARCH models
- **Support/Resistance**: Automatic level detection

### 5. Correlation Analysis
- Crypto correlation matrix (BTC, ETH, XRP, ADA, DOGE, BNB, DASH)
- Rolling correlation windows
- Portfolio diversification insights

### 6. Automated Alerts
- Price threshold notifications
- Volatility spike alerts
- Portfolio rebalancing triggers
- Model drift detection

---

## 🧪 Data Quality & Testing

### dbt Tests
```yaml
# models/silver/schema.yml
models:
  - name: silver_crypto_prices_cleaned
    tests:
      - dbt_utils.recency:
          field: timestamp
          interval: 1
          interval_unit: hour
    columns:
      - name: close_price
        tests:
          - not_null
          - positive_value
```

### Custom Data Quality Checks
```python
# airflow/plugins/sensors/data_quality_sensor.py
class DataQualitySensor(BaseSensorOperator):
    def poke(self, context):
        # Check for missing data
        # Validate price ranges
        # Ensure no duplicates
        return quality_passed
```

---

## 📈 Performance Optimization

1. **Incremental dbt Models**: Only process new data
2. **Airflow Task Parallelization**: Fetch multiple coins simultaneously
3. **Database Indexing**: Optimize queries on timestamp + symbol
4. **Caching**: Redis for dashboard data (5-minute TTL)
5. **Batch Predictions**: Pre-compute forecasts, serve from cache

---

## 🔒 Security Best Practices

- API keys stored in environment variables (never committed)
- Database credentials in Docker secrets
- Airflow connections encrypted
- HTTPS for production deployments
- Rate limiting on API calls

---

## 📚 Documentation

- **API Documentation**: Automatically generated with dbt docs
- **Airflow DAG Documentation**: Docstrings in each DAG file
- **Model Cards**: ML model metadata in MLflow
- **Architecture Diagrams**: `/docs/architecture/`

---

## 🛣️ Roadmap

### Phase 1 (Current)
- ✅ Basic price ingestion
- ✅ Technical indicator calculation
- ✅ Sharpe ratio optimization

### Phase 2 (Next 2 months)
- 🔲 Real-time WebSocket ingestion
- 🔲 Advanced ML models (LSTM, Transformer)
- 🔲 Automated backtesting framework
- 🔲 Sentiment analysis from Twitter/Reddit

### Phase 3 (Future)
- 🔲 Multi-exchange arbitrage detection
- 🔲 On-chain analytics integration
- 🔲 Reinforcement learning trading agents
- 🔲 Mobile app with push notifications

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

MIT License - see LICENSE file for details

---

## 📧 Contact

- **Email**: your.email@example.com
- **LinkedIn**: linkedin.com/in/yourprofile
- **Project Issues**: GitHub Issues

---

## 🙏 Acknowledgments

- Yahoo Finance API for historical price data
- CoinGecko for real-time crypto metrics
- Airflow community for orchestration patterns
- dbt community for transformation best practices

---

**Built with ❤️ for the crypto analytics community**
