-- Raw landing table for the HN collector (ELT: load untouched, transform later).
-- hn_id is pulled out of the payload only so we can index/query by it; every
-- other field stays inside payload exactly as the API returned it.
CREATE TABLE IF NOT EXISTS raw_snapshots (
    id BIGSERIAL PRIMARY KEY,
    hn_id BIGINT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_snapshots_hn_id ON raw_snapshots (hn_id);

-- Every collector run looks up the last 24 hours of checks.
CREATE INDEX IF NOT EXISTS idx_raw_snapshots_fetched_at ON raw_snapshots (fetched_at);
