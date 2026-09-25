# 0005: The story outcomes table

## What was decided
1. One row per story in `fct_story_outcomes`, rebuilt every run, holding the first hour and the outcome.
2. Score at one hour is the last reading at or before minute 60, and it only counts if it was taken at least 50 minutes in.
3. A story is usable for modeling if it was first seen within 10 minutes of posting, has a score at one hour, was not deleted, and its first day is over.
4. A story reached 100 if any reading showed 100 or more. A story that never did only counts if it was watched for at least 20 hours.
5. Tests fail the build if a one-hour feature ever uses a reading from outside minutes 50 to 60.

## Why
The question is what can be predicted at the one hour mark, so every feature has to come from readings taken by then. Using a reading from minute 62 would be leakage, and the model would look better than it could ever be in practice. A reading from minute 30 labeled as one hour would be wrong the other way, so readings before minute 50 don't count. Since collection moved to Railway, every story caught early has a reading between minutes 50 and 60, usually around minute 57.

Stories first seen hours after posting can't say how they started, so they are left out.

A story's outcome is only known once its first day is over. Counting younger stories would add the ones that already reached 100 and leave out the ones still climbing, which would make hits look more common than they are. Reaching 100 is certain the moment a reading shows it. Not reaching it needs the story to have been watched through most of its day, because the laptop's gaps could have hidden a late climb.

## What was not done
1. Use the reading closest to minute 60. That reading can land after the hour.
2. Fill gaps by drawing a line between readings. It invents readings that were never taken.
3. Build the table incrementally. A story's numbers keep changing for a day, and the table is small enough to rebuild each run.
