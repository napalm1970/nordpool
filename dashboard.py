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
def load_data():
    """Fetches data from the database."""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    
    query = "SELECT timestamp, price, region FROM electricity_prices ORDER BY timestamp ASC"
    
    try:
        # Use pandas to read sql directly
        df = pd.read_sql_query(query, conn)
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

# Load Data
df = load_data()

if not df.empty:
    # Convert timestamp to datetime just in case (pandas usually handles it)
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
    vat_rate = st.sidebar.number_input("VAT (%)", min_value=0.0, max_value=100.0, value=22.0, step=0.5)
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

    # Date Range
    # ... (skipping some logic to find context)
    min_db_date = df['timestamp'].min().date()
    max_db_date = df['timestamp'].max().date()
    
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
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        mask = (df['timestamp'].dt.date >= start_date) & (df['timestamp'].dt.date <= end_date)
        filtered_df = df.loc[mask]
    else:
        start_date = date_range[0]
        mask = (df['timestamp'].dt.date >= start_date)
        filtered_df = df.loc[mask]

    # Metrics
    if not filtered_df.empty:
        # Get price for current hour
        current_time = pd.Timestamp.now(tz=selected_tz).replace(minute=0, second=0, microsecond=0)
        current_hour_row = filtered_df[filtered_df['timestamp'] == current_time]
        
        if not current_hour_row.empty:
            current_price = current_hour_row.iloc[0]['display_price']
            price_label = "Current Hour Price"
        else:
            current_price = filtered_df.iloc[-1]['display_price']
            price_label = "Latest Available Price"
            
        avg_price = filtered_df['display_price'].mean()
        max_price = filtered_df['display_price'].max()
        min_price = filtered_df['display_price'].min()
        
        st.subheader(f"Key Metrics ({price_unit})")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(price_label, f"{current_price:.2f} {price_unit}")
            
        with col2:
            st.metric("Average Price", f"{avg_price:.2f} {price_unit}")
            
        with col3:
            st.metric("Max Price", f"{max_price:.2f} {price_unit}")
            
        with col4:
            st.metric("Min Price", f"{min_price:.2f} {price_unit}")
        
        # Prepare chart data
        chart_df = filtered_df.copy()
        now_dt = pd.Timestamp.now(tz='UTC')

        # Chart
        st.subheader(f"Price History ({price_unit})")
        
        # Base chart for the line
        base = alt.Chart(chart_df).encode(
            x=alt.X('timestamp:T', title='Time', axis=alt.Axis(format='%d.%m.%Y %H:%M'))
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

        # Static vertical rule for "Now"
        now_rule = alt.Chart(pd.DataFrame({'now': [now_dt]})).mark_rule(
            color='red', 
            strokeDash=[5, 5],
            strokeWidth=2
        ).encode(x='now:T')

        # Combine layers
        final_chart = alt.layer(
            line, hover_rule, now_rule
        ).interactive().properties(height=400)
        
        st.altair_chart(final_chart, width='stretch')
        
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
