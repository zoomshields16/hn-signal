"""Model helper tests. Small made-up tables, no database."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from analysis.model import (
    best_threshold, make_features, precision_and_recall, time_split, utc_date,
)


def _stories(**columns):
    return pd.DataFrame(columns)


def test_time_split_trains_on_older_stories():
    stories = _stories(
        story_id=[1, 2, 3, 4],
        posted_at=pd.to_datetime(["2026-09-04", "2026-09-01", "2026-09-03", "2026-09-02"]),
    )

    train, test = time_split(stories, test_share=0.25)

    assert list(train["story_id"]) == [2, 4, 3]
    assert list(test["story_id"]) == [1]


def test_time_split_leaves_out_stories_still_settling_when_testing_starts():
    stories = _stories(
        story_id=[1, 2, 3, 4],
        posted_at=pd.to_datetime(
            ["2026-09-01 00:00", "2026-09-02 00:00", "2026-09-02 12:00", "2026-09-03 00:00"]
        ),
    )

    train, test = time_split(stories, test_share=0.25)

    assert list(train["story_id"]) == [1, 2]
    assert list(test["story_id"]) == [4]


def test_make_features_logs_counts_and_fills_gaps():
    stories = _stories(
        score_at_1h=[0, 9], comments_at_1h=[None, 0], points_per_minute_30_to_60=[0.5, None],
    )

    features = make_features(stories, momentum_fill=0.1)

    assert list(features["log_score_at_1h"]) == [0.0, np.log(10)]
    assert list(features["log_comments_at_1h"]) == [0.0, 0.0]
    assert list(features["points_per_minute_30_to_60"]) == [0.5, 0.1]


def test_make_features_never_uses_the_outcome():
    stories = _stories(
        score_at_1h=[1], comments_at_1h=[0], points_per_minute_30_to_60=[0.0],
        peak_score=[500], reached_100=[True],
    )

    features = make_features(stories, momentum_fill=0.0)

    assert not {"peak_score", "reached_100"} & set(features.columns)


def test_best_threshold_finds_the_clean_cut():
    y_true = pd.Series([False, False, True, True])

    assert best_threshold(y_true, np.array([1, 2, 30, 40])) == 30


def test_precision_and_recall():
    y_true = pd.Series([True, True, False, False])
    flagged = np.array([True, False, True, False])

    assert precision_and_recall(y_true, flagged) == (0.5, 0.5)


def test_precision_is_zero_when_nothing_is_flagged():
    y_true = pd.Series([True, False])

    assert precision_and_recall(y_true, np.array([False, False])) == (0.0, 0.0)


def test_utc_date_is_midnight_utc():
    assert utc_date("2026-09-28") == datetime(2026, 9, 28, tzinfo=timezone.utc)
