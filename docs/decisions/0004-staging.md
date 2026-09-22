# 0004: Staging models in dbt

## What we decided
1. Use dbt to turn the raw JSON into staging tables, instead of SQL scripts run by hand.
2. Start with two models: stg_snapshots, one row per reading, and stg_stories, one row per story.
3. Build them as views.
4. Keep connection settings in environment variables, with a dev target that writes to its own schema and a prod target for the real tables.
5. Run `dbt build` in CI, after creating the tables from `sql/`.

## Why
The raw table holds one JSON response per reading. Everything after this point needs real columns, and it needs the same definitions everywhere. dbt gives us one place for those definitions, works out what order to run things in, and tests the results.

Views suit staging here. A view is a saved query, so it always reflects the raw table, which changes every 5 minutes, and it costs no extra storage. If reading one ever gets slow, it can become a table later without changing anything that uses it.

Deleted stories come back without a title, so stg_stories takes the newest reading that still has one. Numbers are read only when the JSON really holds a number, because the raw table is stored exactly as the API sent it, and one odd value would otherwise break every run.

The dev target writes to its own schema, so nothing we try out touches the real tables. Building the real ones takes `--target prod`, which has to be asked for by name.

## What we did not do
1. Run SQL scripts in order by hand. That is the job dbt already does, with tests included.
2. Build staging as tables. Views are enough at this size and are never stale.
3. Load sample data in CI. CI proves the models compile and run; the data checks run against the real database.
