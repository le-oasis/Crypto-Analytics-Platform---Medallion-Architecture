# 🚀 Quick Start Guide - Crypto Analytics Platform

## 📋 What We Built

You now have a **production-ready architecture** that transforms your Jupyter notebooks into a scalable data platform:

### ✅ From This (Your Current Setup):
- 3 separate notebooks running manually
- Data fetched each time you run
- No automation, no scheduling
- Results lost when kernel restarts

### ✅ To This (New Architecture):
- **Automated data pipeline** (runs every 15 minutes)
- **Medallion architecture** (Bronze → Silver → Gold)
- **ML-powered predictions** (LSTM + Prophet models)
- **Interactive dashboards** (Streamlit + Plotly)
- **Production-grade orchestration** (Airflow + dbt)

---

## 📦 What You Received

### Core Documents:
1. **README.md** - Complete project documentation
2. **ARCHITECTURE.md** - Detailed design decisions & migration guide
3. **docker-compose.yml** - Full service orchestration (11 services!)
4. **Makefile** - Easy commands for setup and management

### Sample Code:
5. **bronze_ingestion_dag.py** - Example Airflow DAG for data ingestion
6. **silver_crypto_prices_cleaned.sql** - Example dbt model for transformations

---

## 🎯 Immediate Next Steps (30 Minutes)

### Step 1: Create Project Structure (5 min)
```bash
# Create directories
mkdir -p crypto-analytics-platform
cd crypto-analytics-platform

# Create subdirectories
mkdir -p {airflow/{dags,plugins,logs},dbt/models/{bronze,silver,gold},ml/models,src,streamlit,config,scripts,tests,notebooks}

# Copy provided files
# Place README.md, docker-compose.yml, Makefile, ARCHITECTURE.md in root
# Place bronze_ingestion_dag.py in airflow/dags/
# Place silver_crypto_prices_cleaned.sql in dbt/models/silver/
```

### Step 2: Create Environment File (5 min)
```bash
# Create config/secrets.env
cat > config/secrets.env << EOF
# API Keys (get free keys from these services)
YAHOO_FINANCE_API_KEY=not_needed_for_yfinance
COINGECKO_API_KEY=get_from_coingecko.com
BINANCE_API_KEY=optional
BINANCE_API_SECRET=optional

# Database
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow
POSTGRES_DB=crypto_analytics

# Airflow
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=admin
AIRFLOW_FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# MLflow
MLFLOW_TRACKING_URI=http://mlflow:5000
EOF
```

### Step 3: Build and Start (10 min)
```bash
# Build containers (takes 5-10 minutes first time)
make build

# Initialize Airflow database
make init-airflow

# Start all services
make start
```

### Step 4: Verify Services (5 min)
```bash
# Check all services are running
make ps

# Access these URLs:
# - Airflow:   http://localhost:8080 (login: admin/admin)
# - Streamlit: http://localhost:8501
# - MLflow:    http://localhost:5000
# - Jupyter:   http://localhost:8888
```

### Step 5: Trigger First DAG (5 min)
```bash
# In Airflow UI (http://localhost:8080):
# 1. Navigate to "bronze_ingestion_dag"
# 2. Toggle it ON (unpause)
# 3. Click "Trigger DAG" button
# 4. Watch it run and fetch crypto data!

# Or via command line:
make trigger-bronze
```

---

## 📊 Your Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│  SOURCES: Yahoo Finance, CoinGecko, Binance                 │
└────────────┬────────────────────────────────────────────────┘
             │ Every 15 minutes (Airflow)
             ▼
┌─────────────────────────────────────────────────────────────┐
│  🥉 BRONZE: Raw data (PostgreSQL)                           │
│     • raw_crypto_prices (OHLCV)                             │
│     • raw_market_data (market cap, volume)                  │
└────────────┬────────────────────────────────────────────────┘
             │ Triggered automatically (dbt)
             ▼
┌─────────────────────────────────────────────────────────────┐
│  🥈 SILVER: Cleaned & validated (dbt models)                │
│     • Deduplicated prices                                   │
│     • Technical indicators (SMA, EMA, RSI, Bollinger)       │
│     • Returns & volatility calculations                     │
└────────────┬────────────────────────────────────────────────┘
             │ Triggered automatically (dbt)
             ▼
┌─────────────────────────────────────────────────────────────┐
│  🥇 GOLD: Business metrics & ML predictions                 │
│     • Daily aggregates                                      │
│     • Optimized portfolio weights (Sharpe ratio)            │
│     • Price predictions (LSTM + Prophet)                    │
│     • Correlation matrices                                  │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  📊 DASHBOARDS: Streamlit + Metabase                        │
│     • Live price monitoring                                 │
│     • Portfolio optimizer                                   │
│     • Technical analysis charts                             │
│     • Prediction visualizations                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 Answering Your Specific Questions

### Q: "How could we architecture this with Airflow DAGs?"

**Answer**: 5 main DAGs (all provided in architecture):

1. **`bronze_ingestion_dag.py`** ✅ Sample provided
   - Runs every 15 minutes
   - Fetches data from Yahoo Finance, CoinGecko
   - Validates and stores in bronze layer

2. **`silver_transformation_dag.py`** (template in README)
   - Triggered after bronze completes
   - Runs dbt models to clean and transform
   - Calculates technical indicators

3. **`gold_aggregation_dag.py`** (template in README)
   - Triggered after silver completes
   - Aggregates to daily metrics
   - Runs portfolio optimization

4. **`ml_training_dag.py`** (template in README)
   - Runs daily at 2 AM
   - Trains LSTM and Prophet models
   - Generates next-day predictions

5. **`portfolio_optimization_dag.py`** (template in README)
   - Runs weekly on Mondays
   - Monte Carlo simulation (your notebook logic!)
   - Maximizes Sharpe ratio

### Q: "How to integrate dbt?"

**Answer**: dbt transforms data in Silver and Gold layers

**Example provided**: `silver_crypto_prices_cleaned.sql`
- Replaces your notebook's pandas operations with SQL
- Runs automatically via Airflow
- Includes data quality tests

**Your notebook code**:
```python
btc['log_returns'] = np.log(btc['Close'] / btc['Close'].shift(1))
```

**Becomes dbt SQL**:
```sql
LN(close / LAG(close) OVER (PARTITION BY symbol ORDER BY timestamp)) as log_return
```

### Q: "What viz to use as BI layer - just Plotly?"

**Answer**: **Streamlit + Plotly** (primary) + Metabase (secondary)

**Why this combo?**
- You already use Plotly in notebooks ✓
- Streamlit lets you keep Python workflows ✓
- Can embed your ML models directly ✓
- Metabase for exec dashboards (no code) ✓

**Architecture includes**:
- Streamlit dashboard (port 8501)
- Metabase for business users (port 3000)
- Grafana for system monitoring (port 3001)
- Jupyter for experiments (port 8888)

---

## 🛠️ Technology Stack (All Dockerized)

| Service | Port | Purpose |
|---------|------|---------|
| **PostgreSQL** | 5432 | Bronze/Silver/Gold data storage |
| **Airflow Webserver** | 8080 | DAG monitoring and management |
| **Airflow Scheduler** | - | Runs DAGs on schedule |
| **Airflow Worker** | - | Executes tasks |
| **Redis** | 6379 | Message broker for Airflow |
| **dbt** | - | SQL transformations |
| **MLflow** | 5000 | Model tracking & registry |
| **Streamlit** | 8501 | Interactive dashboard |
| **Jupyter** | 8888 | Experimentation |
| **Metabase** | 3000 | Self-service BI |
| **MinIO** | 9000, 9001 | Object storage (S3-compatible) |
| **Grafana** | 3001 | System monitoring |

---

## 📚 Migrating Your Notebooks

### Notebook 1: `Bitcoin_Analysis00.ipynb` → Live Dashboard

**Current**: Manual execution, static Plotly charts

**New**: 
1. Data flows automatically to gold layer
2. Streamlit dashboard queries gold layer
3. Live updating every 15 minutes

**Code location**: `streamlit/pages/1_📈_Live_Prices.py`

### Notebook 2: `cryto_sharpe_ratio.ipynb` → Automated Optimization

**Current**: Manual Monte Carlo simulation

**New**:
1. `portfolio_optimization_dag.py` runs weekly
2. Results stored in `gold.portfolio_weights_optimized`
3. Streamlit shows optimal allocation + efficient frontier

**Code location**: `ml/models/portfolio_optimization/sharpe_optimizer.py`

### Notebook 3: `CryptoCorrelation.ipynb` → Live Correlation Matrix

**Current**: Static correlation calculation

**New**:
1. dbt model calculates rolling correlations daily
2. Stored in `gold.correlation_matrix`
3. Streamlit renders interactive heatmap

**Code location**: `dbt/models/gold/gold_correlation_matrix.sql`

---

## ⚡ Quick Commands (via Makefile)

```bash
# Setup
make setup              # Initial setup
make build              # Build containers
make start              # Start all services
make stop               # Stop all services

# Development
make logs               # View all logs
make shell-airflow      # Open Airflow shell
make dbt-run            # Run dbt models
make dbt-test           # Test data quality

# Trigger DAGs
make trigger-bronze     # Ingest data now
make trigger-ml         # Train models now

# Monitoring
make ps                 # Check service status
make health             # Health check all services

# Database
make db-connect         # Connect to PostgreSQL
make db-backup          # Backup database

# Cleanup
make clean              # Remove everything
```

---

## 🎓 Learning Resources

### Must-Read (in order):
1. **README.md** - Complete project overview
2. **ARCHITECTURE.md** - Design decisions & migration guide
3. [Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture) - Concept deep dive
4. [dbt Tutorial](https://docs.getdbt.com/tutorial/setting-up) - Learn transformations
5. [Airflow Tutorial](https://airflow.apache.org/docs/apache-airflow/stable/tutorial.html) - DAG creation

### Video Tutorials:
- [Medallion Architecture Explained](https://www.youtube.com/results?search_query=medallion+architecture)
- [dbt Fundamentals](https://courses.getdbt.com/collections)
- [Airflow for Data Engineering](https://www.youtube.com/results?search_query=airflow+data+engineering)

---

## 🐛 Troubleshooting

### Issue: Containers won't start
```bash
# Check Docker is running
docker --version

# Check logs
make logs

# Clean and rebuild
make clean
make build
make start
```

### Issue: Airflow DAG not running
```bash
# Check scheduler logs
make logs-airflow

# Verify DAG is unpaused in UI
# Check for import errors in DAG file
```

### Issue: Can't connect to database
```bash
# Test connection
make db-connect

# Check PostgreSQL logs
docker-compose logs postgres

# Verify credentials in config/secrets.env
```

---

## 📈 Roadmap: What to Build Next

### Week 1: Get it Running
- ✅ Follow this quick start guide
- ✅ Get bronze layer ingesting data
- ✅ Verify Airflow DAG runs successfully

### Week 2: Add Silver Layer
- Create dbt models for your analyses
- Migrate Bitcoin analysis calculations
- Add technical indicators (SMA, EMA, RSI)

### Week 3: Build Gold Layer
- Daily aggregation models
- Portfolio optimization automation
- Correlation matrix calculations

### Week 4: Dashboards & ML
- Build Streamlit dashboard
- Train first LSTM model
- Deploy price predictions

### Future Enhancements:
- Sentiment analysis from Twitter/Reddit
- Multi-exchange arbitrage detection
- Reinforcement learning trading bot
- Mobile app with push notifications

---

## 🎯 Success Criteria

You'll know it's working when:
- ✅ Airflow DAG runs every 15 minutes automatically
- ✅ New crypto data appears in PostgreSQL bronze layer
- ✅ dbt models transform data to silver/gold
- ✅ Streamlit dashboard shows live prices
- ✅ Portfolio weights update weekly
- ✅ ML models predict next-day prices

---

## 💡 Pro Tips

1. **Start Small**: Get bronze layer working first, then add complexity
2. **Use Jupyter**: Keep for experimentation, but move working code to production
3. **Version Control**: Git commit after each working feature
4. **Monitor DAGs**: Check Airflow UI daily for failures
5. **Test Data Quality**: dbt tests catch issues early
6. **Document**: Update README as you add features

---

## 🤝 Need Help?

- **Documentation**: Check README.md and ARCHITECTURE.md
- **Airflow Issues**: View logs with `make logs-airflow`
- **dbt Questions**: Run `make dbt-test` to check data quality
- **Database Queries**: Use `make db-connect` to explore data

---

## 🚀 You're Ready!

You now have everything needed to build a **production-grade crypto analytics platform**. 

**Next step**: Run `make setup` and follow the prompts!

Good luck! 🎉
