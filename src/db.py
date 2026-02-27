import os
import logging
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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

    create_table_query = """
    CREATE TABLE IF NOT EXISTS electricity_prices (
        timestamp TIMESTAMP PRIMARY KEY,
        price NUMERIC(10, 2) NOT NULL,
        region VARCHAR(10) NOT NULL
    );
    """
    
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(create_table_query)
        logger.info("Database initialized successfully.")
    except psycopg2.Error as e:
        logger.error(f"Error initializing database: {e}")
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
    ON CONFLICT (timestamp) DO NOTHING;
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
