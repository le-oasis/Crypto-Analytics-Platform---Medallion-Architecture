"""
Crypto Analytics Dashboard - Step 2: Enhanced Visualizations
Advanced charts with candlesticks, volume, and interactive features
"""

import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

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

def create_candlestick_chart(df, symbol):
    """Create an interactive candlestick chart with volume"""
    # Create subplots: price chart and volume chart
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=(f'{symbol} Price', 'Volume'),
        row_heights=[0.7, 0.3]
    )

    # Candlestick chart
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

    # Volume bars
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

    # Update layout
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

    # Update y-axes
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    return fig

def create_comparison_chart(df_multi):
    """Create a comparison chart for multiple symbols"""
    fig = go.Figure()

    # Normalize prices to percentage change from first day
    for symbol in df_multi['symbol'].unique():
        symbol_data = df_multi[df_multi['symbol'] == symbol].copy()
        symbol_data = symbol_data.sort_values('date')

        # Calculate cumulative return
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

def main():
    # Header
    st.title("📈 Crypto Analytics Platform")
    st.markdown("**Step 2:** Enhanced Visualizations with Candlesticks & Volume")
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

        # Price table
        st.header("📊 Price Summary Table")

        # Format the dataframe for display
        display_df = latest_df.copy()
        display_df['price'] = display_df['price'].apply(lambda x: f"${x:,.2f}")
        display_df['open'] = display_df['open'].apply(lambda x: f"${x:,.2f}")
        display_df['high'] = display_df['high'].apply(lambda x: f"${x:,.2f}")
        display_df['low'] = display_df['low'].apply(lambda x: f"${x:,.2f}")
        display_df['volume'] = display_df['volume'].apply(lambda x: f"${x:,.0f}")
        display_df['daily_return_pct'] = display_df['daily_return_pct'].apply(lambda x: f"{x:.2f}%")

        # Rename columns
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

        st.markdown("---")

        # Tabs for different chart types
        tab1, tab2 = st.tabs(["📊 Single Asset Analysis", "🔄 Compare Assets"])

        with tab1:
            st.header("📈 Candlestick Chart")

            # Symbol selector
            symbols = latest_df['symbol'].tolist()
            selected_symbol = st.selectbox("Select cryptocurrency:", symbols, index=0, key="single")

            # Timeframe buttons
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

            # Default timeframe
            if 'timeframe' not in st.session_state:
                st.session_state.timeframe = 30

            # Load and display history
            history_df = load_price_history(selected_symbol, st.session_state.timeframe)

            if not history_df.empty:
                # Create candlestick chart
                fig = create_candlestick_chart(history_df, selected_symbol)
                st.plotly_chart(fig, use_container_width=True)

                # Stats row
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

        with tab2:
            st.header("🔄 Compare Multiple Assets")

            # Multi-select for symbols
            available_symbols = latest_df['symbol'].tolist()
            selected_symbols = st.multiselect(
                "Select cryptocurrencies to compare:",
                available_symbols,
                default=available_symbols[:3]  # Default: first 3
            )

            if len(selected_symbols) > 0:
                # Timeframe for comparison
                compare_days = st.slider(
                    "Days to compare:",
                    min_value=7,
                    max_value=365,
                    value=90,
                    step=7
                )

                # Load multi-symbol data
                multi_df = load_multiple_symbols(selected_symbols, compare_days)

                if not multi_df.empty:
                    # Create comparison chart
                    fig_compare = create_comparison_chart(multi_df)
                    st.plotly_chart(fig_compare, use_container_width=True)

                    # Performance summary table
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

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        st.exception(e)

    # Footer
    st.markdown("---")
    st.markdown("**Data Source:** Gold Layer (daily aggregations) | **Built with:** Streamlit + dbt + PostgreSQL + Plotly")

if __name__ == "__main__":
    main()
