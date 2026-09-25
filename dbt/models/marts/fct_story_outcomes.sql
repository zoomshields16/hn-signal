-- One row per story: how it did in its first hour, and whether it went on to reach 100 points.
-- is_usable marks the stories fit for modeling. See docs/decisions/0005-analytics.md.

with readings as (

    select
        snapshots.story_id,
        snapshots.score,
        snapshots.comment_count,
        extract(epoch from snapshots.fetched_at - stories.posted_at) / 60 as age_minutes
    from {{ ref('stg_snapshots') }} as snapshots
    join {{ ref('stg_stories') }} as stories on stories.story_id = snapshots.story_id
    where stories.posted_at is not null

),

-- The latest reading with a score in each window. The one-hour window stops at minute 60,
-- so nothing from after the hour can leak into the features.
windowed as (

    select
        story_id,
        age_minutes,
        score,
        comment_count,
        case
            when age_minutes between 50 and 60 then 'one_hour'
            when age_minutes between 20 and 30 then 'half_hour'
        end as window_name
    from readings
    where score is not null

),

latest_in_window as (

    select
        *,
        row_number() over (
            partition by story_id, window_name
            order by age_minutes desc
        ) as recency
    from windowed
    where window_name is not null

),

one_hour as (

    select story_id, age_minutes, score, comment_count
    from latest_in_window
    where window_name = 'one_hour' and recency = 1

),

half_hour as (

    select story_id, age_minutes, score
    from latest_in_window
    where window_name = 'half_hour' and recency = 1

),

lifetime as (

    select
        story_id,
        min(age_minutes) as first_reading_minutes,
        max(age_minutes) as last_reading_minutes,
        max(score) as peak_score
    from readings
    group by story_id

)

select
    stories.story_id,
    stories.title,
    stories.posted_at,
    extract(hour from stories.posted_at at time zone 'UTC')::int as posted_hour_utc,
    extract(isodow from stories.posted_at at time zone 'UTC')::int as posted_weekday,
    lifetime.first_reading_minutes,
    one_hour.age_minutes as one_hour_reading_minutes,
    half_hour.age_minutes as half_hour_reading_minutes,
    one_hour.score as score_at_1h,
    one_hour.comment_count as comments_at_1h,
    half_hour.score as score_at_30m,
    -- A rate, so stories whose readings landed a few minutes apart can still be compared.
    round(
        (one_hour.score - half_hour.score) / (one_hour.age_minutes - half_hour.age_minutes), 3
    ) as points_per_minute_30_to_60,
    lifetime.peak_score,
    lifetime.peak_score >= 100 as reached_100,
    round(lifetime.last_reading_minutes / 60, 1) as age_at_last_reading_hours,
    stories.deleted,
    stories.dead,
    coalesce(
        not stories.deleted
        and not stories.dead
        -- Seen early enough to know how it started.
        and lifetime.first_reading_minutes <= 10
        and one_hour.score is not null
        -- Its first day is over and it was watched through most of it. Hits and misses get
        -- the same rule, so a gap in collection can't make hits look more common.
        and stories.posted_at <= now() - interval '24 hours'
        and lifetime.last_reading_minutes >= 20 * 60,
        false
    ) as is_usable
from {{ ref('stg_stories') }} as stories
join lifetime on lifetime.story_id = stories.story_id
left join one_hour on one_hour.story_id = stories.story_id
left join half_hour on half_hour.story_id = stories.story_id
