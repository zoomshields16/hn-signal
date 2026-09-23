"""Collector tests. HN and the db are faked, so these run instantly."""

from datetime import datetime, timedelta, timezone
from unittest.mock import ANY, MagicMock, patch

import psycopg
import pytest
import requests

from collector.collect import is_due, pick_stories_to_check, poll_slot, run_once

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def fake_run_setup():
    # Pin the clock early in a slot and fake the lock and run log. Tests can patch their own.
    with (
        patch("collector.collect.utc_now", return_value=NOW + timedelta(seconds=30)),
        patch("collector.collect.try_lock", return_value=True),
        patch("collector.collect.unlock"),
        patch("collector.collect.start_run", return_value=1),
        patch("collector.collect.finish_run"),
    ):
        yield


def test_poll_slot_rounds_down_to_five_minutes():
    assert poll_slot(datetime(2026, 9, 11, 12, 7, 31, 500, tzinfo=timezone.utc)) == datetime(
        2026, 9, 11, 12, 5, tzinfo=timezone.utc
    )


def test_young_stories_are_due_every_run():
    assert is_due(age=timedelta(minutes=30), since_last_check=timedelta(minutes=5))


def test_nothing_is_due_twice_within_two_minutes():
    assert not is_due(age=timedelta(minutes=30), since_last_check=timedelta(minutes=1))


def test_a_young_story_is_still_due_after_a_late_run():
    # The last run started late, so this story was checked only 3.5 minutes ago.
    assert is_due(age=timedelta(minutes=30), since_last_check=timedelta(minutes=3, seconds=30))


def test_older_stories_are_due_about_hourly():
    assert not is_due(age=timedelta(hours=5), since_last_check=timedelta(minutes=20))
    assert is_due(age=timedelta(hours=5), since_last_check=timedelta(minutes=58))


def test_stories_past_a_day_are_never_due():
    assert not is_due(age=timedelta(hours=25), since_last_check=timedelta(hours=3))


def test_pick_puts_young_stories_first_then_new_then_older():
    recent = [
        (4, NOW - timedelta(hours=5), NOW - timedelta(minutes=58), False),  # Older: due
        (1, NOW - timedelta(minutes=30), NOW - timedelta(minutes=5), False),  # Young: due
        (2, NOW - timedelta(hours=5), NOW - timedelta(minutes=10), False),  # Not due yet
        (3, NOW - timedelta(hours=30), NOW - timedelta(hours=2), False),  # Over a day old
    ]

    picked = pick_stories_to_check(new_ids=[9, 1], recent=recent, now=NOW)

    assert picked == [1, 9, 4]


def test_a_story_with_no_posted_time_is_seen_but_never_due():
    recent = [(4, None, NOW - timedelta(minutes=5), False)]

    assert pick_stories_to_check(new_ids=[4], recent=recent, now=NOW) == []


def test_a_deleted_story_is_seen_but_never_due():
    recent = [(5, NOW - timedelta(minutes=30), NOW - timedelta(minutes=5), True)]

    assert pick_stories_to_check(new_ids=[5], recent=recent, now=NOW) == []


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
def test_run_once_skips_null_answers(mock_new_ids, _mock_recent, mock_fetch_item, mock_insert):
    mock_new_ids.return_value = [1, 2]
    mock_fetch_item.side_effect = [None, {"id": 2, "score": 7}]
    conn = MagicMock()

    assert run_once(MagicMock(), conn) == 1
    mock_insert.assert_called_once_with(conn, 2, {"id": 2, "score": 7}, ANY)


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


@patch("collector.collect.insert_raw_snapshot")
@patch("collector.collect.fetch_item")
@patch("collector.collect.get_recent_stories", return_value=[])
@patch("collector.collect.fetch_new_story_ids", return_value=[1, 2])
def test_run_once_skips_a_story_that_cannot_be_saved(
    _mock_new_ids, _mock_recent, mock_fetch_item, mock_insert
):
    mock_fetch_item.side_effect = [{"id": 1}, {"id": 2}]
    mock_insert.side_effect = [psycopg.DataError("bad character"), True]

    assert run_once(MagicMock(), MagicMock()) == 1


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


@patch("collector.collect.utc_now")
@patch("collector.collect.insert_raw_snapshot", return_value=True)
@patch("collector.collect.fetch_item", return_value={"id": 1})
@patch("collector.collect.get_recent_stories", return_value=[])
@patch("collector.collect.fetch_new_story_ids", return_value=[1, 2, 3])
def test_run_stops_starting_new_fetches_four_minutes_into_the_slot(
    _mock_new_ids, _mock_recent, mock_fetch_item, _mock_insert, mock_now
):
    # Clock: run starts 12:00:30, story 1 at 12:03:00, story 2 at 12:04:10 (too late).
    mock_now.side_effect = [
        NOW + timedelta(seconds=30),
        NOW + timedelta(minutes=3),
        NOW + timedelta(minutes=4, seconds=10),
    ]

    assert run_once(MagicMock(), MagicMock()) == 1
    mock_fetch_item.assert_called_once()


@patch("collector.collect.utc_now")
@patch("collector.collect.fetch_item")
@patch("collector.collect.get_recent_stories", return_value=[])
@patch("collector.collect.fetch_new_story_ids", return_value=[1, 2, 3])
def test_a_run_that_starts_too_late_leaves_everything_for_the_next_one(
    _mock_new_ids, _mock_recent, mock_fetch_item, mock_now
):
    mock_now.return_value = NOW + timedelta(minutes=4, seconds=45)

    assert run_once(MagicMock(), MagicMock()) == 0
    mock_fetch_item.assert_not_called()
