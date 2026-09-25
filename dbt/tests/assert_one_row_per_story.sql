-- The outcomes table promises one row for every story in staging, usable or not.
-- Any row returned here fails the test.
select outcomes.total as outcome_rows, stories.total as story_rows
from (select count(*) as total from {{ ref('fct_story_outcomes') }}) as outcomes
cross join (select count(*) as total from {{ ref('stg_stories') }}) as stories
where outcomes.total != stories.total
