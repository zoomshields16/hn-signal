# 0005: The story outcomes table

## What was decided
1. One row per story in `fct_story_outcomes`, rebuilt every run, holding the first hour and the outcome.
2. Score at one hour is the latest reading taken between minutes 50 and 60. Score at half an hour is the latest between minutes 20 and 30.
3. Momentum is the points gained per minute between those two readings.
4. A story is usable for modeling if it was first seen within 10 minutes of posting, has a score at one hour, was neither deleted nor dead, and its first day is over.
5. A story reached 100 if any reading showed 100 or more. Every usable story, hit or not, must have been watched for at least 20 hours.
6. Tests fail the build if a feature reading falls outside its window, or if a story marked usable breaks any of these rules.

## Why
The question is what can be predicted at the one hour mark, so every feature has to come from readings taken by then. Using a reading from minute 62 would be leakage, and the model would look better than it could ever be in practice. A reading from minute 30 labeled as one hour would be wrong the other way, so the window starts at minute 50. Since collection moved to Railway, every story caught early has a reading between minutes 50 and 60, usually around minute 57.

Readings land a few minutes apart from story to story, so momentum is a rate rather than a plain difference in points. That keeps a story read at minutes 30 and 50 comparable with one read at minutes 20 and 60.

Stories first seen hours after posting can't say how they started, so they are left out. Deleted and dead stories are left out too, because their run was ended by the author, a moderator or HN's filters, not by how readers voted.

A story's outcome is only known once its first day is over. Counting younger stories would add the ones that already reached 100 and leave out the ones still climbing, which would make hits look more common than they are. The same goes for watching time. An earlier version asked only misses to have been watched for 20 hours, and a review caught the problem: among stories whose collection stopped early, only the hits got in. Every story now has to meet the same rule.

## What was not done
1. Use the reading closest to minute 60. That reading can land after the hour.
2. Fill gaps by drawing a line between readings. It invents readings that were never taken.
3. Build the table incrementally. A story's numbers keep changing for a day, and the table is small enough to rebuild each run.
