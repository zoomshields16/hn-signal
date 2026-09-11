"""Thin wrapper around the public Hacker News API (no auth, no key)."""

import requests

from collector.config import HN_API_BASE


def fetch_top_story_ids(session: requests.Session, limit: int) -> list[int]:
    resp = session.get(f"{HN_API_BASE}/topstories.json", timeout=10)
    resp.raise_for_status()
    return resp.json()[:limit]


def fetch_item(session: requests.Session, item_id: int) -> dict | None:
    """Returns None for deleted/dead items, which the API reports as null."""
    resp = session.get(f"{HN_API_BASE}/item/{item_id}.json", timeout=10)
    resp.raise_for_status()
    return resp.json()
