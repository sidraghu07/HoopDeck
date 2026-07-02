import os

from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=nba_cards")

pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=5, open=True)
