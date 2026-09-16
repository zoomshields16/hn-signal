# 0002: Ingestion

## What we decided
1. Poll the newest stories list instead of the top 100 list.
2. Check a story every run while it is under 2 hours old, then about once an hour until it is a day old, then stop.
3. Retry server errors up to 3 times, and skip a story that still fails or that HN rate limits.
4. Save at most one row per story per 5 minute slot, and let only one run work at a time.
5. Stop a run from starting new fetches after 4 minutes, so it always ends before the next one.
6. When HN answers null for a story, save that answer, so the story is not fetched again every run.
7. Write one row per run to a collector_runs table.
8. Run the collector every 5 minutes with cron.

## Why
The first version used the top 100 list. A story only reaches that list once it is already doing well, so we missed the first hour of most stories and almost every story that flopped. Those are the two things this project needs to compare.

Checking by age keeps the request count reasonable. Checking every tracked story every run would be about 1,400 requests, and a score barely moves after the first couple of hours. With the age rules a run is about 230 requests and takes a few seconds.

Two runs can overlap, for example if cron starts while a slow run is still going. Without a guard the same story gets saved twice seconds apart, which later looks like two real readings. A run now takes a lock in Postgres before it does anything, so the second run skips its slot instead of racing. Inside a single run, the unique constraint on story and slot stops repeats. This already happened once and left 148 duplicate rows, which the sql/002 migration removed.

The laptop sleeps, so the collector stops with it. The run log makes that visible. A slot with no row means the collector was not running, or an earlier run still had the lock. A row with no finish time means that run crashed.

## What we did not do
1. Keep the top 100 list. It drops the stories we need to compare against.
2. Check every story every run. Six times the requests for data that barely changes.
3. Compare payloads in Python to find duplicates. The database can enforce it properly.
4. Use launchd instead of cron. The same cron line will work if this ever runs on a server.
