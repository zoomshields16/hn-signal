-- A usable story has to pass every rule in docs/decisions/0005-analytics.md.
-- Any row returned here fails the test.
select story_id
from {{ ref('fct_story_outcomes') }}
where is_usable
    and (
        deleted
        or dead
        or first_reading_minutes > 10
        or score_at_1h is null
        or age_at_last_reading_hours < 20
        or posted_at > now() - interval '24 hours'
    )
