-- The one-hour features may only use a reading taken between minute 50 and minute 60.
-- Anything later would be leakage. Any row returned here fails the test.
select story_id, one_hour_reading_minutes
from {{ ref('fct_story_outcomes') }}
where one_hour_reading_minutes > 60 or one_hour_reading_minutes < 50
