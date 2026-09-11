"""Polls the HN API and lands raw item JSON into Postgres.

Usage:
    python -m collector.collect --once   # single poll, exits (for cron/launchd)
    python -m collector.collect          # foreground loop, polls every POLL_INTERVAL_SECONDS
"""

import argparse
import logging
import time

import requests

from collector.config import POLL_INTERVAL_SECONDS, TOP_N
from collector.db import get_connection, insert_raw_snapshot
from collector.hn_api import fetch_item, fetch_top_story_ids

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run_once(session: requests.Session, conn) -> int:
    """Fetches the current top stories and inserts one raw snapshot row per story.

    Returns the number of stories successfully snapshotted.
    """
    story_ids = fetch_top_story_ids(session, TOP_N)
    count = 0
    for story_id in story_ids:
        item = fetch_item(session, story_id)
        if item is None:
            logger.warning("item %s returned null (deleted/dead), skipping", story_id)
            continue
        insert_raw_snapshot(conn, story_id, item)
        count += 1
    logger.info("snapshotted %d/%d top stories", count, len(story_ids))
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="poll a single time and exit")
    args = parser.parse_args()

    session = requests.Session()
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
