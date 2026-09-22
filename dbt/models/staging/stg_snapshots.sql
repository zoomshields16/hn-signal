-- One row per reading, with the JSON unpacked into columns.
-- Numbers are read as numeric, so a fraction or an oversized value can't break the run.

select
    id as snapshot_id,
    hn_id as story_id,
    poll_slot,
    fetched_at,
    case
        when jsonb_typeof(payload -> 'score') = 'number' then (payload ->> 'score')::numeric
    end as score,
    case
        when jsonb_typeof(payload -> 'descendants') = 'number'
        then (payload ->> 'descendants')::numeric
    end as comment_count
from {{ source('raw', 'raw_snapshots') }}
