import os
import logging
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

def get_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        return conn
    except psycopg2.Error as e:
        logger.error(f"Error connecting to database: {e}")
        return None

def init_db():
    """Initializes the database table."""
    conn = get_connection()
    if not conn:
        return

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS electricity_prices (
                        timestamp TIMESTAMP PRIMARY KEY,
                        price NUMERIC(10, 2) NOT NULL,
                        region VARCHAR(10) NOT NULL
                    );
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_electricity_prices_timestamp
                    ON electricity_prices (timestamp);
                """)
        logger.info("Database initialized successfully.")
    except psycopg2.Error as e:
        logger.error(f"Error initializing database: {e}")
    finally:
        conn.close()

def init_weather_table():
    """Initializes the weather data table."""
    conn = get_connection()
    if not conn:
        return

    create_table_query = """
    CREATE TABLE IF NOT EXISTS weather_data (
        timestamp TIMESTAMP PRIMARY KEY,
        temperature NUMERIC(5, 2),
        humidity NUMERIC(5, 2),
        wind_speed NUMERIC(5, 2),
        wind_direction INTEGER,
        weather_code INTEGER,
        region VARCHAR(10)
    );
    """

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(create_table_query)
        logger.info("Weather table initialized successfully.")
    except psycopg2.Error as e:
        logger.error(f"Error initializing weather table: {e}")
    finally:
        conn.close()

def save_prices(prices):
    """
    Saves a list of price dictionaries to the database.
    Format: [{'timestamp': datetime, 'price': 100.5, 'region': 'EE'}, ...]
    """
    if not prices:
        logger.warning("No prices provided to save_prices.")
        return

    conn = get_connection()
    if not conn:
        return

    insert_query = """
    INSERT INTO electricity_prices (timestamp, price, region)
    VALUES %s
    ON CONFLICT (timestamp) DO UPDATE SET price = EXCLUDED.price, region = EXCLUDED.region;
    """

    data_tuples = [(p['timestamp'], p['price'], p['region']) for p in prices]

    try:
        with conn:
            with conn.cursor() as cur:
                execute_values(cur, insert_query, data_tuples)
        logger.info(f"Successfully saved {len(data_tuples)} records to database.")
    except psycopg2.Error as e:
        logger.error(f"Error saving data: {e}")
    finally:
        conn.close()

def save_weather_data(weather_list):
    """
    Saves a list of weather dictionaries to the database.
    Format: [{'timestamp': datetime, 'temperature': 10.5, 'humidity': 80, 
              'wind_speed': 5.2, 'wind_direction': 180, 'weather_code': 1, 'region': 'EE'}, ...]
    """
    if not weather_list:
        logger.warning("No weather data provided to save_weather_data.")
        return

    conn = get_connection()
    if not conn:
        return

    insert_query = """
    INSERT INTO weather_data (timestamp, temperature, humidity, wind_speed, wind_direction, weather_code, region)
    VALUES %s
    ON CONFLICT (timestamp) DO NOTHING;
    """

    data_tuples = [
        (
            w['timestamp'],
            w.get('temperature'),
            w.get('humidity'),
            w.get('wind_speed'),
            w.get('wind_direction'),
            w.get('weather_code'),
            w.get('region', 'EE')
        )
        for w in weather_list
    ]

    try:
        with conn:
            with conn.cursor() as cur:
                execute_values(cur, insert_query, data_tuples)
        logger.info(f"Successfully saved {len(data_tuples)} weather records to database.")
    except psycopg2.Error as e:
        logger.error(f"Error saving weather data: {e}")
    finally:
        conn.close()

def get_date_range():
    """Returns (min_timestamp, max_timestamp) from electricity_prices."""
    conn = get_connection()
    if not conn:
        return None, None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT MIN(timestamp), MAX(timestamp) FROM electricity_prices")
            return cur.fetchone()
    except psycopg2.Error as e:
        logger.error(f"Error fetching date range: {e}")
        return None, None
    finally:
        conn.close()


def get_prices_with_weather(start_date=None, end_date=None):
    """
    Fetches electricity prices with weather data joined.
    Returns DataFrame-ready data.
    """
    conn = get_connection()
    if not conn:
        return None

    query = """
    SELECT 
        p.timestamp,
        p.price,
        p.region,
        w.temperature,
        w.humidity,
        w.wind_speed,
        w.wind_direction,
        w.weather_code
    FROM electricity_prices p
    LEFT JOIN weather_data w ON w.timestamp = date_trunc('hour', p.timestamp)
    WHERE 1=1
    """
    params = []

    if start_date and end_date:
        query += " AND p.timestamp >= %s AND p.timestamp < %s + interval '1 day'"
        params = [start_date, end_date]
    elif start_date:
        query += " AND p.timestamp >= %s"
        params = [start_date]

    query += " ORDER BY p.timestamp ASC"

    try:
        import pandas as pd
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)
            df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        logger.error(f"Database query error: {e}")
        return None
    finally:
        conn.close()
