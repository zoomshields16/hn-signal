"""Tests against real Postgres (hn_test locally, a throwaway db in CI)."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest

from collector.db import get_recent_stories, insert_raw_snapshot

DDL_PATH = Path(__file__).resolve().parent.parent / "sql" / "001_create_raw_snapshots.sql"
# Separate database, so tests never wipe real data.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/hn_test")


@pytest.fixture
def conn():
    connection = psycopg.connect(TEST_DATABASE_URL)
    connection.execute(DDL_PATH.read_text())
    connection.execute("TRUNCATE raw_snapshots")
    connection.commit()
    yield connection
    connection.close()


def test_insert_raw_snapshot_persists_payload(conn):
    insert_raw_snapshot(conn, hn_id=123, payload={"id": 123, "score": 42, "title": "Hi"})

    row = conn.execute(
        "SELECT hn_id, payload FROM raw_snapshots WHERE hn_id = %s", (123,)
    ).fetchone()

    assert row[0] == 123
    assert row[1] == {"id": 123, "score": 42, "title": "Hi"}


def test_get_recent_stories_collapses_to_one_row_per_story(conn):
    posted = 1_700_000_000
    insert_raw_snapshot(conn, hn_id=7, payload={"id": 7, "time": posted})
    insert_raw_snapshot(conn, hn_id=7, payload={"id": 7, "time": posted})

    rows = get_recent_stories(conn, timedelta(hours=24))

    assert len(rows) == 1
    hn_id, posted_at, _last_checked_at = rows[0]
    assert hn_id == 7
    assert posted_at == datetime.fromtimestamp(posted, tz=timezone.utc)
