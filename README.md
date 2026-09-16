# hn-signal
Predicting Hacker News front-page performance from early engagement signals. Postgres, dbt, Python.

## Status
Work in progress. Currently: a collector polls the HN API and lands raw story
JSON in Postgres (`raw_snapshots`). See `docs/decisions/` for why.

## Setup
```
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
createdb hn
for f in sql/*.sql; do psql -v ON_ERROR_STOP=1 -d hn -f "$f" || break; done
cp .env.example .env
```

## Run the collector
```
.venv/bin/python -m collector.collect   # one run
```

## Schedule it (every 5 minutes)
```
mkdir -p logs
crontab -l 2>/dev/null | grep -q collector.collect || \
  (crontab -l 2>/dev/null; echo "*/5 * * * * cd '$(pwd)' && .venv/bin/python -m collector.collect >> logs/collector.log 2>&1") | crontab -
```
Only runs while the machine is awake. On macOS, cron may need Full Disk Access if the repo is in Documents.

## Tests
Tests use their own `hn_test` database, so they never touch collected data.
```
createdb hn_test
.venv/bin/pytest
```
