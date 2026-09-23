"""Predictive distributions of the full-game total (Release D, D1).

Every candidate returns one probability table per game over integer totals
0..support_max, overtime included; scores, intervals, and prices all derive from it.

- `normal_const`: N(mu, sigma^2), sigma the window's residual SD, discretized.
- `empirical_total`: mu plus every residual in the game's segment pool, rounded.
- `joint_bootstrap`: home and away regulation means shifted by residual pairs from the
  same historical game; a regulation tie adds an observed overtime total.

Point forecasts are season-ahead (each season fit on every earlier usable season), and
residual pools come from the `window` most recent usable seasons before the test season,
split into early (a team with fewer than `early_min` prior games) and primary games.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from models.tuning.dist_spec import CalibrationGate
from models.tuning.estimators import fit_fold
from models.tuning.folds import make_folds
from models.tuning.spec import FoldSpec, ModelSpec, RunSpec

TARGET_PARTS = ("home_reg", "away_reg", "ot_points")


def season_forecasts(frame: pd.DataFrame, run_spec: RunSpec, model: ModelSpec, target: str,
                     seasons: list[int]) -> pd.Series:
    """Out-of-sample forecasts of `target`: each season fit only on earlier usable seasons."""
    work = frame.assign(target=frame[target])
    folds = make_folds(FoldSpec(inner_test_seasons=(), outer_test_seasons=tuple(seasons),
                                exclude_seasons=run_spec.folds.exclude_seasons,
                                embargo_days=run_spec.folds.embargo_days), work)
    out = pd.Series(np.nan, index=frame.index, name=f"{target}_hat")
    for fold in folds:
        r = fit_fold(work.loc[fold.train_idx], work.loc[fold.test_idx], run_spec, model,
                     fold.fold_id)
        out.loc[fold.test_idx] = [p for _, p in r.predictions]
    return out


def window_seasons(test_season: int, usable: list[int], k: int) -> list[int]:
    return sorted(s for s in usable if s < test_season)[-k:]


def normal_pmf(mu: np.ndarray, sigma: np.ndarray, support_max: int) -> np.ndarray:
    edges = np.arange(-0.5, support_max + 1.0)            # bin k is [k - 0.5, k + 0.5)
    cdf = norm.cdf((edges[None, :] - mu[:, None]) / sigma[:, None])
    cdf[:, 0], cdf[:, -1] = 0.0, 1.0                       # tails go to the end bins
    return np.diff(cdf, axis=1)


def empirical_pmf(mu: np.ndarray, pools: list[np.ndarray], support_max: int) -> np.ndarray:
    out = np.zeros((len(mu), support_max + 1))
    for i, (m, e) in enumerate(zip(mu, pools)):
        vals = np.clip(np.round(m + e), 0, support_max).astype(int)
        out[i] = np.bincount(vals, minlength=support_max + 1) / len(vals)
    return out


def joint_pmf(mu_home: np.ndarray, mu_away: np.ndarray, pair_pools: list[np.ndarray],
              ot_pools: list[np.ndarray], support_max: int) -> tuple[np.ndarray, np.ndarray]:
    """Table of totals and P(home win), a regulation tie counting as half a win."""
    out = np.zeros((len(mu_home), support_max + 1))
    home_win = np.zeros(len(mu_home))
    for i, (mh, ma, pairs, ot) in enumerate(zip(mu_home, mu_away, pair_pools, ot_pools)):
        h = np.maximum(np.round(mh + pairs[:, 0]), 0)
        a = np.maximum(np.round(ma + pairs[:, 1]), 0)
        tie = h == a
        total = h + a
        m = len(pairs)
        decided = np.clip(total[~tie], 0, support_max).astype(int)
        out[i] = np.bincount(decided, minlength=support_max + 1) / m
        if tie.any():
            if len(ot):
                spread = np.clip(np.add.outer(total[tie], ot).ravel(), 0, support_max).astype(int)
                out[i] += np.bincount(spread, minlength=support_max + 1) / (m * len(ot))
            else:
                tied = np.clip(total[tie], 0, support_max).astype(int)
                out[i] += np.bincount(tied, minlength=support_max + 1) / m
        home_win[i] = ((h > a).sum() + 0.5 * tie.sum()) / m
    return out, home_win


def score_pmf(pmf: np.ndarray, y: np.ndarray, quantiles: tuple[float, ...],
              levels: tuple[float, ...]) -> pd.DataFrame:
    """Per-game CRPS, mid-PIT, central-interval hits, quantiles, pinball loss, mean, SD."""
    support = np.arange(pmf.shape[1])
    y = np.clip(np.asarray(y, dtype=int), 0, pmf.shape[1] - 1)
    cdf = np.cumsum(pmf, axis=1)
    step = (support[None, :] >= y[:, None]).astype(float)
    rows = np.arange(len(y))
    below = np.where(y > 0, cdf[rows, np.maximum(y - 1, 0)], 0.0)
    pit = below + 0.5 * pmf[rows, y]
    mean = pmf @ support
    out = {"crps": ((cdf - step) ** 2).sum(axis=1), "pit": pit, "mean": mean,
           "sd": np.sqrt(np.maximum(pmf @ support ** 2 - mean ** 2, 0.0))}
    for lv in levels:
        tail = (1 - lv) / 2
        out[f"cover_{lv:g}"] = (pit >= tail) & (pit <= 1 - tail)
    for tau in quantiles:
        q = (cdf >= tau - 1e-12).argmax(axis=1)
        out[f"q_{tau:g}"] = q
        out[f"pinball_{tau:g}"] = (y - q) * (tau - (y < q))
    return pd.DataFrame(out)


def calibration_report(scores: pd.DataFrame, gate: CalibrationGate,
                       levels: tuple[float, ...]) -> dict:
    """The declared gate: pooled coverage, one season-level coverage, PIT deciles."""
    pooled = {f"{lv:g}": {"value": float(scores[f"cover_{lv:g}"].mean()), "nominal": lv}
              for lv in levels}
    for v in pooled.values():
        v["pass"] = abs(v["value"] - v["nominal"]) <= gate.pooled_coverage_tol
    key = f"cover_{gate.season_coverage_level:g}"
    by_season = {int(s): {"value": float(g[key].mean()), "n": int(len(g))}
                 for s, g in scores.groupby("season")}
    for v in by_season.values():
        v["pass"] = abs(v["value"] - gate.season_coverage_level) <= gate.season_coverage_tol
    deciles = np.histogram(scores["pit"], bins=np.linspace(0, 1, 11))[0] / len(scores)
    worst = float(np.abs(deciles - 0.1).max())
    passed = (all(v["pass"] for v in pooled.values()) and all(v["pass"] for v in by_season.values())
              and worst <= gate.pit_decile_tol)
    return {"pass": bool(passed), "pooled_coverage": pooled,
            "season_coverage": {"level": gate.season_coverage_level, "by_season": by_season},
            "pit_deciles": {"shares": [float(d) for d in deciles], "max_abs_dev": worst,
                            "tolerance": gate.pit_decile_tol, "pass": worst <= gate.pit_decile_tol},
            "n": int(len(scores))}


def paired_diff(scores: pd.DataFrame, a: str, b: str) -> dict:
    """Mean of a - b per game with Release B's week-cluster bootstrap interval."""
    from scripts.weekly_ratings_eval import Z_MDE, _cluster_boot

    d = scores[a] - scores[b]
    boot, sums = _cluster_boot(scores, {"d": d, "n": pd.Series(1.0, index=scores.index)})
    draws = boot["d"] / boot["n"]
    lo, hi = np.percentile(draws, [2.5, 97.5])
    se = float(draws.std(ddof=1))
    return {"n": int(len(scores)), "n_clusters": int(len(sums)), "diff": float(d.mean()),
            "ci95": [float(lo), float(hi)], "mde80": Z_MDE * se,
            "by_season": {int(s): float(v) for s, v in d.groupby(scores["season"]).mean().items()}}


def open_label_scores(pmf: np.ndarray, y: np.ndarray, label: np.ndarray) -> dict:
    """Brier and log loss of P(over the label), pushes excluded; a forecast, not a price."""
    y = np.asarray(y, dtype=float)
    label = np.asarray(label, dtype=float)
    have = ~np.isnan(label)
    push = have & (y == label)
    keep = have & ~push
    cdf = np.cumsum(pmf, axis=1)
    floor = np.clip(np.floor(label[keep]).astype(int), 0, pmf.shape[1] - 1)
    rows = np.flatnonzero(keep)
    p_over = 1.0 - cdf[rows, floor]
    integer = label[keep] == np.floor(label[keep])
    p_push = np.where(integer, pmf[rows, floor], 0.0)
    p = np.clip(p_over / np.maximum(1.0 - p_push, 1e-12), 1e-12, 1 - 1e-12)
    o = (y[keep] > label[keep]).astype(float)
    bins = np.minimum((p * 10).astype(int), 9)
    reliability = [{"decile": int(b), "n": int((bins == b).sum()),
                    "mean_p": float(p[bins == b].mean()), "over_rate": float(o[bins == b].mean())}
                   for b in range(10) if (bins == b).any()]
    return {"n": int(keep.sum()), "pushes_excluded": int(push.sum()),
            "brier": float(((p - o) ** 2).mean()) if keep.any() else None,
            "log_loss": float(-(o * np.log(p) + (1 - o) * np.log(1 - p)).mean()) if keep.any() else None,
            "over_rate": float(o.mean()) if keep.any() else None, "reliability": reliability}
