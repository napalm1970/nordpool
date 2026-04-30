import requests
import logging
from datetime import datetime, timedelta
import pytz
from src.utils import get_retrying_session

logger = logging.getLogger(__name__)

# Elering API endpoint
API_URL = "https://dashboard.elering.ee/api/nps/price"

def fetch_prices(start_dt=None, end_dt=None, region='EE'):
    """
    Fetches electricity prices from Elering API.
    
    :param start_dt: datetime object for start of period (UTC)
    :param end_dt: datetime object for end of period (UTC)
    :param region: Region code (e.g., 'EE', 'FI', 'LV', 'LT')
    :return: List of dictionaries with price data
    """
    
    # Defaults: fetch mostly recent data if not specified
    if not start_dt:
        start_dt = datetime.now(pytz.utc) - timedelta(days=1)
    if not end_dt:
        end_dt = datetime.now(pytz.utc) + timedelta(days=1)
        
    start_str = start_dt.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    end_str = end_dt.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    
    params = {
        'start': start_str,
        'end': end_str
    }
    
    session = get_retrying_session()
    
    try:
        logger.info(f"Fetching prices for region {region} from {start_str} to {end_str}")
        response = session.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        region_key = region.lower()
        
        if 'data' not in data or region_key not in data['data']:
            logger.warning(f"No data found for region {region} in API response")
            return []
            
        prices = []
        for entry in data['data'][region_key]:
            # entry: {"timestamp": 1704499200, "price": 105.21}
            ts = datetime.fromtimestamp(entry['timestamp'], pytz.utc)
            prices.append({
                'timestamp': ts,
                'price': entry['price'],
                'region': region
            })
            
        return prices
        
    except requests.RequestException as e:
        logger.error(f"Error fetching data from API: {e}")
        return []
