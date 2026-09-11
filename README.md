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
psql -d hn -f sql/001_create_raw_snapshots.sql
cp .env.example .env
```

## Run the collector
```
.venv/bin/python -m collector.collect --once   # single poll
.venv/bin/python -m collector.collect          # foreground loop
```

## Tests
```
.venv/bin/pytest
```
