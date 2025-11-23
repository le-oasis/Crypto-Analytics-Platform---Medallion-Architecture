"""
Crypto Analytics Dashboard - With ML Predictions
Advanced charts with candlesticks, volume, predictions, and RL scoring
"""

import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import json

# Page configuration
st.set_page_config(
    page_title="Crypto Analytics Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    .prediction-up {
        color: #26a69a;
        font-weight: bold;
    }
    .prediction-down {
        color: #ef5350;
        font-weight: bold;
    }
    .correct {
        background-color: rgba(38, 166, 154, 0.2);
    }
    .incorrect {
        background-color: rgba(239, 83, 80, 0.2);
    }
    </style>
""", unsafe_allow_html=True)

# Database connection
@st.cache_resource
def get_connection():
    """Create database connection"""
    return psycopg2.connect(
        host="postgres",
        port=5432,
        database="airflow",
        user="airflow",
        password="airflow"
    )

@st.cache_data(ttl=60)
def load_latest_prices():
    """Load latest prices from Gold layer"""
    conn = get_connection()
    query = """
    WITH latest_date AS (
        SELECT MAX(date) as max_date
        FROM silver_gold.gold_daily_prices
    )
    SELECT
        g.date,
        g.symbol,
        g.close as price,
        g.daily_return_pct,
        g.volume,
        g.open,
        g.high,
        g.low
    FROM silver_gold.gold_daily_prices g
    CROSS JOIN latest_date ld
    WHERE g.date = ld.max_date
    ORDER BY g.symbol
    """
    df = pd.read_sql(query, conn)
    return df

@st.cache_data(ttl=300)
def load_price_history(symbol, days=30):
    """Load price history for a specific symbol"""
    conn = get_connection()
    query = """
    SELECT
        date,
        symbol,
        open,
        high,
        low,
        close,
        volume,
        daily_return_pct,
        price_change_pct
    FROM silver_gold.gold_daily_prices
    WHERE symbol = %s
      AND date >= CURRENT_DATE - INTERVAL '%s days'
    ORDER BY date ASC
    """
    df = pd.read_sql(query, conn, params=(symbol, days))
    return df

@st.cache_data(ttl=300)
def load_multiple_symbols(symbols, days=30):
    """Load price history for multiple symbols"""
    conn = get_connection()
    placeholders = ','.join(['%s'] * len(symbols))
    query = f"""
    SELECT
        date,
        symbol,
        close,
        daily_return_pct
    FROM silver_gold.gold_daily_prices
    WHERE symbol IN ({placeholders})
      AND date >= CURRENT_DATE - INTERVAL '%s days'
    ORDER BY date ASC, symbol
    """
    df = pd.read_sql(query, conn, params=tuple(symbols) + (days,))
    return df

@st.cache_data(ttl=60)
def load_today_predictions():
    """Load today's predictions"""
    conn = get_connection()
    try:
        query = """
        SELECT
            prediction_date,
            symbol,
            predicted_direction,
            predicted_confidence,
            xgboost_direction,
            xgboost_confidence,
            lightgbm_direction,
            lightgbm_confidence,
            xgboost_weight,
            lightgbm_weight,
            fear_greed_value,
            fear_greed_classification,
            reference_close
        FROM gold.daily_predictions
        WHERE prediction_date = CURRENT_DATE
        ORDER BY symbol
        """
        df = pd.read_sql(query, conn)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_yesterday_results():
    """Load yesterday's prediction results"""
    conn = get_connection()
    try:
        query = """
        SELECT
            p.prediction_date,
            p.symbol,
            p.predicted_direction,
            p.predicted_confidence,
            p.fear_greed_value,
            p.reference_close,
            r.actual_direction,
            r.actual_close,
            r.actual_return,
            r.direction_correct,
            r.score,
            r.reward,
            r.xgboost_correct,
            r.lightgbm_correct
        FROM gold.daily_predictions p
        LEFT JOIN gold.prediction_results r
            ON p.prediction_date = r.prediction_date
            AND p.symbol = r.symbol
        WHERE p.prediction_date = CURRENT_DATE - INTERVAL '1 day'
        ORDER BY p.symbol
        """
        df = pd.read_sql(query, conn)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_rolling_accuracy():
    """Load rolling accuracy metrics"""
    conn = get_connection()
    try:
        query = """
        SELECT
            symbol,
            COUNT(*) as total_predictions,
            SUM(CASE WHEN direction_correct THEN 1 ELSE 0 END) as correct,
            ROUND(AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy,
            SUM(reward) as total_reward
        FROM gold.prediction_results
        WHERE prediction_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY symbol
        ORDER BY accuracy DESC
        """
        df = pd.read_sql(query, conn)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_recent_predictions(days=7):
    """Load recent prediction history"""
    conn = get_connection()
    try:
        query = """
        SELECT
            p.prediction_date,
            p.symbol,
            p.predicted_direction,
            p.predicted_confidence,
            r.actual_direction,
            r.actual_return,
            r.direction_correct,
            r.reward
        FROM gold.daily_predictions p
        LEFT JOIN gold.prediction_results r
            ON p.prediction_date = r.prediction_date
            AND p.symbol = r.symbol
        WHERE p.prediction_date >= CURRENT_DATE - INTERVAL '%s days'
        ORDER BY p.prediction_date DESC, p.symbol
        """
        df = pd.read_sql(query, conn, params=(days,))
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_model_weights():
    """Load current RL agent weights"""
    conn = get_connection()
    try:
        query = """
        SELECT symbol, weights, total_predictions, total_correct, total_reward
        FROM gold.rl_agent_state
        ORDER BY symbol
        """
        df = pd.read_sql(query, conn)
        return df
    except Exception:
        return pd.DataFrame()

def create_candlestick_chart(df, symbol):
    """Create an interactive candlestick chart with volume"""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=(f'{symbol} Price', 'Volume'),
        row_heights=[0.7, 0.3]
    )

    fig.add_trace(
        go.Candlestick(
            x=df['date'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='OHLC',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350'
        ),
        row=1, col=1
    )

    colors = ['#ef5350' if row['close'] < row['open'] else '#26a69a'
              for idx, row in df.iterrows()]

    fig.add_trace(
        go.Bar(
            x=df['date'],
            y=df['volume'],
            name='Volume',
            marker_color=colors,
            showlegend=False
        ),
        row=2, col=1
    )

    fig.update_layout(
        title=dict(
            text=f'{symbol} - OHLCV Chart',
            font=dict(size=20)
        ),
        xaxis_rangeslider_visible=False,
        height=700,
        hovermode='x unified',
        template='plotly_white',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig

def create_comparison_chart(df_multi):
    """Create a comparison chart for multiple symbols"""
    fig = go.Figure()

    for symbol in df_multi['symbol'].unique():
        symbol_data = df_multi[df_multi['symbol'] == symbol].copy()
        symbol_data = symbol_data.sort_values('date')

        first_price = symbol_data['close'].iloc[0]
        symbol_data['pct_change'] = ((symbol_data['close'] / first_price) - 1) * 100

        fig.add_trace(
            go.Scatter(
                x=symbol_data['date'],
                y=symbol_data['pct_change'],
                mode='lines',
                name=symbol.replace('-USD', ''),
                line=dict(width=2)
            )
        )

    fig.update_layout(
        title='Performance Comparison (% Change from Start)',
        xaxis_title='Date',
        yaxis_title='Return (%)',
        height=500,
        hovermode='x unified',
        template='plotly_white',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    return fig

def create_accuracy_chart(df_accuracy):
    """Create accuracy comparison chart"""
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_accuracy['symbol'].str.replace('-USD', ''),
        y=df_accuracy['accuracy'],
        marker_color=['#26a69a' if acc >= 50 else '#ef5350' for acc in df_accuracy['accuracy']],
        text=[f"{acc:.1f}%" for acc in df_accuracy['accuracy']],
        textposition='auto',
    ))

    fig.add_hline(y=50, line_dash="dash", line_color="gray",
                  annotation_text="50% baseline", annotation_position="right")

    fig.update_layout(
        title='30-Day Prediction Accuracy by Asset',
        xaxis_title='Asset',
        yaxis_title='Accuracy (%)',
        height=400,
        template='plotly_white',
    )

    return fig

def main():
    # Header
    st.title("📈 Crypto Analytics Platform")
    st.markdown("**ML-Powered Price Predictions with RL Scoring**")
    st.markdown("---")

    # Sidebar
    st.sidebar.header("🔧 Controls")

    # Auto-refresh toggle
    auto_refresh = st.sidebar.checkbox("Auto-refresh (60s)", value=False)
    if auto_refresh:
        st.sidebar.info("Dashboard refreshes every 60 seconds")
        import time
        time.sleep(60)
        st.rerun()

    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Data last updated
    st.sidebar.metric("Last Updated", datetime.now().strftime("%H:%M:%S"))

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Chart Controls:**")
    st.sidebar.markdown("- 🖱️ Click & drag to zoom")
    st.sidebar.markdown("- 📱 Double-click to reset")
    st.sidebar.markdown("- 🔍 Hover for details")

    # Load latest prices
    try:
        latest_df = load_latest_prices()

        if latest_df.empty:
            st.warning("No data available. Please run the Gold layer transformation.")
            return

        # Display latest prices
        st.header("💰 Current Prices")

        # Create metrics row
        cols = st.columns(len(latest_df))
        for idx, row in latest_df.iterrows():
            with cols[idx]:
                symbol_short = row['symbol'].replace('-USD', '')
                delta_color = "normal" if row['daily_return_pct'] >= 0 else "inverse"
                st.metric(
                    label=symbol_short,
                    value=f"${row['price']:,.2f}",
                    delta=f"{row['daily_return_pct']:.2f}%",
                    delta_color=delta_color
                )

        st.markdown("---")

        # Tabs for different sections
        tab1, tab2, tab3, tab4 = st.tabs([
            "🔮 ML Predictions",
            "📊 Single Asset Analysis",
            "🔄 Compare Assets",
            "📋 Price Table"
        ])

        # ==================== ML PREDICTIONS TAB ====================
        with tab1:
            st.header("🔮 ML Price Predictions")

            # Load prediction data
            today_preds = load_today_predictions()
            yesterday_results = load_yesterday_results()
            accuracy_df = load_rolling_accuracy()
            recent_preds = load_recent_predictions(7)

            # Check if we have prediction data
            has_predictions = not today_preds.empty or not yesterday_results.empty

            if has_predictions:
                # Yesterday's Results Section
                st.subheader("📊 Yesterday's Predictions vs Actual Results")

                if not yesterday_results.empty:
                    # Summary metrics
                    total = len(yesterday_results)
                    correct = yesterday_results['direction_correct'].sum() if 'direction_correct' in yesterday_results.columns else 0
                    accuracy = (correct / total * 100) if total > 0 else 0

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Predictions Made", total)
                    with col2:
                        st.metric("Correct", int(correct))
                    with col3:
                        st.metric("Accuracy", f"{accuracy:.1f}%")
                    with col4:
                        total_reward = yesterday_results['reward'].sum() if 'reward' in yesterday_results.columns else 0
                        st.metric("Total Reward", f"{total_reward:.2f}")

                    st.markdown("")

                    # Results table
                    results_data = []
                    for _, row in yesterday_results.iterrows():
                        pred_dir = "🟢 UP" if row['predicted_direction'] == 1 else "🔴 DOWN"
                        actual_dir = "🟢 UP" if row.get('actual_direction') == 1 else "🔴 DOWN" if row.get('actual_direction') == 0 else "⏳ Pending"
                        correct = "✅" if row.get('direction_correct') else "❌" if row.get('direction_correct') is not None else "⏳"
                        actual_return = f"{row.get('actual_return', 0) * 100:.2f}%" if row.get('actual_return') is not None else "-"

                        results_data.append({
                            'Symbol': row['symbol'].replace('-USD', ''),
                            'Predicted': pred_dir,
                            'Confidence': f"{row['predicted_confidence'] * 100:.1f}%",
                            'Actual': actual_dir,
                            'Return': actual_return,
                            'Result': correct,
                            'Reward': f"{row.get('reward', 0):.2f}" if row.get('reward') is not None else "-"
                        })

                    results_df = pd.DataFrame(results_data)
                    st.dataframe(results_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No results from yesterday yet. Predictions will be scored after market close.")

                st.markdown("---")

                # Today's Predictions Section
                st.subheader("🎯 Today's Predictions")

                if not today_preds.empty:
                    # Fear & Greed indicator
                    fg_value = today_preds['fear_greed_value'].iloc[0] if 'fear_greed_value' in today_preds.columns else None
                    fg_class = today_preds['fear_greed_classification'].iloc[0] if 'fear_greed_classification' in today_preds.columns else None

                    if fg_value:
                        fg_color = "#ef5350" if fg_value < 30 else "#26a69a" if fg_value > 70 else "#ffa726"
                        st.markdown(f"**Fear & Greed Index:** <span style='color:{fg_color}; font-weight:bold;'>{fg_value} ({fg_class})</span>", unsafe_allow_html=True)

                    st.markdown("")

                    # Predictions cards
                    cols = st.columns(min(5, len(today_preds)))
                    for idx, row in today_preds.iterrows():
                        col_idx = idx % len(cols)
                        with cols[col_idx]:
                            symbol = row['symbol'].replace('-USD', '')
                            direction = "UP 📈" if row['predicted_direction'] == 1 else "DOWN 📉"
                            color = "#26a69a" if row['predicted_direction'] == 1 else "#ef5350"
                            confidence = row['predicted_confidence'] * 100

                            st.markdown(f"""
                            <div style='border: 2px solid {color}; border-radius: 10px; padding: 15px; text-align: center; margin: 5px;'>
                                <h3 style='margin: 0;'>{symbol}</h3>
                                <p style='color: {color}; font-size: 24px; font-weight: bold; margin: 10px 0;'>{direction}</p>
                                <p style='margin: 0;'>Confidence: {confidence:.1f}%</p>
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.info("No predictions for today yet. Run the ML pipeline to generate predictions.")

                st.markdown("---")

                # Rolling Performance Section
                st.subheader("📈 30-Day Rolling Performance")

                if not accuracy_df.empty:
                    # Accuracy chart
                    fig_accuracy = create_accuracy_chart(accuracy_df)
                    st.plotly_chart(fig_accuracy, use_container_width=True)

                    # Performance table
                    perf_data = []
                    for _, row in accuracy_df.iterrows():
                        perf_data.append({
                            'Symbol': row['symbol'].replace('-USD', ''),
                            'Predictions': int(row['total_predictions']),
                            'Correct': int(row['correct']),
                            'Accuracy': f"{row['accuracy']:.1f}%",
                            'Total Reward': f"{row['total_reward']:.2f}"
                        })

                    perf_df = pd.DataFrame(perf_data)
                    st.dataframe(perf_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No performance data yet. Results will accumulate as predictions are scored.")

                st.markdown("---")

                # Recent Predictions History
                st.subheader("📜 Recent Prediction History (7 Days)")

                if not recent_preds.empty:
                    history_data = []
                    for _, row in recent_preds.iterrows():
                        pred_dir = "UP" if row['predicted_direction'] == 1 else "DOWN"
                        actual_dir = "UP" if row.get('actual_direction') == 1 else "DOWN" if row.get('actual_direction') == 0 else "Pending"
                        correct = "✅" if row.get('direction_correct') else "❌" if row.get('direction_correct') is not None else "⏳"

                        history_data.append({
                            'Date': row['prediction_date'].strftime('%Y-%m-%d') if hasattr(row['prediction_date'], 'strftime') else str(row['prediction_date']),
                            'Symbol': row['symbol'].replace('-USD', ''),
                            'Predicted': pred_dir,
                            'Conf': f"{row['predicted_confidence'] * 100:.0f}%",
                            'Actual': actual_dir,
                            'Result': correct
                        })

                    history_df = pd.DataFrame(history_data)
                    st.dataframe(history_df, use_container_width=True, hide_index=True, height=400)
            else:
                st.info("""
                ### 🚀 ML Predictions Not Yet Available

                The ML prediction system needs to be initialized. To generate predictions:

                1. **Initialize ML Tables**: Run the `init_ml_tables.sql` script
                2. **Train Models**: The ML pipeline will automatically train on historical data
                3. **Generate Predictions**: Run the `ml_prediction_dag` in Airflow

                Once set up, you'll see:
                - **Today's Predictions**: Direction forecasts for each crypto
                - **Yesterday's Results**: How accurate yesterday's predictions were
                - **Rolling Accuracy**: 30-day performance tracking
                - **RL Learning**: Models automatically improve based on results
                """)

        # ==================== SINGLE ASSET TAB ====================
        with tab2:
            st.header("📈 Candlestick Chart")

            symbols = latest_df['symbol'].tolist()
            selected_symbol = st.selectbox("Select cryptocurrency:", symbols, index=0, key="single")

            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)

            with col1:
                if st.button("7D", use_container_width=True):
                    st.session_state.timeframe = 7
            with col2:
                if st.button("1M", use_container_width=True):
                    st.session_state.timeframe = 30
            with col3:
                if st.button("3M", use_container_width=True):
                    st.session_state.timeframe = 90
            with col4:
                if st.button("6M", use_container_width=True):
                    st.session_state.timeframe = 180
            with col5:
                if st.button("1Y", use_container_width=True):
                    st.session_state.timeframe = 365
            with col6:
                if st.button("2Y", use_container_width=True):
                    st.session_state.timeframe = 730
            with col7:
                if st.button("ALL", use_container_width=True):
                    st.session_state.timeframe = 3000

            if 'timeframe' not in st.session_state:
                st.session_state.timeframe = 30

            history_df = load_price_history(selected_symbol, st.session_state.timeframe)

            if not history_df.empty:
                fig = create_candlestick_chart(history_df, selected_symbol)
                st.plotly_chart(fig, use_container_width=True)

                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Period High", f"${history_df['high'].max():,.2f}")
                with col2:
                    st.metric("Period Low", f"${history_df['low'].min():,.2f}")
                with col3:
                    avg_return = history_df['daily_return_pct'].mean()
                    st.metric("Avg Daily Return", f"{avg_return:.2f}%")
                with col4:
                    volatility = history_df['daily_return_pct'].std()
                    st.metric("Volatility (StdDev)", f"{volatility:.2f}%")
                with col5:
                    total_return = ((history_df['close'].iloc[-1] / history_df['close'].iloc[0]) - 1) * 100
                    st.metric("Total Return", f"{total_return:.2f}%")
            else:
                st.info(f"No data available for {selected_symbol}")

        # ==================== COMPARE ASSETS TAB ====================
        with tab3:
            st.header("🔄 Compare Multiple Assets")

            available_symbols = latest_df['symbol'].tolist()
            selected_symbols = st.multiselect(
                "Select cryptocurrencies to compare:",
                available_symbols,
                default=available_symbols[:3]
            )

            if len(selected_symbols) > 0:
                compare_days = st.slider(
                    "Days to compare:",
                    min_value=7,
                    max_value=365,
                    value=90,
                    step=7
                )

                multi_df = load_multiple_symbols(selected_symbols, compare_days)

                if not multi_df.empty:
                    fig_compare = create_comparison_chart(multi_df)
                    st.plotly_chart(fig_compare, use_container_width=True)

                    st.subheader("Performance Summary")

                    summary_data = []
                    for symbol in selected_symbols:
                        symbol_data = multi_df[multi_df['symbol'] == symbol].sort_values('date')
                        if len(symbol_data) > 0:
                            first_price = symbol_data['close'].iloc[0]
                            last_price = symbol_data['close'].iloc[-1]
                            total_return = ((last_price / first_price) - 1) * 100
                            avg_daily = symbol_data['daily_return_pct'].mean()
                            volatility = symbol_data['daily_return_pct'].std()

                            summary_data.append({
                                'Symbol': symbol.replace('-USD', ''),
                                'Start Price': f"${first_price:,.2f}",
                                'End Price': f"${last_price:,.2f}",
                                'Total Return': f"{total_return:.2f}%",
                                'Avg Daily Return': f"{avg_daily:.2f}%",
                                'Volatility': f"{volatility:.2f}%"
                            })

                    summary_df = pd.DataFrame(summary_data)
                    st.dataframe(summary_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No data available for selected symbols")
            else:
                st.info("Please select at least one cryptocurrency to compare")

        # ==================== PRICE TABLE TAB ====================
        with tab4:
            st.header("📊 Price Summary Table")

            display_df = latest_df.copy()
            display_df['price'] = display_df['price'].apply(lambda x: f"${x:,.2f}")
            display_df['open'] = display_df['open'].apply(lambda x: f"${x:,.2f}")
            display_df['high'] = display_df['high'].apply(lambda x: f"${x:,.2f}")
            display_df['low'] = display_df['low'].apply(lambda x: f"${x:,.2f}")
            display_df['volume'] = display_df['volume'].apply(lambda x: f"${x:,.0f}")
            display_df['daily_return_pct'] = display_df['daily_return_pct'].apply(lambda x: f"{x:.2f}%")

            display_df = display_df.rename(columns={
                'symbol': 'Symbol',
                'price': 'Price',
                'daily_return_pct': 'Daily Return',
                'volume': 'Volume',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'date': 'Date'
            })

            st.dataframe(
                display_df[['Symbol', 'Price', 'Daily Return', 'Open', 'High', 'Low', 'Volume']],
                use_container_width=True,
                hide_index=True
            )

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        st.exception(e)

    # Footer
    st.markdown("---")
    st.markdown("**Data Source:** Gold Layer (daily aggregations) | **ML:** XGBoost + LightGBM Ensemble | **RL Agent:** Adaptive weight learning")

if __name__ == "__main__":
    main()
