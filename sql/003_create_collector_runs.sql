-- One row per collector run. A missing slot means the collector wasn't running
-- (e.g. the Mac was asleep); a row with no finished_at means the run crashed.
CREATE TABLE IF NOT EXISTS collector_runs (
    id BIGSERIAL PRIMARY KEY,
    poll_slot TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    stories_due INT,
    stories_saved INT,
    stories_failed INT
);
