# 0002: Ingestion

## What we decided
1. Poll the newest stories list instead of the top 100 list.
2. Check a story every run while it is under 2 hours old, then about once an hour until it is a day old, then stop.
3. Retry a failed request up to 3 times, and skip that story if it still fails.
4. Save at most one row per story per 5 minute slot.
5. Write one row per run to a collector_runs table.
6. Run the collector every 5 minutes with cron.

## Why
The first version used the top 100 list. A story only reaches that list once it is already doing well, so we missed the first hour of most stories and almost every story that flopped. Those are the two things this project needs to compare.

Checking by age keeps the request count reasonable. Checking every tracked story every run would be about 1,400 requests, and a score barely moves after the first couple of hours. With the age rules a run is about 230 requests and takes a few seconds.

Two runs can overlap, for example if cron starts while a manual run is going. Without a guard the same story gets saved twice seconds apart, which later looks like two real readings. The slot and the unique constraint stop that in the database, so it holds even if the Python is wrong. This already happened once and left 148 duplicate rows, which the sql/002 migration removed.

The laptop sleeps, so the collector stops with it. The run log makes that visible. A slot with no row means the collector was not running. A row with no finish time means that run crashed.

## What we did not do
1. Keep the top 100 list. It drops the stories we need to compare against.
2. Check every story every run. Six times the requests for data that barely changes.
3. Compare payloads in Python to find duplicates. The database can enforce it properly.
4. Use launchd instead of cron. The same cron line will work if this ever runs on a server.
