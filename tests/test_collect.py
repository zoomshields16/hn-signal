from unittest.mock import MagicMock, patch

from collector.collect import run_once


@patch("collector.collect.insert_raw_snapshot")
@patch("collector.collect.fetch_item")
@patch("collector.collect.fetch_top_story_ids")
def test_run_once_inserts_a_snapshot_per_story(mock_top_ids, mock_fetch_item, mock_insert):
    mock_top_ids.return_value = [1, 2]
    mock_fetch_item.side_effect = [{"id": 1, "score": 5}, {"id": 2, "score": 7}]
    session = MagicMock()
    conn = MagicMock()

    count = run_once(session, conn)

    assert count == 2
    assert mock_insert.call_count == 2
    mock_insert.assert_any_call(conn, 1, {"id": 1, "score": 5})
    mock_insert.assert_any_call(conn, 2, {"id": 2, "score": 7})


@patch("collector.collect.insert_raw_snapshot")
@patch("collector.collect.fetch_item")
@patch("collector.collect.fetch_top_story_ids")
def test_run_once_skips_deleted_items(mock_top_ids, mock_fetch_item, mock_insert):
    mock_top_ids.return_value = [1, 2]
    mock_fetch_item.side_effect = [None, {"id": 2, "score": 7}]
    session = MagicMock()
    conn = MagicMock()

    count = run_once(session, conn)

    assert count == 1
    mock_insert.assert_called_once_with(conn, 2, {"id": 2, "score": 7})
