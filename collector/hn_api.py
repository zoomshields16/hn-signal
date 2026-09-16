"""HN API calls. Public API, no key needed."""

import requests
from requests.adapters import HTTPAdapter, Retry

from collector.config import HN_API_BASE


def make_session() -> requests.Session:
    """Session that retries failed requests up to 3 times, backing off a bit more each time."""
    # Retry server errors (5xx) only. On a 429 we skip the story and the next run tries again,
    # and we never wait on a Retry-After header, which could stall a run for an hour.
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        respect_retry_after_header=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_new_story_ids(session: requests.Session) -> list[int]:
    """Newest ~500 story IDs, newest first. Empty list if the API answers null."""
    resp = session.get(f"{HN_API_BASE}/newstories.json", timeout=10)
    resp.raise_for_status()
    return resp.json() or []


def fetch_item(session: requests.Session, item_id: int) -> dict | None:
    """None if the API answers null for this ID."""
    resp = session.get(f"{HN_API_BASE}/item/{item_id}.json", timeout=10)
    resp.raise_for_status()
    return resp.json()
