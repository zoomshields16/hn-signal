"""Can a story's first hour predict whether it reaches 100 points? Fits the model and saves the chart."""

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter
from psycopg import sql
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve
from sklearn.model_selection import cross_val_predict
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from collector.config import DATABASE_URL

# Time of day and day of the week were tried too and made the model worse, so they're left out.
FEATURES = ["log_score_at_1h", "log_comments_at_1h", "points_per_minute_30_to_60"]
TEST_SHARE = 0.25
# A story's outcome takes a day to settle, so training stops a day before testing starts.
LABEL_DELAY = pd.Timedelta(hours=24)
REPO_ROOT = Path(__file__).resolve().parents[1]
CHART_PATH = REPO_ROOT / "docs" / "images" / "precision_recall.png"


def load_stories(conn: psycopg.Connection, schema: str) -> pd.DataFrame:
    """Usable stories, with only the columns the model needs."""
    query = sql.SQL(
        "select story_id, posted_at, score_at_1h, comments_at_1h, points_per_minute_30_to_60,"
        " reached_100 from {}.fct_story_outcomes where is_usable"
    ).format(sql.Identifier(schema))
    with conn.cursor() as cur:
        cur.execute(query)
        return pd.DataFrame(cur.fetchall(), columns=[col.name for col in cur.description])


def time_split(stories: pd.DataFrame, test_share: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Older stories train, newer stories test, the way the model would be used for real."""
    stories = stories.sort_values(["posted_at", "story_id"], kind="stable")
    cut = int(len(stories) * (1 - test_share))
    train, test = stories.iloc[:cut], stories.iloc[cut:]
    # Stories whose outcome wasn't known yet when the test stories were posted are left out.
    train = train[train["posted_at"] <= test["posted_at"].iloc[0] - LABEL_DELAY]
    return train, test


def make_features(stories: pd.DataFrame, momentum_fill: float) -> pd.DataFrame:
    """Model inputs. Nothing here comes from after the first hour."""
    # A few stories have hundreds of points, so logs keep them from drowning out the rest.
    return pd.DataFrame({
        "log_score_at_1h": np.log1p(stories["score_at_1h"].astype(float)),
        # A missing comment count is treated as no comments.
        "log_comments_at_1h": np.log1p(stories["comments_at_1h"].astype(float).fillna(0)),
        # About 2% of stories had no reading at half an hour, so they get a typical value.
        "points_per_minute_30_to_60":
            stories["points_per_minute_30_to_60"].astype(float).fillna(momentum_fill),
    }, index=stories.index)[FEATURES]


def best_threshold(y_true: pd.Series, scores: np.ndarray) -> float:
    """The cutoff with the best balance of precision and recall (F1)."""
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    # The last precision/recall pair has no threshold, so it's dropped.
    precision, recall = precision[:-1], recall[:-1]
    f1 = np.divide(
        2 * precision * recall, precision + recall,
        out=np.zeros_like(precision), where=(precision + recall) > 0,
    )
    return float(thresholds[np.argmax(f1)])


def precision_and_recall(y_true: pd.Series, flagged: np.ndarray) -> tuple[float, float]:
    caught = int((flagged & y_true).sum())
    precision = caught / flagged.sum() if flagged.sum() else 0.0
    return precision, caught / y_true.sum()


def make_model() -> Pipeline:
    # No class weights: the cutoff handles the rare hits, and the output stays a real probability.
    return make_pipeline(StandardScaler(), LogisticRegression())


def save_chart(y_test: pd.Series, rule_scores: np.ndarray, model_scores: np.ndarray) -> None:
    """Precision against recall on the test stories, for the rule and the model."""
    ink, muted, grid, surface = "#0b0b0b", "#52514e", "#e1e0d9", "#fcfcfb"
    fig = Figure(figsize=(7, 4.5), dpi=200, facecolor=surface)
    ax = fig.subplots()
    ax.set_facecolor(surface)

    for scores, color, label in [
        (model_scores, "#2a78d6", "Model"),
        (rule_scores, "#eb6834", "Score at 1h only"),
    ]:
        precision, recall, _ = precision_recall_curve(y_test, scores)
        ax.plot(recall, precision, drawstyle="steps-post", color=color, linewidth=2, label=label)

    base_rate = y_test.mean()
    ax.axhline(base_rate, color=muted, linewidth=1, linestyle="--")
    ax.text(0.01, base_rate + 0.02, f"Guessing: {base_rate:.0%}", color=muted, fontsize=9)

    ax.set_title("Catching hits on the newest stories", color=ink, fontsize=11, loc="left")
    ax.set_xlabel("Recall (share of hits caught)", color=muted)
    ax.set_ylabel("Precision (share of flags that were hits)", color=muted)
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.grid(color=grid, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=muted)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(grid)
    ax.legend(frameon=False, labelcolor=ink, loc="upper right")

    fig.tight_layout()
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, facecolor=surface)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", default="analytics", help="where dbt built fct_story_outcomes")
    args = parser.parse_args()
    started = time.monotonic()

    with psycopg.connect(DATABASE_URL) as conn:
        stories = load_stories(conn, args.schema)
    train, test = time_split(stories, TEST_SHARE)
    y_train, y_test = train["reached_100"].astype(bool), test["reached_100"].astype(bool)
    if not y_train.any() or not y_test.any():
        raise SystemExit("Not enough hits yet to train and test. Let the collector run longer.")

    # Everything learned (the fill value, the scaling, both cutoffs) comes from the older stories.
    momentum_fill = float(train["points_per_minute_30_to_60"].astype(float).median())
    x_train, x_test = make_features(train, momentum_fill), make_features(test, momentum_fill)
    model = make_model().fit(x_train, y_train)

    rule_cutoff = best_threshold(y_train, train["score_at_1h"].astype(float))
    # A cutoff picked on stories the model was fit on would flatter it, so this one comes from
    # predictions for stories each fit left out.
    held_out = cross_val_predict(make_model(), x_train, y_train, cv=5, method="predict_proba")
    model_cutoff = best_threshold(y_train, held_out[:, 1])

    rule_scores = test["score_at_1h"].astype(float).to_numpy()
    model_scores = model.predict_proba(x_test)[:, 1]
    rule_point = precision_and_recall(y_test, rule_scores >= rule_cutoff)
    model_point = precision_and_recall(y_test, model_scores >= model_cutoff)

    for name, part, y in [("Train", train, y_train), ("Test", test, y_test)]:
        print(f"{name}: {len(part):,} stories, {y.sum()} hits, "
              f"{part['posted_at'].min():%b %d} to {part['posted_at'].max():%b %d}")
    print(f"\n{'':32}{'precision':>10}{'recall':>8}{'avg precision':>15}")
    for name, point, scores in [
        (f"Rule: {rule_cutoff:.0f}+ points at 1h", rule_point, rule_scores),
        (f"Model: {model_cutoff:.0%}+ chance", model_point, model_scores),
    ]:
        print(f"{name:32}{point[0]:>10.0%}{point[1]:>8.0%}"
              f"{average_precision_score(y_test, scores):>15.2f}")

    # Scaled inputs, so the sizes can be compared with each other.
    weights = model.named_steps["logisticregression"].coef_[0]
    print("\nWeights: " + ", ".join(f"{f} {w:+.2f}" for f, w in zip(FEATURES, weights)))

    save_chart(y_test, rule_scores, model_scores)
    print(f"\nSaved {CHART_PATH.relative_to(REPO_ROOT)} in {time.monotonic() - started:.1f}s")


if __name__ == "__main__":
    main()
