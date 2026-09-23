# 0003: Run the collector on Railway

## What was decided
1. Run the collector as a Railway cron job every 5 minutes instead of cron on a laptop.
2. Keep the data in a Postgres database on Railway, and copy over everything collected so far.
3. Deploy from main, so merging a PR is what ships a change.

## Why
On the laptop, collection only covered 6 to 25 percent of each day. The laptop slept, the Wi-Fi dropped, and macOS blocked some runs even with Full Disk Access. After 11 days that left 1,110 stories with a usable first hour, and only 38 of them reached 100 points. That is too few to say much about what predicts a hit.

A server that never sleeps catches every new story, which should mean roughly ten times as many usable stories per day.

Railway fits the code as it is. Its cron jobs can run as often as every 5 minutes, which is our schedule. They run on UTC like our slots, and each run has to exit when it is done, which the collector already does. If a run is still going when the next one is due, Railway skips the new one, and our lock covers the same case.

## What was not done
1. Keep collecting on the laptop. It works, but the gaps cost too much data.
2. Use a railway.json file for the settings. Railway has deprecated it, so the start command and schedule live in the service settings and in the README.
3. Pick a different host. Railway was already set up from another project.
