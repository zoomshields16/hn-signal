-- How many stories HN answered with null in a run, so a run's numbers add up.
ALTER TABLE collector_runs ADD COLUMN IF NOT EXISTS stories_null INT;
