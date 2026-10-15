
import os

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "myfinance"),
        user=os.getenv("DB_USER", "myfinance_user"),
        password=os.getenv("DB_PASSWORD"),
        row_factory=dict_row,
    )
