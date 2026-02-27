import argparse
import logging
from datetime import datetime, timedelta
import pytz
from src.db import init_db, save_prices
from src.fetcher import fetch_prices

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Nordpool Electricity Price Fetcher for Estonia"
    )
    parser.add_argument(
        "--init-db", action="store_true", help="Initialize the database table"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days back and forward to fetch (default: 1)",
    )
    parser.add_argument(
        "--start-date", type=str, help="Start date in YYYY-MM-DD format (default: now)"
    )
    parser.add_argument(
        "--region", type=str, default="EE", help="Region code (default: EE)"
    )

    args = parser.parse_args()

    if args.init_db:
        init_db()

    # Determine date range
    if args.start_date:
        try:
            base_dt = datetime.strptime(args.start_date, "%d-%m-%Y").replace(
                tzinfo=pytz.utc
            )
            start_dt = base_dt
            end_dt = base_dt + timedelta(days=args.days)
        except ValueError as e:
            logger.error(f"Invalid date format: {e}. Use YYYY-MM-DD.")
            return
    else:
        now = datetime.now(pytz.utc)
        start_dt = (now - timedelta(days=args.days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_dt = (now + timedelta(days=args.days)).replace(
            hour=23, minute=59, second=59, microsecond=0
        )

    logger.info(f"Starting fetch for region {args.region} from {start_dt} to {end_dt}")
    prices = fetch_prices(start_dt=start_dt, end_dt=end_dt, region=args.region)

    if prices:
        logger.info(f"Fetched {len(prices)} records.")
        save_prices(prices)
    else:
        logger.warning("No prices fetched.")


if __name__ == "__main__":
    main()
