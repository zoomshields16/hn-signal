"""Tests against real Postgres (hn_test locally, a throwaway db in CI)."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest

from collector.db import finish_run, get_recent_stories, insert_raw_snapshot, start_run

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
# Separate database, so tests never wipe real data.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/hn_test")
SLOT = datetime(2026, 9, 11, 12, 5, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    connection = psycopg.connect(TEST_DATABASE_URL)
    for path in sorted(SQL_DIR.glob("*.sql")):
        connection.execute(path.read_text())
    connection.execute("TRUNCATE raw_snapshots, collector_runs")
    connection.commit()
    yield connection
    connection.close()


def test_insert_raw_snapshot_persists_payload(conn):
    assert insert_raw_snapshot(conn, 123, {"id": 123, "score": 42, "title": "Hi"}, SLOT)

    row = conn.execute(
        "SELECT hn_id, payload FROM raw_snapshots WHERE hn_id = %s", (123,)
    ).fetchone()

    assert row[0] == 123
    assert row[1] == {"id": 123, "score": 42, "title": "Hi"}


def test_same_story_is_saved_once_per_slot(conn):
    assert insert_raw_snapshot(conn, 5, {"id": 5, "score": 1}, SLOT)
    assert not insert_raw_snapshot(conn, 5, {"id": 5, "score": 2}, SLOT)
    assert insert_raw_snapshot(conn, 5, {"id": 5, "score": 3}, SLOT + timedelta(minutes=5))

    count = conn.execute("SELECT count(*) FROM raw_snapshots WHERE hn_id = 5").fetchone()[0]

    assert count == 2


def test_get_recent_stories_collapses_to_one_row_per_story(conn):
    posted = 1_700_000_000
    insert_raw_snapshot(conn, 7, {"id": 7, "time": posted}, SLOT)
    insert_raw_snapshot(conn, 7, {"id": 7, "time": posted}, SLOT + timedelta(minutes=5))

    rows = get_recent_stories(conn, timedelta(hours=24))

    assert len(rows) == 1
    hn_id, posted_at, _last_checked_at = rows[0]
    assert hn_id == 7
    assert posted_at == datetime.fromtimestamp(posted, tz=timezone.utc)


def test_a_finished_run_records_its_counts(conn):
    run_id = start_run(conn, SLOT)
    finish_run(conn, run_id, due=10, saved=8, failed=1)

    row = conn.execute(
        """
        SELECT poll_slot, finished_at IS NOT NULL, stories_due, stories_saved, stories_failed
        FROM collector_runs WHERE id = %s
        """,
        (run_id,),
    ).fetchone()

    assert row == (SLOT, True, 10, 8, 1)
