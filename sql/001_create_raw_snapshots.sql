-- Raw landing table: API responses stored as-is. Cleanup happens later in SQL (ELT).
-- hn_id is copied out of the payload just so we can index it.
CREATE TABLE IF NOT EXISTS raw_snapshots (
    id BIGSERIAL PRIMARY KEY,
    hn_id BIGINT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_snapshots_hn_id ON raw_snapshots (hn_id);
