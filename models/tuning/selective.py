"""Selective prediction: abstain on the games expected to be hardest (Release D, D3).

A Ridge meta-model predicts |residual| from the kept features plus `week`, trained only
on out-of-fold residuals of the window seasons before the test season (plan §31.4). A
risk-coverage curve keeps the fraction of games with the lowest predicted error and
reports the mean loss on them; its area (AURC) is compared with keeping everything, which
is also what random abstention gives in expectation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

META_ALPHA = 1.0  # fixed, not tuned: the meta-model must not become a second search


def meta_scores(frame: pd.DataFrame, features: list[str], residual: str, test_season: int,
                window: list[int]) -> pd.Series:
    """Predicted |residual| for the test season's games, fit on the window seasons only."""
    cols = [*features, "week"]
    train = frame[frame["season"].isin(window) & frame[residual].notna()]
    test = frame[frame["season"] == test_season]
    pipe = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                     ("model", Ridge(alpha=META_ALPHA))])
    pipe.fit(train[cols].to_numpy(dtype=float), train[residual].abs().to_numpy(dtype=float))
    return pd.Series(pipe.predict(test[cols].to_numpy(dtype=float)), index=test.index,
                     name="selective_score")


def risk_coverage(loss: pd.Series, score: pd.Series, game_id: pd.Series,
                  coverages: tuple[float, ...]) -> list[dict]:
    """Mean loss on the lowest-score fraction of games; ties broken by game id."""
    order = pd.DataFrame({"loss": loss, "score": score, "gid": game_id}).sort_values(
        ["score", "gid"], kind="stable")
    out = []
    for c in coverages:
        k = max(1, int(round(c * len(order))))
        out.append({"coverage": c, "n_kept": k, "mean_loss": float(order["loss"].iloc[:k].mean())})
    return out


def aurc(curve: list[dict]) -> float:
    """Average risk over the coverage grid (the grid is evenly spaced)."""
    return float(np.mean([p["mean_loss"] for p in curve]))


def aurc_vs_full(df: pd.DataFrame, coverages: tuple[float, ...], draws: int = 10_000,
                 seed: int = 20260922) -> dict:
    """AURC minus full-coverage risk, with a season-week cluster bootstrap interval.

    `df` needs season, week, game_id, loss, score. Negative means abstaining on high
    scores lowers the loss on the games kept.
    """
    def stat(d: pd.DataFrame) -> float:
        return aurc(risk_coverage(d["loss"], d["score"], d["game_id"], coverages)) - d["loss"].mean()

    df = df.reset_index(drop=True)
    groups = [idx.to_numpy() for _, idx in df.groupby(["season", "week"]).groups.items()]
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(draws):
        pick = rng.integers(0, len(groups), size=len(groups))
        boot.append(stat(df.iloc[np.concatenate([groups[i] for i in pick])]))
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"diff": float(stat(df)), "ci95": [float(lo), float(hi)], "draws": draws,
            "n": int(len(df)), "n_clusters": len(groups),
            "curve": risk_coverage(df["loss"], df["score"], df["game_id"], coverages)}
