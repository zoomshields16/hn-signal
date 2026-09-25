-- Each feature reading must come from its own window: minutes 50 to 60 for the one-hour
-- features, and 20 to 30 for the half hour. Anything past minute 60 would be leakage.
-- Any row returned here fails the test.
select story_id, one_hour_reading_minutes, half_hour_reading_minutes
from {{ ref('fct_story_outcomes') }}
where one_hour_reading_minutes not between 50 and 60
    or half_hour_reading_minutes not between 20 and 30
