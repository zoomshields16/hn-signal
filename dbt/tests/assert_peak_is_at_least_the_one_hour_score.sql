-- The peak is the highest score ever seen, so it can't be below the score at one hour.
select story_id, score_at_1h, peak_score
from {{ ref('fct_story_outcomes') }}
where peak_score < score_at_1h
