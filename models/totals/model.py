"""Total-points model and walk-forward backtest.

The model predicts combined points, then bets the side the market disagrees
with: ``edge = line - prediction``; positive edge means the model says UNDER.

The line is itself a feature and dominates importance (~46%). This model is
"trust the market, then nudge" — it does not beat the closing total at raw
prediction, it only wins by disagreeing selectively.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from .inference import cluster_ids, cluster_mean, paired_score_delta

BREAKEVEN = 0.5238  # -110 vig
CITABLE_MIN_EDGE = 0.0  # unselected full book; other thresholds are diagnostic
PAYOUT = 100 / 110  # -110

# Untuned defaults. No hyperparameter search was run — that avoids selection
# bias on the validation seasons, but also means these are not known-optimal.
PARAMS = dict(n_estimators=300, max_depth=3, learning_rate=0.05,
              subsample=0.8, random_state=0)


@dataclass(frozen=True)
class FoldResult:
    season: int
    n_train: int
    frame: pd.DataFrame
    week_expanding: bool = False


@dataclass
class Backtest:
    line_col: str
    folds: list[FoldResult] = field(default_factory=list)

    def _graded(self, expanding: bool | None = None) -> pd.DataFrame:
        folds = self.folds
        if expanding is not None:
            folds = [f for f in folds if f.week_expanding is expanding]
        if not folds:
            return pd.DataFrame()
        return pd.concat([f.frame for f in folds], ignore_index=True)

    @property
    def graded(self) -> pd.DataFrame:
        return self._graded(expanding=None)

    def summary(self, thresholds=(0, 1, 2, 3, 5), *,
                expanding: bool | None = False) -> pd.DataFrame:
        g = self._graded(expanding=expanding)
        if g.empty:
            return pd.DataFrame()
        rows = []
        for thr in thresholds:
            s = g[g["edge"].abs() >= thr]
            if s.empty:
                continue
            wins = int(s["hit"].sum())
            n = len(s)
            groups = cluster_ids(s)
            hit = cluster_mean(s["hit"].astype(float).to_numpy(), groups)
            ret = np.where(s["hit"].to_numpy(), PAYOUT, -1.0)
            roi = cluster_mean(ret, groups)
            rows.append({
                "min_edge": thr, "n": n, "wins": wins, "losses": n - wins,
                "hit_pct": round(100 * wins / n, 2),
                "hit_ci_lo": round(100 * hit["ci_lo"], 2),
                "hit_ci_hi": round(100 * hit["ci_hi"], 2),
                "mde_pp": round(100 * hit["mde"], 2),
                "n_clusters": hit["n_clusters"],
                "roi_pct": round(100 * roi["mean"], 2),
                "roi_ci_lo": round(100 * roi["ci_lo"], 2),
                "roi_ci_hi": round(100 * roi["ci_hi"], 2),
                "citable": thr == CITABLE_MIN_EDGE,
            })
        return pd.DataFrame(rows)

    def by_season(self, min_edge: float = CITABLE_MIN_EDGE, *,
                  expanding: bool | None = False) -> pd.DataFrame:
        g = self._graded(expanding=expanding)
        if g.empty:
            return pd.DataFrame()
        s = g[g["edge"].abs() >= min_edge]
        out = s.groupby("season").agg(n=("hit", "size"), hit_pct=("hit", "mean"))
        out["hit_pct"] = (100 * out["hit_pct"]).round(2)
        return out.reset_index()

    def paired_vs_line(self, *, expanding: bool | None = False) -> dict:
        g = self._graded(expanding=expanding)
        if g.empty:
            return {"mspe": cluster_mean([], []), "mae": cluster_mean([], [])}
        return paired_score_delta(
            g["pts"], g["pred"], g[self.line_col], cluster_ids(g))


def _fit_predict(train: pd.DataFrame, test: pd.DataFrame, cols: list[str],
                 line_col: str) -> np.ndarray:
    x_cols = cols + [line_col]
    median = train[x_cols].median()
    model = GradientBoostingRegressor(**PARAMS)
    model.fit(train[x_cols].fillna(median), train["pts"])
    return model.predict(test[x_cols].fillna(median))


def iter_walk_forward_splits(df: pd.DataFrame, test_seasons, *,
                             min_train: int = 300):
    """Yield (season, train, test) with no future leakage.

    Default is prior seasons only. Opening lines start in 2021, so that first
    year has no prior-season train — fall back to an expanding week window
    inside the year (train weeks 1..k-1, test week k) once ``min_train`` is met.
    """
    has_week = "week" in df.columns
    for season in test_seasons:
        prior = df[df["season"] < season]
        year = df[df["season"] == season]
        if year.empty:
            continue
        if len(prior) >= min_train:
            yield season, prior, year
            continue
        if not has_week:
            continue
        for week in sorted(year["week"].dropna().unique()):
            test_w = year[year["week"] == week]
            train_w = pd.concat(
                [prior, year[year["week"] < week]], ignore_index=True)
            if len(train_w) < min_train or test_w.empty:
                continue
            yield season, train_w, test_w


def _grade_split(train: pd.DataFrame, test: pd.DataFrame, cols: list[str],
                 line_col: str) -> pd.DataFrame:
    pred = _fit_predict(train, test, cols, line_col)
    graded = test.assign(pred=pred)
    graded["edge"] = graded[line_col] - graded["pred"]
    actual_under = graded["pts"] < graded[line_col]
    # cast to bool dtype: np.where on a Series yields object, which makes
    # downstream .mean()/.sum() silently drop rows
    graded["hit"] = np.where(graded["edge"] > 0, actual_under, ~actual_under).astype(bool)
    # Pushes are not wins; drop exact landings so hit-rate is honest.
    return graded[graded["pts"] != graded[line_col]]


def walk_forward(dataset, *, line_col: str = "ou_open",
                 test_seasons=(2021, 2022, 2023, 2024, 2025),
                 min_train: int = 300) -> Backtest:
    """Walk-forward: each season trains on prior seasons only.

    The first season that has this line (2021 for ``ou_open``) uses an
    expanding week window instead, because there is no prior-season train.
    """
    df = dataset.frame.dropna(subset=[line_col, "pts"]).copy()
    bt = Backtest(line_col=line_col)
    parts: dict[int, list[pd.DataFrame]] = {}
    n_train: dict[int, int] = {}
    expanding: dict[int, bool] = {}
    for season, train, test in iter_walk_forward_splits(
            df, test_seasons, min_train=min_train):
        graded = _grade_split(train, test, dataset.feature_cols, line_col)
        keep = ["season", line_col, "pred", "edge", "hit", "pts", "game_id"]
        if "week" in graded.columns:
            keep.append("week")
        if season not in parts:
            n_train[season] = len(train)
            expanding[season] = bool(train["season"].eq(season).any())
            parts[season] = []
        parts[season].append(graded[keep])
    for season in test_seasons:
        if season not in parts:
            continue
        bt.folds.append(FoldResult(
            season=season, n_train=n_train[season],
            frame=pd.concat(parts[season], ignore_index=True),
            week_expanding=expanding[season],
        ))
    return bt


def permutation_test(bt: Backtest, n: int = 500, seed: int = 0, *,
                     expanding: bool | None = False) -> dict:
    """Shuffle predictions to confirm the grading metric isn't self-fulfilling."""
    g = bt._graded(expanding=expanding)
    if g.empty:
        g = bt.graded
    line = g[bt.line_col].to_numpy()
    pts = g["pts"].to_numpy()
    edge = g["edge"].to_numpy()
    rng = np.random.default_rng(seed)
    actual_under = pts < line
    rates = []
    for _ in range(n):
        shuffled = rng.permutation(edge)
        hit = np.where(shuffled > 0, actual_under, ~actual_under)
        rates.append(hit.mean())
    rates = np.array(rates)
    return {
        "shuffled_mean": round(100 * rates.mean(), 2),
        "shuffled_sd": round(100 * rates.std(), 2),
        "ci_lo": round(100 * np.percentile(rates, 2.5), 2),
        "ci_hi": round(100 * np.percentile(rates, 97.5), 2),
        "actual": round(100 * g["hit"].mean(), 2),
    }


def feature_importance(dataset, *, line_col: str = "ou_open",
                       through_season: int = 2022) -> pd.Series:
    df = dataset.frame.dropna(subset=[line_col, "pts"])
    train = df[df["season"] <= through_season]
    x_cols = dataset.feature_cols + [line_col]
    model = GradientBoostingRegressor(**PARAMS)
    model.fit(train[x_cols].fillna(train[x_cols].median()), train["pts"])
    return pd.Series(model.feature_importances_, index=x_cols).sort_values(ascending=False)
