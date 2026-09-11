"""Polls the HN API and lands raw item JSON into Postgres.

Usage:
    python -m collector.collect --once   # single poll, exits (for cron)
    python -m collector.collect          # foreground loop, polls every POLL_INTERVAL_SECONDS
"""

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone

import requests

from collector.config import POLL_INTERVAL_SECONDS
from collector.db import get_connection, get_recent_stories, insert_raw_snapshot
from collector.hn_api import fetch_item, fetch_new_story_ids, make_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

YOUNG_FOR = timedelta(hours=2)
TRACK_FOR = timedelta(hours=24)
# Just under an hour, so a few seconds of timing drift can't push a check to the next poll.
OLDER_EVERY = timedelta(minutes=55)


def is_due(age: timedelta, since_last_check: timedelta) -> bool:
    if age >= TRACK_FOR:
        return False
    if age < YOUNG_FOR:
        return True
    return since_last_check >= OLDER_EVERY


def pick_stories_to_check(
    new_ids: list[int], recent: list[tuple[int, datetime, datetime]], now: datetime
) -> list[int]:
    """Brand-new stories we haven't seen yet, plus tracked stories that are due."""
    seen = {hn_id for hn_id, _, _ in recent}
    unseen = [hn_id for hn_id in new_ids if hn_id not in seen]
    due = [
        hn_id
        for hn_id, posted_at, last_checked_at in recent
        if is_due(now - posted_at, now - last_checked_at)
    ]
    return unseen + due


def run_once(session: requests.Session, conn) -> int:
    """Saves one raw snapshot for every story that's due. Returns how many were saved."""
    started = time.monotonic()
    now = datetime.now(timezone.utc)
    to_check = pick_stories_to_check(
        fetch_new_story_ids(session), get_recent_stories(conn, TRACK_FOR), now
    )
    count = 0
    for story_id in to_check:
        try:
            item = fetch_item(session, story_id)
        except requests.RequestException:
            logger.warning("item %s failed after retries, skipping", story_id)
            continue
        if item is None:
            logger.warning("item %s returned null, skipping", story_id)
            continue
        insert_raw_snapshot(conn, story_id, item)
        count += 1
    logger.info("saved %d/%d stories in %.1fs", count, len(to_check), time.monotonic() - started)
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="poll a single time and exit")
    args = parser.parse_args()

    session = make_session()
    conn = get_connection()
    try:
        if args.once:
            run_once(session, conn)
            return
        while True:
            try:
                run_once(session, conn)
            except requests.RequestException:
                logger.exception("poll failed, will retry next interval")
            time.sleep(POLL_INTERVAL_SECONDS)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
