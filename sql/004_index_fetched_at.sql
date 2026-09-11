-- The collector reads the last 24 hours of checks on every run.
CREATE INDEX IF NOT EXISTS idx_raw_snapshots_fetched_at ON raw_snapshots (fetched_at);
