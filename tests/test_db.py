"""Tests against real Postgres (hn_test locally, a throwaway db in CI)."""

import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from collector.db import (
    finish_run,
    get_recent_stories,
    insert_raw_snapshot,
    start_run,
    try_lock,
    unlock,
)

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
# Separate database, so tests never wipe real data.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://localhost:5432/hn_test")
SLOT = datetime(2026, 9, 11, 12, 5, tzinfo=timezone.utc)


def _postgres_is_listening() -> bool:
    settings = conninfo_to_dict(TEST_DATABASE_URL)
    address = (settings.get("host", "localhost"), int(settings.get("port", 5432)))
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex(address) == 0


@pytest.fixture(scope="session")
def schema():
    # Only a missing server is worth skipping. A missing database or a bad password
    # is a real problem and should fail loudly. CI always has a server.
    if not os.environ.get("CI") and not _postgres_is_listening():
        pytest.skip("no Postgres listening for the test database")
    # Runs every migration once, like a fresh setup.
    with psycopg.connect(TEST_DATABASE_URL) as connection:
        for path in sorted(SQL_DIR.glob("*.sql")):
            connection.execute(path.read_text())


@pytest.fixture
def conn(schema):
    connection = psycopg.connect(TEST_DATABASE_URL)
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
    hn_id, posted_at, _last_checked_at, deleted = rows[0]
    assert hn_id == 7
    assert posted_at == datetime.fromtimestamp(posted, tz=timezone.utc)
    assert deleted is False


def test_a_finished_run_records_its_counts(conn):
    run_id = start_run(conn, SLOT)
    finish_run(conn, run_id, due=10, saved=7, failed=1, nulls=2)

    row = conn.execute(
        """
        SELECT poll_slot, finished_at IS NOT NULL,
               stories_due, stories_saved, stories_failed, stories_null
        FROM collector_runs WHERE id = %s
        """,
        (run_id,),
    ).fetchone()

    assert row == (SLOT, True, 10, 7, 1, 2)


def test_only_one_run_can_hold_the_lock(conn):
    assert try_lock(conn)

    second_run = psycopg.connect(TEST_DATABASE_URL)
    try:
        assert not try_lock(second_run)
    finally:
        second_run.close()


def test_unlock_lets_the_next_run_take_the_lock(conn):
    assert try_lock(conn)
    unlock(conn)

    next_run = psycopg.connect(TEST_DATABASE_URL)
    try:
        assert try_lock(next_run)
    finally:
        next_run.close()


def test_unlock_does_nothing_on_a_closed_connection(schema):
    closed = psycopg.connect(TEST_DATABASE_URL)
    closed.close()

    unlock(closed)


def test_a_story_postgres_cannot_store_raises_a_data_error(conn):
    with pytest.raises(psycopg.DataError):
        insert_raw_snapshot(conn, 3, {"id": 3, "text": "a" + chr(0) + "b"}, SLOT)


def test_reading_the_watch_list_leaves_no_open_transaction(conn):
    get_recent_stories(conn, timedelta(hours=24))

    assert conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE


def test_a_story_with_no_posted_time_still_counts_as_seen(conn):
    assert insert_raw_snapshot(conn, 9, {"id": 9}, SLOT)

    rows = get_recent_stories(conn, timedelta(hours=24))

    assert [(hn_id, posted_at) for hn_id, posted_at, *_ in rows] == [(9, None)]


def test_a_story_marked_deleted_is_flagged(conn):
    posted = 1_700_000_000
    insert_raw_snapshot(conn, 8, {"id": 8, "time": posted}, SLOT)
    later = SLOT + timedelta(minutes=5)
    insert_raw_snapshot(conn, 8, {"id": 8, "time": posted, "deleted": True}, later)

    rows = get_recent_stories(conn, timedelta(hours=24))

    assert [(hn_id, deleted) for hn_id, _, _, deleted in rows] == [(8, True)]


@pytest.mark.parametrize("odd_time", ["soon", 1e20])
def test_an_odd_time_value_does_not_break_the_watch_list(conn, odd_time):
    insert_raw_snapshot(conn, 6, {"id": 6, "time": odd_time}, SLOT)

    rows = get_recent_stories(conn, timedelta(hours=24))

    assert [(hn_id, posted_at) for hn_id, posted_at, *_ in rows] == [(6, None)]
