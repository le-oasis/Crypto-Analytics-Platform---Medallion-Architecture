# Architecture Decision Record (ADR)

## 🎯 Project Goals Revisited

Based on your existing notebooks, we're building a production system that:

1. **Automates data collection** (replacing manual API calls)
2. **Enables price prediction** (new ML capability)
3. **Optimizes portfolios** (scaling your Sharpe ratio work)
4. **Provides real-time insights** (live dashboards)
5. **Ensures data quality** (medallion architecture)

---

## 🏛️ Architecture Decisions

### 1. Why Medallion Architecture?

**Decision**: Implement Bronze → Silver → Gold layers

**Rationale**:
- **Bronze (Raw)**: Keep immutable source data for auditability
- **Silver (Cleaned)**: Apply transformations once, reuse everywhere
- **Gold (Business)**: Pre-aggregated metrics for fast dashboard queries

**Your notebooks today**:
- All transformations happen in-notebook (no reusability)
- No data versioning or lineage
- Hard to debug when something breaks

**With medallion**:
- Each layer is testable independently
- Can rebuild downstream layers if upstream changes
- Clear separation of concerns

---

### 2. Why Airflow for Orchestration?

**Decision**: Apache Airflow as the orchestrator

**Rationale**:
- **Scheduling**: Automatic 15-min ingestion (no manual runs)
- **Dependencies**: Ensure bronze completes before silver runs
- **Monitoring**: See exactly where failures occur
- **Backfilling**: Easily fill data gaps

**Alternatives considered**:
- **Prefect**: More modern, but smaller community
- **Dagster**: Great for data assets, steeper learning curve
- **Cron jobs**: No dependency management or retry logic

**Why Airflow wins**:
- Industry standard (easier hiring/support)
- Rich ecosystem of operators
- Battle-tested at scale

---

### 3. Why dbt for Transformations?

**Decision**: Use dbt for SQL transformations

**Rationale**:
- **Your current code**: Pandas operations in notebooks
  ```python
  # Your current approach
  btc['log_returns'] = np.log(btc['Close'] / btc['Close'].shift(1))
  btc['volatility'] = btc['log_returns'].rolling(30).std()
  ```

- **With dbt**: SQL models with testing
  ```sql
  -- Reusable, version-controlled, tested
  SELECT 
      timestamp,
      symbol,
      LN(close / LAG(close) OVER (ORDER BY timestamp)) as log_return,
      STDDEV(log_return) OVER (
          ORDER BY timestamp 
          ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
      ) as volatility_30d
  FROM silver.crypto_prices_cleaned
  ```

**Benefits**:
- SQL is more readable for financial calculations
- Built-in testing framework
- Automatic documentation generation
- Incremental processing (only transform new data)

---

### 4. BI Layer: Streamlit vs Alternatives

**Decision**: Use **Streamlit + Plotly** as primary BI layer

**Comparison**:

| Tool | Pros | Cons | Use Case |
|------|------|------|----------|
| **Streamlit** | - Python-native<br>- Rapid development<br>- ML integration | - Single-threaded<br>- Limited customization | ✅ **Recommended**: Best for data science teams |
| **Plotly Dash** | - More control<br>- Better callbacks | - Steeper learning curve<br>- More boilerplate | Use if need complex interactions |
| **Metabase** | - No code<br>- Great for business users | - Limited to SQL queries<br>- No ML integration | Supplement for exec dashboards |
| **Superset** | - Enterprise features<br>- Drill-downs | - Heavy setup<br>- Java dependency | Overkill for this project |
| **Grafana** | - Best for time-series<br>- Alerting | - Limited to metrics | Use for system monitoring |

**Recommendation**: 
1. **Primary**: Streamlit (for your technical dashboard)
2. **Secondary**: Metabase (for business stakeholders)
3. **Optional**: Grafana (for system health monitoring)

**Why Streamlit?**
- You already use Plotly in notebooks! Easy migration
- Can embed your ML models directly
- Fast iteration (hot reload)
- Deploy easily with Docker

---

### 5. Database: PostgreSQL vs Alternatives

**Decision**: PostgreSQL as OLTP + light OLAP

**Alternatives considered**:

| Database | Pros | Cons | Decision |
|----------|------|------|----------|
| **PostgreSQL** | - Full SQL support<br>- TimescaleDB extension for time-series<br>- JSON support | - Not optimized for analytics | ✅ **Use for**: Transactional + medium analytics |
| **DuckDB** | - Columnar (fast analytics)<br>- Embedded (no server) | - Not for transactions<br>- Single-writer | Consider for future if analytics too slow |
| **ClickHouse** | - Lightning fast analytics<br>- Compression | - Complex setup<br>- Overkill for now | Overkill for current scale |
| **Delta Lake** | - ACID transactions<br>- Time travel | - Requires Spark<br>- More complex | Future if scale 100x |

**Decision**: Start with PostgreSQL + TimescaleDB extension
- Handles your current scale (millions of rows)
- Single database = simpler operations
- Upgrade to DuckDB later if queries slow down

---

### 6. ML Pipeline Architecture

**Your current approach**:
```python
# In notebook: All manual
stocks = ['BTC-USD', 'ETH-USD', 'LTC-USD', 'XRP-USD']
df = pdr.get_data_yahoo(stocks, start=start_date, end=end_date)
returns = df.pct_change()
# ... manual Monte Carlo simulation
```

**New production approach**:
```
┌─────────────────────────────────────────────────┐
│           ML Training Pipeline (Airflow)         │
├─────────────────────────────────────────────────┤
│  1. Feature Engineering (dbt)                    │
│     - Technical indicators (SMA, EMA, RSI)      │
│     - Returns, volatility, momentum              │
│     - Lag features for time series               │
│                                                  │
│  2. Model Training                               │
│     - LSTM (PyTorch/TensorFlow)                 │
│     - Prophet (Facebook)                         │
│     - XGBoost (for tabular)                      │
│                                                  │
│  3. Model Evaluation                             │
│     - Backtesting framework                      │
│     - Performance metrics (MAE, RMSE, Sharpe)   │
│     - Model comparison                           │
│                                                  │
│  4. Model Registry (MLflow)                      │
│     - Version tracking                           │
│     - Experiment logging                         │
│     - A/B testing support                        │
│                                                  │
│  5. Deployment                                   │
│     - Batch predictions → gold layer             │
│     - Real-time API (optional)                   │
└─────────────────────────────────────────────────┘
```

**Why this approach?**
- **Reproducibility**: Every model version tracked
- **Automation**: No manual retraining
- **Comparison**: Easily compare LSTM vs Prophet
- **Monitoring**: Track model drift over time

---

### 7. Sharpe Ratio Optimization - Production Version

**Your current notebook**:
```python
def monte_carlo_sharpe(returns, cov_matrix, num_portfolios=10000):
    # ... simulation code
    # Runs once, results lost after kernel restart
```

**Production approach**:

```sql
-- gold/portfolio_weights_optimized.sql
-- Runs weekly, stores results
WITH monte_carlo_simulation AS (
    -- dbt can call Python models!
    {{ ref('python_monte_carlo_optimizer') }}
),
optimal_weights AS (
    SELECT 
        symbol,
        weight,
        expected_return,
        portfolio_risk,
        sharpe_ratio
    FROM monte_carlo_simulation
    WHERE sharpe_ratio = MAX(sharpe_ratio)
)
SELECT 
    CURRENT_DATE as rebalance_date,
    symbol,
    weight,
    expected_return,
    portfolio_risk,
    sharpe_ratio,
    -- Compare to current holdings
    weight - LAG(weight) OVER (PARTITION BY symbol ORDER BY rebalance_date) 
        as weight_change_from_last_week
FROM optimal_weights
```

**Improvements**:
1. **Historical tracking**: See how optimal weights change over time
2. **Alerting**: Email when rebalancing needed (>5% drift)
3. **Backtesting**: Test strategy on historical data
4. **Constraints**: Add max position size, sector limits

---

## 📊 Data Flow Summary

```
┌──────────────────────────────────────────────────────────────┐
│                     DATA SOURCES                              │
│  Yahoo Finance │ CoinGecko │ Binance │ Twitter (sentiment)  │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│              AIRFLOW: bronze_ingestion_dag.py                 │
│  Every 15 minutes: Fetch prices, validate, store raw         │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│                    BRONZE LAYER (PostgreSQL)                  │
│  • raw_crypto_prices (OHLCV data)                            │
│  • raw_market_data (market cap, volume)                      │
│  • raw_orderbook (bid/ask spreads)                           │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│        AIRFLOW: silver_transformation_dag.py (triggered)      │
│  Runs dbt models: Clean, validate, add technical indicators  │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│         SILVER LAYER (dbt models on PostgreSQL)               │
│  • silver_crypto_prices_cleaned (deduped, validated)         │
│  • silver_technical_indicators (SMA, EMA, RSI, Bollinger)   │
│  • silver_returns_volatility (log returns, rolling vol)      │
│  • silver_correlations (pairwise correlations)               │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│         AIRFLOW: gold_aggregation_dag.py (triggered)          │
│  Aggregate to business metrics, run optimizations            │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│            GOLD LAYER (dbt models on PostgreSQL)              │
│  • gold_daily_crypto_metrics (daily OHLCV, returns)         │
│  • gold_portfolio_weights (optimal Sharpe allocations)       │
│  • gold_price_predictions (LSTM + Prophet forecasts)         │
│  • gold_correlation_matrix (heatmap data)                    │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────┐
│                  CONSUMPTION LAYER                            │
│                                                               │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Streamlit    │  │    Metabase     │  │  ML Models   │ │
│  │   Dashboard    │  │  (Business BI)  │  │  (Real-time  │ │
│  │   (Technical)  │  │                 │  │  Inference)  │ │
│  └────────────────┘  └─────────────────┘  └──────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## 🚀 Migration Path from Your Notebooks

### Phase 1: Setup Infrastructure (Week 1)
- [ ] Set up Docker environment
- [ ] Initialize PostgreSQL with schemas
- [ ] Deploy Airflow
- [ ] Create bronze ingestion DAG

**Deliverable**: Live data flowing into bronze layer

---

### Phase 2: Transform Your Analysis (Week 2)

**From Notebook → dbt Models**:

| Notebook Code | → | dbt Model |
|---------------|---|-----------|
| `btc['log_returns'] = ...` | → | `silver_returns_volatility.sql` |
| `btc['SMA_20'] = btc['Close'].rolling(20).mean()` | → | `silver_technical_indicators.sql` |
| Bollinger Bands calculation | → | `macros/bollinger_bands.sql` |
| Sharpe Ratio optimization | → | `gold_portfolio_weights.sql` |
| Correlation matrix | → | `gold_correlation_matrix.sql` |

---

### Phase 3: Add ML Models (Week 3)
- [ ] Train LSTM on historical data
- [ ] Deploy Prophet for trend forecasting
- [ ] Register models in MLflow
- [ ] Create `ml_training_dag.py`

**Deliverable**: Automated price predictions

---

### Phase 4: Build Dashboards (Week 4)

**Streamlit Pages**:
1. **Live Prices** - Real-time tickers (your `Bitcoin_Analysis00.ipynb` → live)
2. **Portfolio Optimizer** - Interactive Sharpe ratio tool (your `cryto_sharpe_ratio.ipynb` → automated)
3. **Price Predictions** - ML forecasts with confidence intervals
4. **Technical Analysis** - Your Bollinger Bands, SMA/EMA (your notebook → interactive)
5. **Correlation Heatmap** - Your `CryptoCorrelation.ipynb` → live updating

---

## 🎨 BI Layer - Detailed Recommendation

### Primary: Streamlit Dashboard

**File structure**:
```
streamlit/
├── app.py                    # Main entry point
├── pages/
│   ├── 1_📈_Live_Prices.py
│   ├── 2_💼_Portfolio_Optimizer.py
│   ├── 3_🔮_Price_Predictions.py
│   ├── 4_📊_Technical_Analysis.py
│   └── 5_🔗_Correlation_Matrix.py
├── components/
│   ├── charts.py             # Reusable Plotly charts
│   └── metrics.py            # KPI cards
└── utils/
    └── db.py                 # Database connections
```

**Example page (migrate your Sharpe ratio notebook)**:
```python
# pages/2_💼_Portfolio_Optimizer.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.db import get_gold_data

st.title("💼 Portfolio Optimizer")

# Fetch optimized weights from gold layer
weights_df = get_gold_data("gold_portfolio_weights_optimized")

col1, col2, col3 = st.columns(3)
col1.metric("Expected Return", f"{weights_df['expected_return'].iloc[0]:.2%}")
col2.metric("Portfolio Risk", f"{weights_df['portfolio_risk'].iloc[0]:.2%}")
col3.metric("Sharpe Ratio", f"{weights_df['sharpe_ratio'].iloc[0]:.2f}")

# Interactive pie chart (your notebook's visualization → live)
fig = go.Figure(data=[go.Pie(
    labels=weights_df['symbol'],
    values=weights_df['weight'],
    hole=.3
)])
st.plotly_chart(fig, use_container_width=True)

# Efficient frontier plot
st.subheader("Efficient Frontier")
# ... plot from your Monte Carlo simulation
```

---

### Secondary: Metabase (for Business Users)

**Use cases**:
- Executive dashboards (daily P&L, portfolio value)
- SQL-based alerts ("notify me if BTC drops >10%")
- Scheduled email reports

**Setup**:
1. Connect to PostgreSQL gold layer
2. Create questions:
   - "What's my portfolio value today?"
   - "Which coin had highest return this week?"
3. Build dashboard with 5-6 key metrics
4. Schedule daily email at 9 AM

---

## 📈 Visualization Strategy

### For Each Analysis Type:

1. **Price Analysis** (from `Bitcoin_Analysis00.ipynb`)
   - **Chart**: Candlestick with volume bars
   - **Tool**: Plotly (`go.Candlestick`)
   - **Update**: Real-time (every 15 min)

2. **Technical Indicators**
   - **Chart**: Line chart with Bollinger Bands overlay
   - **Tool**: Plotly subplots
   - **Update**: Every 15 min

3. **Portfolio Weights** (from `cryto_sharpe_ratio.ipynb`)
   - **Chart**: Pie chart + efficient frontier scatter
   - **Tool**: Plotly
   - **Update**: Weekly (Mondays)

4. **Correlation Matrix** (from `CryptoCorrelation.ipynb`)
   - **Chart**: Heatmap
   - **Tool**: Plotly (`go.Heatmap`)
   - **Update**: Daily

5. **Price Predictions**
   - **Chart**: Line chart with confidence intervals
   - **Tool**: Plotly
   - **Update**: Daily

---

## 🔧 Technology Stack - Final Choices

| Component | Technology | Why? |
|-----------|-----------|------|
| **Orchestration** | Apache Airflow | Industry standard, battle-tested |
| **Transformation** | dbt | SQL-first, great testing |
| **Database** | PostgreSQL + TimescaleDB | Handles OLTP + OLAP |
| **BI (Primary)** | Streamlit + Plotly | Python-native, rapid dev |
| **BI (Secondary)** | Metabase | For business stakeholders |
| **ML Ops** | MLflow | Model tracking & registry |
| **ML Framework** | PyTorch/TensorFlow + Prophet | Best for time-series |
| **Containerization** | Docker Compose | Local dev, easy deployment |
| **Monitoring** | Prometheus + Grafana | System health (optional) |

---

## 🎯 Next Steps

1. **Read the main README.md** for full architecture
2. **Run `make setup`** to initialize the project
3. **Start with bronze layer** - get live data flowing
4. **Migrate one notebook** - pick `Bitcoin_Analysis00.ipynb` first
5. **Add Streamlit page** - visualize live prices
6. **Iterate**: Silver → Gold → ML → Dashboards

---

## 📚 Resources

- [dbt Best Practices](https://docs.getdbt.com/guides/best-practices)
- [Airflow Tutorial](https://airflow.apache.org/docs/apache-airflow/stable/tutorial.html)
- [Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture)
- [Streamlit Gallery](https://streamlit.io/gallery)
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)

---

**Questions? Open an issue or contact the team!** 🚀
