-- One row per story per 5-minute slot, so a rerun can't save the same reading twice.
-- Safe to re-run: every step is a no-op once it has been applied.
ALTER TABLE raw_snapshots ADD COLUMN IF NOT EXISTS poll_slot TIMESTAMPTZ;

-- Backfill rows saved before this column existed.
UPDATE raw_snapshots
SET poll_slot = date_bin('5 minutes', fetched_at, TIMESTAMPTZ '2000-01-01 00:00+00')
WHERE poll_slot IS NULL;

-- Drop existing repeats, keeping the first reading in each slot.
DELETE FROM raw_snapshots a
USING raw_snapshots b
WHERE a.hn_id = b.hn_id
  AND a.poll_slot = b.poll_slot
  AND a.id > b.id;

ALTER TABLE raw_snapshots ALTER COLUMN poll_slot SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_snapshots_hn_id_poll_slot
    ON raw_snapshots (hn_id, poll_slot);
