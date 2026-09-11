# 0001: Store the raw JSON

## What we decided
1. The collector saves the full JSON response for each story, exactly as the API returns it, in one table called raw_snapshots.
2. Nothing is parsed or cleaned while collecting. The only field copied out of the JSON is the story id, so the table can be indexed by it.

## Why
The HN API only gives a story's score right now. There is no way to ask what it was an hour ago. If we miss a reading, or drop a field while saving, that data is gone for good.

Saving the whole response removes that risk. Anything we want later, such as the comment count, is already sitting in the table, and the queries that clean the data can be rewritten as often as we need without collecting again.

This is ELT: extract, load, then transform. ETL does the transform first, which would mean deciding up front which fields matter.

## What we did not do
1. Parse the JSON into columns while collecting. One mistake there loses a field for every story already saved.
2. Only save stories above a certain score. The stories that never take off are half of the comparison this project is built on.

## What comes later
Turning the raw JSON into tidy tables and one summary row per story, using dbt.
