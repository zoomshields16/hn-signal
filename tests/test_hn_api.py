from unittest.mock import MagicMock

from collector.hn_api import fetch_item, fetch_top_story_ids


def _mock_response(json_value):
    resp = MagicMock()
    resp.json.return_value = json_value
    resp.raise_for_status.return_value = None
    return resp


def test_fetch_top_story_ids_truncates_to_limit():
    session = MagicMock()
    session.get.return_value = _mock_response([1, 2, 3, 4, 5])

    result = fetch_top_story_ids(session, limit=3)

    assert result == [1, 2, 3]
    session.get.assert_called_once()
    assert "topstories.json" in session.get.call_args[0][0]


def test_fetch_item_returns_payload():
    session = MagicMock()
    session.get.return_value = _mock_response({"id": 42, "score": 10, "title": "Test"})

    result = fetch_item(session, 42)

    assert result == {"id": 42, "score": 10, "title": "Test"}
    assert "item/42.json" in session.get.call_args[0][0]


def test_fetch_item_returns_none_for_deleted_item():
    session = MagicMock()
    session.get.return_value = _mock_response(None)

    result = fetch_item(session, 99)

    assert result is None
