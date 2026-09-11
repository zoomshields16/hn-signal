"""Main collector script: grab new stories, work out which are due, save the raw JSON.

Usage:
    python -m collector.collect --once   # One run, then exit (cron uses this)
    python -m collector.collect          # Loop, one run every POLL_INTERVAL_SECONDS
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

# Young stories get checked every run, older ones about hourly, and we drop them after a day.
YOUNG_FOR = timedelta(hours=2)
TRACK_FOR = timedelta(hours=24)
# 55, not 60, so a few seconds of drift can't bump a check to the next run.
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
    """New stories we haven't seen yet, plus tracked ones that are due."""
    seen = {hn_id for hn_id, _, _ in recent}
    unseen = [hn_id for hn_id in new_ids if hn_id not in seen]
    due = [
        hn_id
        for hn_id, posted_at, last_checked_at in recent
        if is_due(now - posted_at, now - last_checked_at)
    ]
    return unseen + due


def run_once(session: requests.Session, conn) -> int:
    """One collector run. Returns how many stories got saved."""
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
            # Session already retried, so one bad story shouldn't end the run.
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
