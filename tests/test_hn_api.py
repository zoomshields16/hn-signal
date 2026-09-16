"""HN API tests. Fake responses, so no internet needed."""

from unittest.mock import MagicMock

from collector.hn_api import fetch_item, fetch_new_story_ids, make_session


def _mock_response(json_value):
    resp = MagicMock()
    resp.json.return_value = json_value
    resp.raise_for_status.return_value = None
    return resp


def test_make_session_retries_failed_requests():
    retries = make_session().get_adapter("https://hacker-news.firebaseio.com").max_retries

    assert retries.total == 3
    assert 503 in retries.status_forcelist
    assert 429 not in retries.status_forcelist
    assert not retries.respect_retry_after_header


def test_fetch_new_story_ids_returns_the_list():
    session = MagicMock()
    session.get.return_value = _mock_response([3, 2, 1])

    assert fetch_new_story_ids(session) == [3, 2, 1]
    assert "newstories.json" in session.get.call_args[0][0]


def test_fetch_new_story_ids_handles_a_null_response():
    session = MagicMock()
    session.get.return_value = _mock_response(None)

    assert fetch_new_story_ids(session) == []


def test_fetch_item_returns_payload():
    session = MagicMock()
    session.get.return_value = _mock_response({"id": 42, "score": 10, "title": "Test"})

    result = fetch_item(session, 42)

    assert result == {"id": 42, "score": 10, "title": "Test"}
    assert "item/42.json" in session.get.call_args[0][0]


def test_fetch_item_returns_none_when_api_answers_null():
    session = MagicMock()
    session.get.return_value = _mock_response(None)

    assert fetch_item(session, 99) is None
