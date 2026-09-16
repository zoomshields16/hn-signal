# 0002: Ingestion

## What we decided
1. Poll the newest stories list instead of the top 100 list.
2. Check a story every run while it is under 2 hours old, then about once an hour until it is a day old, then stop. Never check the same story twice within 4 minutes, and stop checking stories HN marks as deleted.
3. Retry server errors up to 3 times. Skip a story that still fails, that HN rate limits, that comes back null, or that Postgres can't store. The next run tries it again.
4. Save at most one row per story per 5 minute slot, and let only one run work at a time.
5. Stop starting new fetches 4 minutes into the slot, so a run is done before the next one starts.
6. Write one row per run to a collector_runs table.
7. Run the collector every 5 minutes with cron.

## Why
The first version used the top 100 list. A story only reaches that list once it is already doing well, so we missed the first hour of most stories and almost every story that flopped. Those are the two things this project needs to compare.

Checking by age keeps the request count reasonable. Checking every tracked story every run would be about 1,400 requests, and a score barely moves after the first couple of hours. With the age rules a normal run is a couple hundred requests and takes a few seconds.

Two readings of the same story a few seconds apart would later look like two real data points. That happened in two ways. Two runs overlapped, which left 148 duplicate rows that the sql/002 migration removed. And runs that started late, like right after the laptop woke up, finished just before the next slot, so the next run saved the same stories again. The lock stops the first case. The 4 minute gap and the time limit tied to the slot stop the second. Inside a single run, the unique constraint on story and slot stops repeats.

HN sometimes answers null for a story that is only seconds old, then returns it normally a few minutes later. So a null answer is skipped, not saved. Saving it would mark the story as seen and lose its first hour. Deleted stories come back as normal objects marked deleted, and those are the ones we stop checking.

The laptop sleeps, so the collector stops with it. The run log makes that visible. A slot with no row means the collector was not running, or an earlier run still had the lock. A row with no finish time means that run crashed.

## What we did not do
1. Keep the top 100 list. It drops the stories we need to compare against.
2. Check every story every run. Six times the requests for data that barely changes.
3. Compare payloads in Python to find duplicates. The database can enforce it properly.
4. Use launchd instead of cron. The same cron line will work if this ever runs on a server.
5. Keep a second way to run the collector in a loop. Cron is the only scheduler, and `python -m collector.collect` runs it once by hand.
