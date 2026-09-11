import json

import psycopg

from collector.config import DATABASE_URL


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def insert_raw_snapshot(conn: psycopg.Connection, hn_id: int, payload: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO raw_snapshots (hn_id, payload) VALUES (%s, %s)",
            (hn_id, json.dumps(payload)),
        )
    conn.commit()
