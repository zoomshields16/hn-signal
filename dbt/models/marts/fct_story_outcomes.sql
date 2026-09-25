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

-- Latest reading at or before the one-hour mark. Nothing after it is used, so nothing
-- from after the hour can leak into the features.
before_one_hour as (

    select
        story_id,
        age_minutes,
        score,
        comment_count,
        row_number() over (partition by story_id order by age_minutes desc) as recency
    from readings
    where age_minutes <= 60

),

before_half_hour as (

    select
        story_id,
        age_minutes,
        score,
        row_number() over (partition by story_id order by age_minutes desc) as recency
    from readings
    where age_minutes <= 30

),

-- Only counts as the one-hour score if it was taken at least 50 minutes in.
one_hour as (

    select story_id, age_minutes, score, comment_count
    from before_one_hour
    where recency = 1 and age_minutes >= 50

),

half_hour as (

    select story_id, score
    from before_half_hour
    where recency = 1 and age_minutes >= 20

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
    round(lifetime.first_reading_minutes, 1) as first_reading_minutes,
    round(one_hour.age_minutes, 1) as one_hour_reading_minutes,
    one_hour.score as score_at_1h,
    one_hour.comment_count as comments_at_1h,
    one_hour.score - half_hour.score as score_gain_last_30m,
    lifetime.peak_score,
    lifetime.peak_score >= 100 as reached_100,
    round(lifetime.last_reading_minutes / 60, 1) as hours_tracked,
    stories.deleted,
    coalesce(
        not stories.deleted
        -- Seen early enough to know how it started.
        and lifetime.first_reading_minutes <= 10
        and one_hour.score is not null
        -- Its first day is over...
        and stories.posted_at <= now() - interval '24 hours'
        -- ...and it either reached 100 or was watched long enough to be sure it didn't.
        and (lifetime.peak_score >= 100 or lifetime.last_reading_minutes >= 20 * 60),
        false
    ) as is_usable
from {{ ref('stg_stories') }} as stories
join lifetime on lifetime.story_id = stories.story_id
left join one_hour on one_hour.story_id = stories.story_id
left join half_hour on half_hour.story_id = stories.story_id
