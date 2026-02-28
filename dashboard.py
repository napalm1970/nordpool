import streamlit as st
import pandas as pd
import logging
from src.db import get_connection
import altair as alt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data(start_date=None, end_date=None):
    """Fetches data from the database with optional date filtering."""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    
    query = "SELECT timestamp, price, region FROM electricity_prices"
    params = []
    
    if start_date and end_date:
        query += " WHERE timestamp >= %s AND timestamp <= %s"
        # Convert date to datetime to include the whole end day
        start_dt = pd.Timestamp(start_date).replace(hour=0, minute=0, second=0)
        end_dt = pd.Timestamp(end_date).replace(hour=23, minute=59, second=59)
        params = [start_dt, end_dt]
    elif start_date:
        query += " WHERE timestamp >= %s"
        start_dt = pd.Timestamp(start_date).replace(hour=0, minute=0, second=0)
        params = [start_dt]
    
    query += " ORDER BY timestamp ASC"
    
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, message=".*pandas only supports SQLAlchemy connectable.*")
            df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        logger.error(f"Database query error: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# Page Config
st.set_page_config(page_title="Nordpool Prices Estonia", layout="wide")

st.title("💡 Electricity Prices (Estonia)")

# --- Initial Data Load (to get min/max dates for range picker) ---
# We still need min/max dates for the sidebar, but we'll fetch them efficiently
def get_date_range():
    conn = get_connection()
    if not conn:
        return None, None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT MIN(timestamp), MAX(timestamp) FROM electricity_prices")
            return cur.fetchone()
    finally:
        conn.close()

min_db_ts, max_db_ts = get_date_range()

if min_db_ts:
    min_db_date = min_db_ts.date()
    max_db_date = max_db_ts.date()
    
    # Sidebar filters
    st.sidebar.header("Settings")
    
    # Date Range Selection (must be before loading filtered data)
    today = pd.Timestamp.now().date()
    default_start = today if min_db_date <= today <= max_db_date else min_db_date
    default_end = max_db_date
    
    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=(default_start, default_end),
        min_value=min_db_date,
        max_value=max_db_date,
        format="DD.MM.YYYY"
    )

    # Determine start/end for SQL
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date_pick, end_date_pick = date_range
    else:
        start_date_pick = date_range[0] if isinstance(date_range, (list, tuple)) else date_range
        end_date_pick = max_db_date

    # Load Data with SQL filtering
    df = load_data(start_date_pick, end_date_pick)
    
    if df.empty:
        st.info("No data found for the selected range.")
        st.stop()

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Sidebar filters
    st.sidebar.header("Settings")
    
    # Timezone selection
    timezone_option = st.sidebar.selectbox(
        "Timezone",
        ["Europe/Tallinn (EET/EEST)", "CET (Nord Pool)", "UTC"],
        index=0
    )
    
    # Map selection to actual timezone string
    tz_map = {
        "Europe/Tallinn (EET/EEST)": "Europe/Tallinn",
        "CET (Nord Pool)": "CET",
        "UTC": "UTC"
    }
    selected_tz = tz_map[timezone_option]
    
    # VAT Input
    vat_rate = st.sidebar.number_input("VAT (%)", min_value=0.0, max_value=100.0, value=24.0, step=0.5)
    vat_multiplier = 1 + (vat_rate / 100)

    # Unit Selection
    unit_option = st.sidebar.selectbox(
        "Display Unit",
        ["cents/kWh (Default)", "€/MWh"],
        index=0
    )
    is_cents = unit_option == "cents/kWh (Default)"
    
    # Apply Timezone
    if df['timestamp'].dt.tz is None:
        df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
    
    df['timestamp'] = df['timestamp'].dt.tz_convert(selected_tz)

    # Apply VAT to prices
    df['price'] = df['price'] * vat_multiplier

    # Unit Conversion for display
    # 1 EUR/MWh = 0.1 cents/kWh
    if is_cents:
        df['display_price'] = df['price'] / 10
        price_unit = "¢/kWh"
    else:
        df['display_price'] = df['price']
        price_unit = "€/MWh"

    # (Date range logic moved above)
    filtered_df = df # Data is already filtered by SQL


    # Metrics
    if not filtered_df.empty:
        # Get price for current hour
        # Use localized "now" and strip to hour precision for matching
        current_time_full = pd.Timestamp.now(tz=selected_tz)
        current_time_hour = current_time_full.floor('h')
        
        # In the dataframe, timestamps are also localized to selected_tz
        # We look for the row where timestamp is less than or equal to now, and closest to it
        current_hour_row = filtered_df[filtered_df['timestamp'] <= current_time_full].tail(1)
        
        if not current_hour_row.empty:
            current_price = current_hour_row.iloc[0]['display_price']
            price_label = f"Current Price ({current_hour_row.iloc[0]['timestamp'].strftime('%H:%M')})"
        else:
            current_price = filtered_df.iloc[-1]['display_price']
            price_label = "Latest Available Price"
            
        # Calculate metrics with timestamps
        avg_price = filtered_df['display_price'].mean()
        
        max_idx = filtered_df['display_price'].idxmax()
        max_row = filtered_df.loc[max_idx]
        max_price = max_row['display_price']
        max_time = max_row['timestamp'].strftime('%H:%M')
        
        min_idx = filtered_df['display_price'].idxmin()
        min_row = filtered_df.loc[min_idx]
        min_price = min_row['display_price']
        min_time = min_row['timestamp'].strftime('%H:%M')
        
        st.subheader(f"Key Metrics ({price_unit})")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(price_label, f"{current_price:.2f} {price_unit}")
            
        with col2:
            st.metric("Average Price", f"{avg_price:.2f} {price_unit}")
            
        with col3:
            st.metric(f"Max Price ({max_time})", f"{max_price:.2f} {price_unit}")
            
        with col4:
            st.metric(f"Min Price ({min_time})", f"{min_price:.2f} {price_unit}")
        
        # Prepare chart data
        chart_df = filtered_df.copy()
        now_dt = pd.Timestamp.now(tz='UTC')

        # Chart
        st.subheader(f"Price History ({price_unit})")
        
        # Base chart for the line
        base = alt.Chart(chart_df).encode(
            x=alt.X('timestamp:T', title='Time', axis=alt.Axis(format='%d.%m.%Y %H:%M'), scale=alt.Scale(nice=True))
        )

        # The price line
        line = base.mark_line().encode(
            y=alt.Y('display_price:Q', title=f'Price ({price_unit})')
        )

        # Selection for interactive vertical line (cursor)
        hover_selection = alt.selection_point(
            fields=['timestamp'],
            nearest=True,
            on='mouseover',
            empty=False,
        )

        # Vertical rule that follows the mouse
        hover_rule = base.mark_rule(color='#aaaaaa', strokeWidth=1).encode(
            opacity=alt.condition(hover_selection, alt.value(0.5), alt.value(0)),
            tooltip=[
                alt.Tooltip('timestamp:T', format='%d.%m.%Y %H:%M', title='Time'),
                alt.Tooltip('display_price:Q', format='.2f', title=f'Price ({price_unit})')
            ]
        ).add_params(hover_selection)

        # Static vertical rule for "Now" (only show if within range)
        now_dt = pd.Timestamp.now(tz=selected_tz)
        layers = [line, hover_rule]
        
        if chart_df['timestamp'].min() <= now_dt <= chart_df['timestamp'].max():
            now_rule = alt.Chart(pd.DataFrame({'now': [now_dt]})).mark_rule(
                color='red', 
                strokeDash=[5, 5],
                strokeWidth=2
            ).encode(x='now:T')
            layers.append(now_rule)

        # Combine layers
        final_chart = alt.layer(*layers).properties(height=450)
        
        st.altair_chart(final_chart, use_container_width=True)
        
        # Data Table with 24h formatting
        with st.expander("Show Raw Data"):
            # Format for display
            display_df = filtered_df.copy()
            display_df['timestamp'] = display_df['timestamp'].dt.strftime('%d.%m.%Y %H:%M')
            st.dataframe(display_df, width='stretch')
            
    else:
        st.warning("No data available for the selected period.")
else:
    st.info("No data found in database. Run 'main.py' to fetch data.")

st.divider()
st.caption("Data source: [Elering NPS API](https://dashboard.elering.ee). Prices are in CET/EET (Nord Pool local time).")
