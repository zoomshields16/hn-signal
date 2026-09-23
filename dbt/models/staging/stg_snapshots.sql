{{
    config(
        materialized='incremental',
        indexes=[
            {'columns': ['story_id']},
            {'columns': ['fetched_at']},
        ],
    )
}}

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

{% if is_incremental() %}
    -- Raw ids only count up, and the collector is the only writer and commits one row at a
    -- time, so rows never show up out of order. Anything above the highest id here is new.
    where id > (select coalesce(max(snapshot_id), 0) from {{ this }})
{% endif %}
