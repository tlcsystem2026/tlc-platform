from __future__ import annotations
import os
import psycopg2

def get_connection():
    return psycopg2.connect(
        host=os.getenv("TLC_DB_HOST", "localhost"),
        port=int(os.getenv("TLC_DB_PORT", "15432")),
        dbname=os.getenv("TLC_DB_NAME", "tlc_platform"),
        user=os.getenv("TLC_DB_USER", "tlc"),
        password=os.getenv("TLC_DB_PASSWORD", "tlc"),
    )
