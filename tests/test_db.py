from pathlib import Path

import pytest

from collector.db import get_connection, insert_raw_snapshot

DDL_PATH = Path(__file__).resolve().parent.parent / "sql" / "001_create_raw_snapshots.sql"


@pytest.fixture
def conn():
    connection = get_connection()
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
