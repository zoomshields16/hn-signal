# 0001: Collector lands raw JSON, unmodified (ELT)

## Decision
The collector polls the HN API's `topstories.json` and `item/{id}.json` endpoints
and inserts each item's full JSON response into a single `raw_snapshots` table
(`hn_id`, `fetched_at`, `payload jsonb`). No parsing or column extraction happens
at collection time.

## Why
The HN API only exposes a story's *current* score — there's no endpoint to fetch
its score history after the fact. If a poll is missed or a field is dropped
during collection, that data point is gone forever. So the safest move is to
capture the full raw response every time and defer all interpretation
(normalizing into `stories`/`snapshots` tables, computing velocity, etc.) to SQL
transforms that run against the accumulated raw data. That's ELT (Extract, Load,
Transform) rather than ETL (Extract, Transform, Load): loading happens before
any transformation, so transforms can be rewritten or fixed later without
re-collecting.

## Alternatives considered
- **Parse into typed columns at collection time (ETL).** Rejected: any bug or
  scope miss in the parsing logic permanently loses that field for stories
  already polled, since there's no re-fetch.
- **Only store items that already have a score above some threshold.** Rejected:
  the whole point of the project is comparing early scores to outcomes, so
  low-scoring/failed stories are exactly the negative examples the mart needs.

## Not done yet (later branches)
- Idempotent inserts / de-duplication and cron/launchd scheduling — hours 4-5.
- Normalized `stories`/`snapshots` schema and indexes — hours 6-7.
- Handling collector downtime (Mac sleep) as visible gaps rather than hiding
  them — will show up naturally once snapshots are analyzed, since the
  `fetched_at` timestamps directly reveal any missed polling intervals.
