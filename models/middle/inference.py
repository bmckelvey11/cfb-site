"""Cluster-robust means, Wald CIs, and MDEs for backtest deltas."""

from __future__ import annotations

import numpy as np
import pandas as pd

Z_WALD = 1.96
Z_MDE = 2.8  # 80% power, two-sided 5%: z_{1-α/2} + z_{1-β}


def cluster_ids(frame: pd.DataFrame) -> np.ndarray:
    """Season-week slate. Falls back to game_id when week is missing."""
    n = len(frame)
    if "week" in frame.columns and "season" in frame.columns:
        return (frame["season"].astype(str) + "-" + frame["week"].astype(str)).to_numpy()
    if "game_id" in frame.columns:
        return frame["game_id"].to_numpy()
    return np.arange(n)


def cluster_mean(y, groups) -> dict:
    """Mean with cluster-robust SE, 95% Wald CI, and 80%-power MDE."""
    y = np.asarray(y, dtype=float)
    n = int(y.size)
    empty = {
        "n": 0, "n_clusters": 0, "mean": float("nan"), "se": float("nan"),
        "ci_lo": float("nan"), "ci_hi": float("nan"), "mde": float("nan"),
    }
    if n == 0:
        return empty
    mean = float(np.mean(y))
    groups = np.asarray(groups)
    _, inv = np.unique(groups, return_inverse=True)
    g = int(inv.max()) + 1
    if n < 2:
        se = 0.0
    elif g < 2:
        se = float(np.std(y, ddof=1) / np.sqrt(n))
    else:
        centered = y - mean
        sums = np.zeros(g)
        np.add.at(sums, inv, centered)
        var = (g / (g - 1.0)) * (1.0 / n ** 2) * float(np.dot(sums, sums))
        se = float(np.sqrt(max(var, 0.0)))
    return {
        "n": n,
        "n_clusters": g,
        "mean": mean,
        "se": se,
        "ci_lo": mean - Z_WALD * se,
        "ci_hi": mean + Z_WALD * se,
        "mde": Z_MDE * se,
    }


def paired_score_delta(pts, pred, line, groups) -> dict:
    """Per-game MSPE/MAE vs the line. Negative mean → model beats the line."""
    pts = np.asarray(pts, dtype=float)
    pred = np.asarray(pred, dtype=float)
    line = np.asarray(line, dtype=float)
    d_mspe = (pts - pred) ** 2 - (pts - line) ** 2
    d_mae = np.abs(pts - pred) - np.abs(pts - line)
    return {
        "mspe": cluster_mean(d_mspe, groups),
        "mae": cluster_mean(d_mae, groups),
    }


def hit_delta_and_clv(pts, pred, ou_open, total, groups) -> dict:
    """Paired open-vs-close hit differential and CLV on the model's open side."""
    pts = np.asarray(pts, dtype=float)
    pred = np.asarray(pred, dtype=float)
    ou_open = np.asarray(ou_open, dtype=float)
    total = np.asarray(total, dtype=float)
    groups = np.asarray(groups)

    edge_o = ou_open - pred
    edge_c = total - pred
    hit_o = np.where(edge_o > 0, pts < ou_open, ~(pts < ou_open)).astype(bool)
    hit_c = np.where(edge_c > 0, pts < total, ~(pts < total)).astype(bool)
    live = (pts != ou_open) & (pts != total)

    d_hit = hit_o[live].astype(float) - hit_c[live].astype(float)
    clv = np.where(edge_o > 0, ou_open - total, total - ou_open)
    return {
        "n_paired": int(live.sum()),
        "hit_open": float(hit_o[live].mean()) if live.any() else float("nan"),
        "hit_close": float(hit_c[live].mean()) if live.any() else float("nan"),
        "hit_delta": cluster_mean(d_hit, groups[live]),
        "clv": cluster_mean(clv, groups),
    }
