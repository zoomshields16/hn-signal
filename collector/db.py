"""Postgres reads/writes for the collector."""

import json
from datetime import datetime, timedelta

import psycopg

from collector.config import DATABASE_URL


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


# Any number works as the key. This one just means "the hn-signal collector".
COLLECTOR_LOCK_KEY = 8675309


def try_lock(conn: psycopg.Connection) -> bool:
    """False if another run already holds the lock. Postgres frees it when the run exits."""
    return conn.execute("SELECT pg_try_advisory_lock(%s)", (COLLECTOR_LOCK_KEY,)).fetchone()[0]


def insert_raw_snapshot(
    conn: psycopg.Connection, hn_id: int, payload: dict, poll_slot: datetime
) -> bool:
    """Store the response exactly as HN sent it. False if this slot already has the story."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw_snapshots (hn_id, poll_slot, payload)
            VALUES (%s, %s, %s)
            ON CONFLICT (hn_id, poll_slot) DO NOTHING
            """,
            (hn_id, poll_slot, json.dumps(payload)),
        )
        inserted = cur.rowcount == 1
    conn.commit()
    return inserted


def get_recent_stories(
    conn: psycopg.Connection, window: timedelta
) -> list[tuple[int, datetime, datetime]]:
    """Watch list: (hn_id, posted_at, last_checked_at) for each recently checked story."""
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


def start_run(conn: psycopg.Connection, poll_slot: datetime) -> int:
    """Log that a run started. Returns the run's id."""
    run_id = conn.execute(
        "INSERT INTO collector_runs (poll_slot) VALUES (%s) RETURNING id", (poll_slot,)
    ).fetchone()[0]
    conn.commit()
    return run_id


def finish_run(conn: psycopg.Connection, run_id: int, due: int, saved: int, failed: int) -> None:
    conn.execute(
        """
        UPDATE collector_runs
        SET finished_at = now(), stories_due = %s, stories_saved = %s, stories_failed = %s
        WHERE id = %s
        """,
        (due, saved, failed, run_id),
    )
    conn.commit()
