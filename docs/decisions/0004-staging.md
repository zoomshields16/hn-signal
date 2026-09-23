# 0004: Staging models in dbt

## What was decided
1. Use dbt to turn the raw JSON into staging tables, instead of SQL scripts run by hand.
2. Two models: stg_snapshots, one row per reading, and stg_stories, one row per story.
3. Store both as tables with indexes. stg_snapshots is incremental, so each run only adds new readings. stg_stories is rebuilt each run.
4. Keep connection settings in environment variables. The dev target writes everything to one schema, and prod writes staging models to a `staging` schema.
5. Run `dbt build` on Railway every 15 minutes, and in CI after creating the tables from `sql/`.

## Why
The raw table holds one JSON response per reading. Everything after this point needs real columns and the same definitions everywhere. dbt keeps those definitions in one place, works out the order to run them, and tests the results.

The models started as views. A view is never stale, but it stores nothing, so every query has to unpack the JSON again for every row. The analysis in the next branch reads these tables constantly, so they are stored instead. stg_snapshots grows by tens of thousands of rows a day, so rebuilding it on every run would waste time. The incremental model only adds rows with a raw id above the highest one it already has, which is safe because the collector is the only writer and commits rows in order. stg_stories is small, so a full rebuild is simpler.

The indexes cover the lookups the analysis will do. Finding one story's readings took 0.27 ms with the index and 6 ms without it, because without it Postgres read all 150,140 rows to find 46. That gap grows with the table.

Stored tables go stale until dbt runs again, so dbt runs on Railway next to the collector. The dev target writes to its own schema, so trying something out never touches the real tables.

Deleted stories come back without a title, so stg_stories takes the newest reading that still has one. Numbers are read only when the JSON really holds a number, because the raw table is stored exactly as the API sent it and one odd value would otherwise break every run.

## What was not done
1. Run SQL scripts in order by hand. That is the job dbt already does, with tests included.
2. Keep the models as views. Simpler, but too slow for the analysis once the table grows.
3. Load sample data in CI. CI proves the models compile and run, and the data checks run against the real database.
