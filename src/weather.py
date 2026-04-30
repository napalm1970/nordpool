import requests
import logging
from datetime import datetime, timedelta
import pytz
from src.utils import get_retrying_session

logger = logging.getLogger(__name__)

# Open-Meteo Forecast API (supports past_days for recent historical data)
API_URL = "https://api.open-meteo.com/v1/forecast"

# Координаты Таллина по умолчанию
DEFAULT_LAT = 59.4370
DEFAULT_LON = 24.7536


def fetch_weather_hourly(start_dt=None, end_dt=None, lat=DEFAULT_LAT, lon=DEFAULT_LON):
    """
    Fetches hourly weather data from Open-Meteo Archive API.

    :param start_dt: datetime object for start of period (UTC)
    :param end_dt: datetime object for end of period (UTC)
    :param lat: Latitude coordinate
    :param lon: Longitude coordinate
    :return: List of dictionaries with weather data
    """
    if not start_dt:
        start_dt = datetime.now(pytz.utc) - timedelta(days=1)
    if not end_dt:
        end_dt = datetime.now(pytz.utc) + timedelta(days=1)

    start_str = start_dt.strftime('%Y-%m-%d')
    end_str = end_dt.strftime('%Y-%m-%d')

    params = {
        'latitude': lat,
        'longitude': lon,
        'start_date': start_str,
        'end_date': end_str,
        'hourly': 'temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,weather_code',
        'timezone': 'UTC'
    }

    session = get_retrying_session()

    try:
        logger.info(f"Fetching weather for {lat},{lon} from {start_str} to {end_str}")
        response = session.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if 'hourly' not in data:
            logger.warning("No hourly data found in API response")
            return []

        hourly = data['hourly']
        times = hourly.get('time', [])
        temperatures = hourly.get('temperature_2m', [])
        humidities = hourly.get('relative_humidity_2m', [])
        wind_speeds = hourly.get('wind_speed_10m', [])
        wind_directions = hourly.get('wind_direction_10m', [])
        weather_codes = hourly.get('weather_code', [])

        weather_data = []
        for i, time_str in enumerate(times):
            # Parse ISO format time string: "2026-01-01T00:00"
            ts = datetime.fromisoformat(time_str).replace(tzinfo=pytz.utc)
            weather_data.append({
                'timestamp': ts,
                'temperature': temperatures[i] if i < len(temperatures) else None,
                'humidity': humidities[i] if i < len(humidities) else None,
                'wind_speed': wind_speeds[i] if i < len(wind_speeds) else None,
                'wind_direction': wind_directions[i] if i < len(wind_directions) else None,
                'weather_code': weather_codes[i] if i < len(weather_codes) else None,
                'region': 'EE'
            })

        logger.info(f"Fetched {len(weather_data)} hourly weather records")
        return weather_data

    except requests.RequestException as e:
        logger.error(f"Error fetching weather data from API: {e}")
        return []


def get_weather_icon(weather_code):
    """
    Returns emoji icon for WMO weather code.
    
    WMO Weather interpretation codes (WW):
    https://open-meteo.com/en/docs
    """
    if weather_code is None:
        return '❓'
    
    code = int(weather_code)
    
    if code == 0:
        return '☀️'  # Clear sky
    elif 1 <= code <= 3:
        return '☁️'  # Mainly clear, partly cloudy, and overcast
    elif code in (45, 48):
        return '🌫️'  # Fog and depositing rime fog
    elif 51 <= code <= 67:
        return '🌧️'  # Drizzle and freezing drizzle
    elif 71 <= code <= 77:
        return '❄️'  # Snow and freezing snow
    elif 80 <= code <= 82:
        return '🌦️'  # Rain showers
    elif 85 <= code <= 86:
        return '🌨️'  # Snow showers
    elif 95 <= code <= 99:
        return '⛈️'  # Thunderstorm
    else:
        return '❓'
