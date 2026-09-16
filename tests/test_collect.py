"""Collector tests. HN and the db are faked, so these run instantly."""

from datetime import datetime, timedelta, timezone
from unittest.mock import ANY, MagicMock, patch

import pytest
import requests

from collector.collect import is_due, pick_stories_to_check, poll_slot, run_once

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


def test_poll_slot_rounds_down_to_five_minutes():
    assert poll_slot(datetime(2026, 9, 11, 12, 7, 31, 500, tzinfo=timezone.utc)) == datetime(
        2026, 9, 11, 12, 5, tzinfo=timezone.utc
    )


def test_young_stories_are_always_due():
    assert is_due(age=timedelta(minutes=30), since_last_check=timedelta(minutes=5))


def test_older_stories_are_due_about_hourly():
    assert not is_due(age=timedelta(hours=5), since_last_check=timedelta(minutes=20))
    assert is_due(age=timedelta(hours=5), since_last_check=timedelta(minutes=58))


def test_stories_past_a_day_are_never_due():
    assert not is_due(age=timedelta(hours=25), since_last_check=timedelta(hours=3))


def test_pick_includes_unseen_new_stories_and_due_tracked_ones():
    recent = [
        (1, NOW - timedelta(minutes=30), NOW - timedelta(minutes=5)),  # Young: due
        (2, NOW - timedelta(hours=5), NOW - timedelta(minutes=10)),  # Checked recently: not due
        (3, NOW - timedelta(hours=30), NOW - timedelta(hours=2)),  # Over a day old: not due
    ]

    picked = pick_stories_to_check(new_ids=[9, 1], recent=recent, now=NOW)

    assert picked == [9, 1]


def test_a_story_with_no_posted_time_is_seen_but_never_due():
    recent = [(4, None, NOW - timedelta(minutes=5))]

    assert pick_stories_to_check(new_ids=[4], recent=recent, now=NOW) == []


@patch("collector.collect.start_run")
@patch("collector.collect.try_lock", return_value=False)
def test_run_once_skips_when_another_run_holds_the_lock(_mock_lock, mock_start_run):
    assert run_once(MagicMock(), MagicMock()) == 0
    mock_start_run.assert_not_called()


@patch("collector.collect.unlock")
@patch("collector.collect.try_lock", return_value=True)
@patch("collector.collect.fetch_new_story_ids", side_effect=requests.ConnectionError())
def test_run_once_releases_the_lock_even_if_the_run_fails(_mock_new_ids, _mock_lock, mock_unlock):
    conn = MagicMock()

    with pytest.raises(requests.ConnectionError):
        run_once(MagicMock(), conn)

    mock_unlock.assert_called_once_with(conn)


@patch("collector.collect.insert_raw_snapshot")
@patch("collector.collect.fetch_item")
@patch("collector.collect.get_recent_stories", return_value=[])
@patch("collector.collect.fetch_new_story_ids")
def test_run_once_saves_each_picked_story(mock_new_ids, _mock_recent, mock_fetch_item, mock_insert):
    mock_new_ids.return_value = [1, 2]
    mock_fetch_item.side_effect = [{"id": 1, "score": 5}, {"id": 2, "score": 7}]
    conn = MagicMock()

    assert run_once(MagicMock(), conn) == 2
    assert mock_insert.call_count == 2
    mock_insert.assert_any_call(conn, 1, {"id": 1, "score": 5}, ANY)
    mock_insert.assert_any_call(conn, 2, {"id": 2, "score": 7}, ANY)


@patch("collector.collect.insert_raw_snapshot")
@patch("collector.collect.fetch_item")
@patch("collector.collect.get_recent_stories", return_value=[])
@patch("collector.collect.fetch_new_story_ids")
def test_run_once_only_counts_rows_actually_saved(
    mock_new_ids, _mock_recent, mock_fetch_item, mock_insert
):
    mock_new_ids.return_value = [1, 2]
    mock_fetch_item.side_effect = [{"id": 1}, {"id": 2}]
    mock_insert.side_effect = [True, False]  # Story 2 already saved in this slot

    assert run_once(MagicMock(), MagicMock()) == 1


@patch("collector.collect.insert_raw_snapshot")
@patch("collector.collect.fetch_item")
@patch("collector.collect.get_recent_stories", return_value=[])
@patch("collector.collect.fetch_new_story_ids")
def test_run_once_saves_null_answers_without_counting_them(
    mock_new_ids, _mock_recent, mock_fetch_item, mock_insert
):
    mock_new_ids.return_value = [1, 2]
    mock_fetch_item.side_effect = [None, {"id": 2, "score": 7}]
    conn = MagicMock()

    assert run_once(MagicMock(), conn) == 1
    mock_insert.assert_any_call(conn, 1, None, ANY)
    mock_insert.assert_any_call(conn, 2, {"id": 2, "score": 7}, ANY)


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
    mock_insert.assert_called_once_with(conn, 2, {"id": 2, "score": 7}, ANY)


@patch("collector.collect.finish_run")
@patch("collector.collect.start_run", return_value=42)
@patch("collector.collect.insert_raw_snapshot", return_value=True)
@patch("collector.collect.fetch_item")
@patch("collector.collect.get_recent_stories", return_value=[])
@patch("collector.collect.fetch_new_story_ids", return_value=[1, 2, 3])
def test_run_once_logs_the_run_with_its_counts(
    _mock_new_ids, _mock_recent, mock_fetch_item, _mock_insert, _mock_start, mock_finish
):
    mock_fetch_item.side_effect = [requests.ConnectionError(), None, {"id": 3}]
    conn = MagicMock()

    run_once(MagicMock(), conn)

    mock_finish.assert_called_once_with(conn, 42, due=3, saved=1, failed=1, nulls=1)


@patch("collector.collect.time")
@patch("collector.collect.insert_raw_snapshot", return_value=True)
@patch("collector.collect.fetch_item", return_value={"id": 1})
@patch("collector.collect.get_recent_stories", return_value=[])
@patch("collector.collect.fetch_new_story_ids", return_value=[1, 2, 3])
def test_run_stops_starting_new_fetches_after_the_deadline(
    _mock_new_ids, _mock_recent, mock_fetch_item, _mock_insert, mock_time
):
    # Clock: start, before story 1, before story 2 (too late), log line.
    mock_time.monotonic.side_effect = [0, 0, 300, 300]

    assert run_once(MagicMock(), MagicMock()) == 1
    mock_fetch_item.assert_called_once()
