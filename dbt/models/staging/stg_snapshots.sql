{{
    config(
        materialized='incremental',
        unique_key='snapshot_id',
        on_schema_change='fail',
        indexes=[
            {'columns': ['snapshot_id'], 'unique': True},
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
    -- Re-check the last hour and let unique_key merge the overlap, so a reading that
    -- commits late or gets written twice still ends up here exactly once.
    where fetched_at > coalesce(
        (select max(fetched_at) from {{ this }}), '1970-01-01'::timestamptz
    ) - interval '1 hour'
{% endif %}
