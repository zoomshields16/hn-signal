# hn-signal
Predicting Hacker News front-page performance from early engagement signals. Postgres, dbt, Python.

## Status
Work in progress. A collector runs every 5 minutes, follows each new story through
its first day, and saves the raw JSON in Postgres (`raw_snapshots`), with one row
per run in `collector_runs`. See `docs/decisions/` for why.

## Setup
```
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
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

## Run it on Railway
The real collection runs as a Railway cron job, so it never depends on a laptop being awake.
1. Add a Postgres database to a Railway project and run the files in `sql/` against it.
2. Add a service from this repo with start command `python -m collector.collect` and cron schedule `*/5 * * * *`.
3. Set the service's `DATABASE_URL` to the database's connection URL.

## Transformations (dbt)
The models in `dbt/` turn the raw JSON into staging tables. Connection settings come from
environment variables, so nothing sensitive is stored in the repo.

Against a local database:
```
export DBT_HOST=localhost DBT_PORT=5432 DBT_DBNAME=hn DBT_SCHEMA=dbt_dev
.venv/bin/dbt build --project-dir dbt --profiles-dir dbt
```
Against the hosted database, open a tunnel first and point dbt at it:
```
railway connect postgres --tunnel-only --port 15432
export DBT_HOST=localhost DBT_PORT=15432 DBT_DBNAME=railway DBT_USER=... DBT_PASSWORD=...
```
Builds go to the `dbt_dev` schema. Add `--target prod` to build the real tables in `analytics`.

## Tests
Tests use their own `hn_test` database, so they never touch collected data. The database
tests skip when no local Postgres is running, and CI always runs them.
```
createdb hn_test
.venv/bin/pytest
```
