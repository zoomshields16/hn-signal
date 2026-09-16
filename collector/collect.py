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
from collector.db import (
    finish_run,
    get_connection,
    get_recent_stories,
    insert_raw_snapshot,
    start_run,
    try_lock,
    unlock,
)
from collector.hn_api import fetch_item, fetch_new_story_ids, make_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Young stories get checked every run, older ones about hourly, and we drop them after a day.
YOUNG_FOR = timedelta(hours=2)
TRACK_FOR = timedelta(hours=24)
# 55, not 60, so a few seconds of drift can't bump a check to the next run.
OLDER_EVERY = timedelta(minutes=55)
# Stop starting new fetches after 4 minutes, so a slow run ends before the next cron run.
RUN_DEADLINE_SECONDS = 240


def poll_slot(now: datetime) -> datetime:
    """Start of the 5-minute slot `now` falls in, e.g. 12:07:31 -> 12:05:00."""
    return now - timedelta(minutes=now.minute % 5, seconds=now.second, microseconds=now.microsecond)


def is_due(age: timedelta, since_last_check: timedelta) -> bool:
    if age >= TRACK_FOR:
        return False
    if age < YOUNG_FOR:
        return True
    return since_last_check >= OLDER_EVERY


def pick_stories_to_check(
    new_ids: list[int],
    recent: list[tuple[int, datetime | None, datetime]],
    now: datetime,
) -> list[int]:
    """New stories we haven't seen yet, plus tracked ones that are due."""
    seen = {hn_id for hn_id, _, _ in recent}
    unseen = [hn_id for hn_id in new_ids if hn_id not in seen]
    # No posted time means HN answered null, usually for a deleted story. Seen, but never due.
    due = [
        hn_id
        for hn_id, posted_at, last_checked_at in recent
        if posted_at is not None and is_due(now - posted_at, now - last_checked_at)
    ]
    return unseen + due


def run_once(session: requests.Session, conn) -> int:
    """One collector run. Returns how many stories got saved."""
    # A slow run can still be going when cron starts the next one. Only one at a time.
    if not try_lock(conn):
        logger.warning("another run is still going, skipping this slot")
        return 0
    try:
        return _collect(session, conn)
    finally:
        unlock(conn)


def _collect(session: requests.Session, conn) -> int:
    started = time.monotonic()
    now = datetime.now(timezone.utc)
    slot = poll_slot(now)
    # Logged up front, so a run that crashes partway still shows up (with no finished_at).
    run_id = start_run(conn, slot)
    to_check = pick_stories_to_check(
        fetch_new_story_ids(session), get_recent_stories(conn, TRACK_FOR), now
    )
    saved = failed = nulls = 0
    for i, story_id in enumerate(to_check):
        if time.monotonic() - started > RUN_DEADLINE_SECONDS:
            logger.warning("out of time, leaving %d stories for the next run", len(to_check) - i)
            break
        try:
            item = fetch_item(session, story_id)
        except requests.RequestException:
            # Session already retried, so one bad story shouldn't end the run.
            logger.warning("item %s failed after retries, skipping", story_id)
            failed += 1
            continue
        if item is None:
            # Saving the null answer marks the story as seen, so we stop asking about it.
            insert_raw_snapshot(conn, story_id, None, slot)
            nulls += 1
            continue
        if insert_raw_snapshot(conn, story_id, item, slot):
            saved += 1
    finish_run(conn, run_id, due=len(to_check), saved=saved, failed=failed, nulls=nulls)
    logger.info(
        "slot %s: saved %d/%d stories (%d null) in %.1fs",
        slot.astimezone().strftime("%H:%M"),
        saved,
        len(to_check),
        nulls,
        time.monotonic() - started,
    )
    return saved


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
