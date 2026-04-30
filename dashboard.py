import streamlit as st
import pandas as pd
import logging
from src.db import get_prices_with_weather, get_date_range as _get_date_range
import altair as alt
from dotenv import load_dotenv
from src.weather import get_weather_icon

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data_with_weather(start_date=None, end_date=None):
    """Fetches data from the database with weather data joined."""
    df = get_prices_with_weather(start_date, end_date)
    if df is None or df.empty:
        return pd.DataFrame()
    return df

# Page Config
st.set_page_config(page_title="Nordpool Prices Estonia", layout="wide")

st.title("💡 Electricity Prices (Estonia)")

@st.cache_data(ttl=3600)
def get_date_range():
    return _get_date_range()

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

    start_date_pick = st.sidebar.date_input(
        "Start Date",
        value=default_start,
        min_value=min_db_date,
        max_value=max_db_date,
        format="DD.MM.YYYY"
    )

    end_date_pick = st.sidebar.date_input(
        "End Date",
        value=default_end,
        min_value=min_db_date,
        max_value=max_db_date,
        format="DD.MM.YYYY"
    )

    date_range = (start_date_pick, end_date_pick)

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Load Data with SQL filtering (includes weather data)
    df = load_data_with_weather(start_date_pick, end_date_pick)
    
    if df.empty:
        st.info("No data found for the selected range.")
        st.stop()

    df['timestamp'] = pd.to_datetime(df['timestamp'])

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
        max_time = max_row['timestamp'].strftime('%d.%m %H:%M')
        
        min_idx = filtered_df['display_price'].idxmin()
        min_row = filtered_df.loc[min_idx]
        min_price = min_row['display_price']
        min_time = min_row['timestamp'].strftime('%d.%m %H:%M')
        
        st.subheader(f"Key Metrics ({price_unit})")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            price_delta = current_price - avg_price
            st.metric(price_label, f"{current_price:.2f} {price_unit}", delta=f"{price_delta:+.2f} vs avg", delta_color="inverse")
            
        with col2:
            st.metric("Average Price", f"{avg_price:.2f} {price_unit}")
            
        with col3:
            st.metric(f"Max Price ({max_time})", f"{max_price:.2f} {price_unit}")
            
        with col4:
            st.metric(f"Min Price ({min_time})", f"{min_price:.2f} {price_unit}")
        
        # Prepare chart data
        chart_df = filtered_df.copy()

        # Add date column for color grouping by day (as string for proper legend)
        chart_df['date'] = chart_df['timestamp'].dt.strftime('%d.%m.%y')

        # Chart
        st.subheader(f"Price History ({price_unit})")

        # Base chart for the line
        base = alt.Chart(chart_df).encode(
            x=alt.X('timestamp:T', title='Time', axis=alt.Axis(format='%d.%m.%y %H:%M'), scale=alt.Scale(nice=True))
        )

        # The price line with color by day
        line = base.mark_line().encode(
            y=alt.Y('display_price:Q', title=f'Price ({price_unit})'),
            color=alt.Color('date:O', title='Date', legend=alt.Legend(orient='bottom'))
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
                alt.Tooltip('timestamp:T', format='%d.%m.%y %H:%M', title='Time'),
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

        # Highlight top-5 cheapest hours
        cheapest = chart_df.nsmallest(5, 'display_price')
        cheap_points = alt.Chart(cheapest).mark_point(
            size=80, color='green', filled=True
        ).encode(
            x='timestamp:T',
            y='display_price:Q',
            tooltip=[
                alt.Tooltip('timestamp:T', format='%d.%m.%y %H:%M', title='Time'),
                alt.Tooltip('display_price:Q', format='.2f', title=f'Price ({price_unit})')
            ]
        )
        layers.append(cheap_points)

        # Combine layers
        final_chart = alt.layer(*layers).properties(height=450)

        st.altair_chart(final_chart, use_container_width=True)

        # Weather chart (if data available)
        if 'temperature' in chart_df.columns and chart_df['temperature'].notna().any():
            st.subheader("Weather Conditions")
            
            # Add weather icons
            chart_df['weather_icon'] = chart_df['weather_code'].apply(
                lambda x: get_weather_icon(x) if pd.notna(x) else '❓'
            )
            
            # Temperature chart
            temp_base = alt.Chart(chart_df).encode(
                x=alt.X('timestamp:T', title='Time', axis=alt.Axis(format='%d.%m.%y %H:%M'))
            )

            temp_line = temp_base.mark_line(color='orange').encode(
                y=alt.Y('temperature:Q', title='Temperature (°C)', scale=alt.Scale(zero=False))
            )

            temp_hover = alt.selection_point(
                fields=['timestamp'],
                nearest=True,
                on='mouseover',
                empty=False,
            )

            temp_rule = temp_base.mark_rule(color='#aaaaaa', strokeWidth=1).encode(
                opacity=alt.condition(temp_hover, alt.value(0.5), alt.value(0)),
                tooltip=[
                    alt.Tooltip('timestamp:T', format='%d.%m.%y %H:%M', title='Time'),
                    alt.Tooltip('temperature:Q', format='.1f', title='Temp (°C)'),
                    alt.Tooltip('humidity:Q', format='.0f', title='Humidity (%)'),
                    alt.Tooltip('wind_speed:Q', format='.1f', title='Wind (km/h)'),
                ]
            ).add_params(temp_hover)

            temp_chart = alt.layer(temp_line, temp_rule).properties(height=300)

            st.altair_chart(temp_chart, use_container_width=True)
            
            # Weather summary metrics
            if chart_df['temperature'].notna().any():
                temp_avg = chart_df['temperature'].mean()
                temp_max = chart_df['temperature'].max()
                temp_min = chart_df['temperature'].min()
                humidity_avg = chart_df['humidity'].mean() if 'humidity' in chart_df.columns else 0
                wind_avg = chart_df['wind_speed'].mean() if 'wind_speed' in chart_df.columns else 0
                
                st.subheader("Weather Summary")
                wcol1, wcol2, wcol3, wcol4 = st.columns(4)
                with wcol1:
                    st.metric("Avg Temperature", f"{temp_avg:.1f}°C")
                with wcol2:
                    st.metric("Max Temperature", f"{temp_max:.1f}°C")
                with wcol3:
                    st.metric("Avg Humidity", f"{humidity_avg:.0f}%")
                with wcol4:
                    st.metric("Avg Wind Speed", f"{wind_avg:.1f} km/h")

        # Data Table with 24h formatting
        with st.expander("Show Raw Data"):
            display_df = filtered_df.copy()
            if 'weather_code' in display_df.columns:
                display_df['weather'] = display_df['weather_code'].apply(
                    lambda x: get_weather_icon(x) if pd.notna(x) else '❓'
                )
            st.dataframe(
                display_df,
                use_container_width=True,
                column_config={
                    "timestamp": st.column_config.DatetimeColumn(
                        "Time", format="DD.MM.YY HH:mm", width="medium"
                    ),
                    "price": st.column_config.NumberColumn("Price (€/MWh)", format="%.4f", width="small"),
                    "display_price": st.column_config.NumberColumn(f"Price ({price_unit})", format="%.4f", width="small"),
                    "temperature": st.column_config.NumberColumn("Temp (°C)", format="%.1f", width="small"),
                    "humidity": st.column_config.NumberColumn("Humidity (%)", format="%.0f", width="small"),
                    "wind_speed": st.column_config.NumberColumn("Wind (km/h)", format="%.1f", width="small"),
                    "wind_direction": st.column_config.NumberColumn("Wind Dir", format="%d°", width="small"),
                    "weather_code": st.column_config.NumberColumn("Code", width="small"),
                    "weather": st.column_config.TextColumn("Weather", width="small"),
                    "region": st.column_config.TextColumn("Region", width="small"),
                    "date": st.column_config.TextColumn("Date", width="small"),
                },
            )

            csv_df = filtered_df.copy()
            csv_df['timestamp'] = csv_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
            st.download_button(
                label="Download CSV",
                data=csv_df.to_csv(index=False).encode('utf-8'),
                file_name='nordpool_prices.csv',
                mime='text/csv'
            )
            
    else:
        st.warning("No data available for the selected period.")
else:
    st.info("No data found in database. Run 'main.py' to fetch data.")

st.divider()
st.caption("Data source: [Elering NPS API](https://dashboard.elering.ee). Prices are in CET/EET (Nord Pool local time).")
