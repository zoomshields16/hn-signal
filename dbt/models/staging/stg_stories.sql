-- One row per story, holding the parts that don't change while it is on the site.
-- Deleted stories come back without a title, so take the newest reading that still has one
-- and fall back to the newest reading of all.

with picked as (

    select
        hn_id as story_id,
        payload,
        row_number() over (
            partition by hn_id
            order by (payload ? 'title') desc, fetched_at desc, id desc
        ) as pick
    from {{ source('raw', 'raw_snapshots') }}

),

per_story as (

    select
        hn_id as story_id,
        min(fetched_at) as first_seen_at,
        max(fetched_at) as last_seen_at,
        coalesce(bool_or(payload ->> 'deleted' = 'true'), false) as deleted,
        -- The posted time never changes, so take it from any reading that has a sane one.
        -- 4102444800 is the year 2100, which rules out nonsense far-future values.
        max(
            case
                when jsonb_typeof(payload -> 'time') = 'number'
                    and (payload ->> 'time')::numeric between 0 and 4102444800
                then to_timestamp((payload ->> 'time')::double precision)
            end
        ) as posted_at
    from {{ source('raw', 'raw_snapshots') }}
    group by hn_id

)

select
    per_story.story_id,
    picked.payload ->> 'title' as title,
    picked.payload ->> 'by' as author,
    picked.payload ->> 'url' as url,
    per_story.posted_at,
    per_story.deleted,
    per_story.first_seen_at,
    per_story.last_seen_at
from per_story
join picked on picked.story_id = per_story.story_id and picked.pick = 1
