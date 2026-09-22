-- One row per story, holding the parts that don't change while it is on the site.
-- Deleted stories come back without a title, so take the newest reading that still has one
-- and fall back to the newest reading of all.

with readings as (

    select
        hn_id as story_id,
        payload,
        fetched_at
    from {{ source('raw', 'raw_snapshots') }}

),

picked as (

    select
        story_id,
        payload,
        row_number() over (
            partition by story_id
            order by (payload ? 'title') desc, fetched_at desc
        ) as pick
    from readings

),

seen as (

    select
        story_id,
        min(fetched_at) as first_seen_at,
        max(fetched_at) as last_seen_at,
        bool_or(coalesce((payload ->> 'deleted')::boolean, false)) as deleted
    from readings
    group by story_id

)

select
    picked.story_id,
    picked.payload ->> 'title' as title,
    picked.payload ->> 'by' as author,
    picked.payload ->> 'url' as url,
    case
        when jsonb_typeof(picked.payload -> 'time') = 'number'
        then to_timestamp((picked.payload ->> 'time')::double precision)
    end as posted_at,
    seen.deleted,
    seen.first_seen_at,
    seen.last_seen_at
from picked
join seen on seen.story_id = picked.story_id
where picked.pick = 1
