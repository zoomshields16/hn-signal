"""Thin wrapper around the public Hacker News API (no auth, no key)."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from collector.config import HN_API_BASE


def make_session() -> requests.Session:
    """Retries a failed request up to 3 times, waiting a little longer before each try."""
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


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
