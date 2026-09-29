# 0006: The prediction model

## What was decided
1. Logistic regression on three first hour features: score at one hour, comments at one hour, and momentum. Score and comments are log scaled.
2. The newest 25% of usable stories test the model. The older ones train it, except the last day before the test stories, whose outcomes weren't known yet.
3. The model is compared against the simple rule "flag a story with N or more points at one hour". Both cutoffs are chosen on the training stories. The model's comes from predictions on stories left out of each fit, so it isn't tuned to stories the model has already seen.
4. Results are judged by precision, recall and average precision, not accuracy.
5. The script lives in `analysis/`, and its libraries are in the dev requirements only.
6. Published results use a cutoff on posting date, so a rerun gives the same numbers.

## Why
Only about 3.5% of stories reach 100 points. A model that says "no" every time is 96.5% accurate and useless, so accuracy says nothing here. Precision is how often a flag was right, and recall is how many of the hits got flagged. Average precision sums up the whole trade off between the two in one number.

A random split would let the model train on stories posted after the ones it is tested on. Splitting by time matches real use, where the model only ever knows the past. A story's outcome takes a day to settle, so a story posted just before the test stories would carry an answer from the test period. Leaving out that last day keeps the split honest. It costs about 950 stories, since about 1,000 usable stories come in each day.

Logistic regression gives a probability, is quick to fit, and its weights can be read. The simple rule is the bar to clear. If a model can't beat "lots of points early", it isn't worth having.

Time of day and day of the week were tried on the training stories and made the model worse, so they were dropped. Log scaling stops a few stories with hundreds of points from drowning out the rest. About 2% of stories have no reading at half an hour, so their momentum is filled with the typical value from the training stories.

A story only counts as usable once its first day is over, so every rebuild of the outcomes table adds a few more. The first run, a day earlier, gave slightly different numbers (72% and 68% precision) for that reason. A cutoff on posting date fixes the set of stories, so a rerun gives the same result.

## Result
Run on 2026-09-29 with `--posted-before 2026-09-28`. The model trained on 3,341 stories posted Sep 11 to Sep 25, with 117 hits. It was tested on 1,430 stories posted Sep 26 and 27, with 47 hits.

| | Precision | Recall | Average precision |
|---|---|---|---|
| Rule: 15+ points at one hour | 66% | 45% | 0.50 |
| Model: 22%+ chance of reaching 100 | 70% | 49% | 0.55 |

The model is a modest step up from the rule. At the chosen cutoffs it catches two more hits (23 vs 21) with one fewer false alarm, and it is more precise at most recall levels. With only 47 hits in the test set, one or two stories can move these numbers by a few points.

Comments get a negative weight. For two stories with the same score, the one with more comments is less likely to reach 100, maybe because it is drawing debate rather than upvotes.

## What was not done
1. A bigger model like a random forest. With a few thousand stories and three features, the gain would be small and the model harder to explain.
2. Class weights. Choosing the cutoff already deals with the rare hits, and without weights the output stays a real probability.
3. Running the model on a schedule. The question is whether the first hour predicts takeoff, not live alerts.
