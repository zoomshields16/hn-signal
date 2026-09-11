import json
from datetime import datetime, timedelta

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


def get_recent_stories(
    conn: psycopg.Connection, window: timedelta
) -> list[tuple[int, datetime, datetime]]:
    """(hn_id, posted_at, last_checked_at) for every story checked within `window`."""
    return conn.execute(
        """
        SELECT hn_id,
               to_timestamp(max((payload->>'time')::bigint)) AS posted_at,
               max(fetched_at) AS last_checked_at
        FROM raw_snapshots
        WHERE fetched_at > now() - %s
          AND payload->>'time' IS NOT NULL
        GROUP BY hn_id
        """,
        (window,),
    ).fetchall()
