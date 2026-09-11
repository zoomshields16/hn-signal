from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import requests

from collector.collect import is_due, pick_stories_to_check, run_once

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


def test_young_stories_are_always_due():
    assert is_due(age=timedelta(minutes=30), since_last_check=timedelta(minutes=5))


def test_older_stories_are_due_about_hourly():
    assert not is_due(age=timedelta(hours=5), since_last_check=timedelta(minutes=20))
    assert is_due(age=timedelta(hours=5), since_last_check=timedelta(minutes=58))


def test_stories_past_a_day_are_never_due():
    assert not is_due(age=timedelta(hours=25), since_last_check=timedelta(hours=3))


def test_pick_includes_unseen_new_stories_and_due_tracked_ones():
    recent = [
        (1, NOW - timedelta(minutes=30), NOW - timedelta(minutes=5)),  # young: due
        (2, NOW - timedelta(hours=5), NOW - timedelta(minutes=10)),  # checked recently: not due
        (3, NOW - timedelta(hours=30), NOW - timedelta(hours=2)),  # over a day old: not due
    ]

    picked = pick_stories_to_check(new_ids=[9, 1], recent=recent, now=NOW)

    assert picked == [9, 1]


@patch("collector.collect.insert_raw_snapshot")
@patch("collector.collect.fetch_item")
@patch("collector.collect.get_recent_stories", return_value=[])
@patch("collector.collect.fetch_new_story_ids")
def test_run_once_saves_each_picked_story(mock_new_ids, _mock_recent, mock_fetch_item, mock_insert):
    mock_new_ids.return_value = [1, 2]
    mock_fetch_item.side_effect = [{"id": 1, "score": 5}, {"id": 2, "score": 7}]
    conn = MagicMock()

    assert run_once(MagicMock(), conn) == 2
    mock_insert.assert_any_call(conn, 1, {"id": 1, "score": 5})
    mock_insert.assert_any_call(conn, 2, {"id": 2, "score": 7})


@patch("collector.collect.insert_raw_snapshot")
@patch("collector.collect.fetch_item")
@patch("collector.collect.get_recent_stories", return_value=[])
@patch("collector.collect.fetch_new_story_ids")
def test_run_once_skips_null_items(mock_new_ids, _mock_recent, mock_fetch_item, mock_insert):
    mock_new_ids.return_value = [1, 2]
    mock_fetch_item.side_effect = [None, {"id": 2, "score": 7}]
    conn = MagicMock()

    assert run_once(MagicMock(), conn) == 1
    mock_insert.assert_called_once_with(conn, 2, {"id": 2, "score": 7})


@patch("collector.collect.insert_raw_snapshot")
@patch("collector.collect.fetch_item")
@patch("collector.collect.get_recent_stories", return_value=[])
@patch("collector.collect.fetch_new_story_ids")
def test_run_once_skips_a_story_that_keeps_failing(
    mock_new_ids, _mock_recent, mock_fetch_item, mock_insert
):
    mock_new_ids.return_value = [1, 2]
    mock_fetch_item.side_effect = [requests.ConnectionError(), {"id": 2, "score": 7}]
    conn = MagicMock()

    assert run_once(MagicMock(), conn) == 1
    mock_insert.assert_called_once_with(conn, 2, {"id": 2, "score": 7})
