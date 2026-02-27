# Nordpool/Elering Electricity Price Fetcher

This project fetches electricity prices for Estonia from the Elering API and stores them in a PostgreSQL database.

## Prerequisites

- Docker and Docker Compose (or a running PostgreSQL instance)
- Python 3.8+

## Setup

1.  Start the database:
    ```bash
    docker run -d --name nordpool_db -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=nordpool_db -p 5432:5432 postgres:15-alpine
    ```

2.  Install dependencies:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  Initialize the database:
    ```bash
    python3 main.py --init-db
    ```

## Usage

Fetch prices for the last 24 hours (and next 24 hours):
```bash
python3 main.py
```

Fetch prices for a specific date range:
```bash
python3 main.py --start-date 2024-01-01 --days 7
```

## Scheduling

To run this daily, add a cron job:
```bash
0 10 * * * cd /path/to/project && source venv/bin/activate && python3 main.py
```
