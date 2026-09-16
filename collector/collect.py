"""Main collector script: grab new stories, work out which are due, save the raw JSON.

Each call does one run and exits. Cron runs it every 5 minutes:
    python -m collector.collect
"""

import logging
import time
from datetime import datetime, timedelta, timezone

import psycopg
import requests

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
# A late run can end just before the next slot starts. Without this gap, the next run
# would save the same readings a few seconds later.
MIN_GAP = timedelta(minutes=4)
# Stop starting new fetches 4 minutes into the slot. Even a slow last fetch then ends
# before the next slot starts, including late runs after the Mac wakes up.
RUN_WINDOW = timedelta(minutes=4)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def poll_slot(now: datetime) -> datetime:
    """Start of the 5-minute slot `now` falls in, e.g. 12:07:31 -> 12:05:00."""
    return now - timedelta(minutes=now.minute % 5, seconds=now.second, microseconds=now.microsecond)


def is_due(age: timedelta, since_last_check: timedelta) -> bool:
    if age >= TRACK_FOR or since_last_check < MIN_GAP:
        return False
    if age < YOUNG_FOR:
        return True
    return since_last_check >= OLDER_EVERY


def pick_stories_to_check(
    new_ids: list[int],
    recent: list[tuple[int, datetime | None, datetime, bool]],
    now: datetime,
) -> list[int]:
    """Stories to check this run, most time-sensitive first."""
    seen = {hn_id for hn_id, *_ in recent}
    unseen = [hn_id for hn_id in new_ids if hn_id not in seen]
    young, older = [], []
    for hn_id, posted_at, last_checked_at, deleted in recent:
        # A row with no usable posted time can't be aged, so it is never due.
        if deleted or posted_at is None:
            continue
        age = now - posted_at
        if not is_due(age, now - last_checked_at):
            continue
        if age < YOUNG_FOR:
            young.append(hn_id)
        else:
            older.append(hn_id)
    # If a run hits its time limit, whatever is at the end waits for the next run.
    return young + unseen + older


def run_once(session: requests.Session, conn: psycopg.Connection) -> int:
    """One collector run. Returns how many stories got saved."""
    # A slow run can still be going when cron starts the next one. Only one at a time.
    if not try_lock(conn):
        logger.warning("another run is still going, skipping this slot")
        return 0
    try:
        return _collect(session, conn)
    finally:
        unlock(conn)


def _collect(session: requests.Session, conn: psycopg.Connection) -> int:
    started = time.monotonic()
    now = utc_now()
    slot = poll_slot(now)
    deadline = slot + RUN_WINDOW
    # Logged up front, so a run that crashes partway still shows up (with no finished_at).
    run_id = start_run(conn, slot)
    to_check = pick_stories_to_check(
        fetch_new_story_ids(session), get_recent_stories(conn, TRACK_FOR), now
    )
    saved = failed = nulls = 0
    for i, story_id in enumerate(to_check):
        if utc_now() >= deadline:
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
            # Brand new stories often come back null for a few seconds. Try again next run.
            nulls += 1
            continue
        try:
            inserted = insert_raw_snapshot(conn, story_id, item, slot)
        except psycopg.DataError:
            # One story Postgres can't store (e.g. a null character) shouldn't end the run.
            conn.rollback()
            logger.warning("item %s could not be saved, skipping", story_id)
            failed += 1
            continue
        if inserted:
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
    conn = get_connection()
    try:
        run_once(make_session(), conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
