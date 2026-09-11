"""Thin wrapper around the public Hacker News API (no auth, no key)."""

import requests

from collector.config import HN_API_BASE


def fetch_new_story_ids(session: requests.Session) -> list[int]:
    """Up to 500 newest story IDs, newest first."""
    resp = session.get(f"{HN_API_BASE}/newstories.json", timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_item(session: requests.Session, item_id: int) -> dict | None:
    """None if the API answers null for this ID."""
    resp = session.get(f"{HN_API_BASE}/item/{item_id}.json", timeout=10)
    resp.raise_for_status()
    return resp.json()
