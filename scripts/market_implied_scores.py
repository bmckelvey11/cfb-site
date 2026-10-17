"""Market-implied score baseline: the Bovada open's spread and total as one score per side.

    python -m scripts.market_implied_scores

Declared in rankings/docs/specs/2026-10-17-market-implied-score-design.md. For every
FBS-vs-FBS game (regular season and postseason) with a Bovada `spreadOpen` and
`overUnderOpen` in raw/lines_<season>.json and a final score:

    implied   home = (T + M) / 2, away = (T - M) / 2, M = -spreadOpen, T = overUnderOpen
    ridge_v1  the weekly possession ridge's implied regulation points per side
              (scripts.weekly_forecast._parts) plus half its overtime constant, fitted on the
              season's games that kicked off before the week's first kickoff
    mean      season-to-date league mean final points, home and away, from FBS-vs-FBS games
              before the week's first kickoff

CFBD carries no open line before 2021, so (spec amendment, 2026-10-17) each model's forecast
SD (one number for both sides) is fitted on 2021-2022 by mean CRPS on a 0.5-point grid and held
fixed for the 2023-2025 descriptive window; 2021-2025 pooled is also shown, flagged in-sample
for the SD. Every window uses the games all three models share. Paired differences (implied
minus each comparator) use a season-week block bootstrap, 2,000 draws, seed 20261017. Reads
nothing after 2026-10-16.
Writes processed/ratings/market_implied_scores.json.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.glicko_ratings_eval import crps

TUNE = [2021, 2022]                                # SD fit (spec amendment 2026-10-17)
DESCRIBE = [2023, 2024, 2025]
POOLED = TUNE + DESCRIBE                           # shown, in-sample for the SD
CUTOFF = pd.Timestamp("2026-10-17T00:00:00Z")      # nothing at or after this is read
OPEN_PROVIDER = "Bovada"
SD_GRID = tuple(np.arange(8.0, 16.01, 0.5).round(1))
BOOT_DRAWS, BOOT_SEED = 2000, 20261017
MODELS = ("implied", "ridge_v1", "mean")


def implied_scores(spread_open: float, total_open: float) -> tuple[float, float]:
    """(home, away) implied final scores. spread_open is home-relative, negative when the home
    team is favoured (sportsbook convention), so the implied home margin is -spread_open."""
    m = -spread_open
    return (total_open + m) / 2.0, (total_open - m) / 2.0


def bovada_opens(raw: Path, season: int) -> dict[int, tuple[float, float]]:
    """{game_id: (spreadOpen, overUnderOpen)} from the first Bovada row per game, both present."""
    out: dict[int, tuple[float, float]] = {}
    seen: set[int] = set()
    for g in json.loads((raw / f"lines_{season}.json").read_text(encoding="utf-8")):
        for ln in g.get("lines") or []:
            if ln.get("provider") == OPEN_PROVIDER and g["id"] not in seen:
                seen.add(g["id"])
                s, t = ln.get("spreadOpen"), ln.get("overUnderOpen")
                if s is not None and t is not None:
                    out[g["id"]] = (float(s), float(t))
    return out


def scored_games(raw: Path, season: int) -> pd.DataFrame:
    """Completed FBS-vs-FBS games (regular + postseason) with final scores, before CUTOFF."""
    rows = []
    for g in json.loads((raw / f"games_{season}.json").read_text(encoding="utf-8")):
        kick = pd.to_datetime(g.get("startDate"), errors="coerce", utc=True, format="ISO8601")
        if (not g.get("completed") or g.get("homePoints") is None or g.get("awayPoints") is None
                or g.get("homeClassification") != "fbs" or g.get("awayClassification") != "fbs"
                or pd.isna(kick) or kick >= CUTOFF):
            continue
        rows.append({"game_id": g["id"], "season": season, "season_type": g["seasonType"],
                     "week": g["week"], "kickoff": kick, "home": g["homeTeam"], "away": g["awayTeam"],
                     "neutral": bool(g.get("neutralSite")),
                     "home_pts": float(g["homePoints"]), "away_pts": float(g["awayPoints"])})
    return pd.DataFrame(rows)


def forecasts(root: Path, season: int) -> pd.DataFrame:
    """One row per scored game with each model's (home, away) forecast; NaN where not built."""
    from scripts.weekly_forecast import _parts
    from scripts.weekly_rankings import RIDGE_V1
    from scripts.weekly_ratings import fit_ridge, fit_set
    from scripts.weekly_ratings_eval import load

    raw = root / "raw"
    g = scored_games(raw, season)
    opens = bovada_opens(raw, season)
    g = g[g["game_id"].isin(opens)].reset_index(drop=True)
    imp = np.array([implied_scores(*opens[i]) for i in g["game_id"]])
    g["implied_h"], g["implied_a"] = imp[:, 0], imp[:, 1]
    fit_games, _ = load(root, [season], [])
    all_fbs = scored_games(raw, season)          # league-mean evidence, any line or none
    for col in ("ridge_v1_h", "ridge_v1_a", "mean_h", "mean_a"):
        g[col] = np.nan
    for _, idx in g.groupby(["season_type", "week"]).groups.items():
        cut = g.loc[idx, "kickoff"].min()
        prior = all_fbs[all_fbs["kickoff"] < cut]
        if len(prior):
            g.loc[idx, "mean_h"], g.loc[idx, "mean_a"] = prior["home_pts"].mean(), prior["away_pts"].mean()
        fs = fit_set(fit_games, cut)
        if len(fs) == 0:
            continue
        r = fit_ridge(fs, *RIDGE_V1)
        for i in idx:
            _, ph, pa = _parts(r, g.at[i, "home"], g.at[i, "away"], bool(g.at[i, "neutral"]))
            g.at[i, "ridge_v1_h"], g.at[i, "ridge_v1_a"] = ph + r.c / 2.0, pa + r.c / 2.0
    return g


def _long(d: pd.DataFrame, model: str) -> tuple[np.ndarray, np.ndarray]:
    """(forecast, actual) stacked home then away."""
    return (np.r_[d[f"{model}_h"].to_numpy(), d[f"{model}_a"].to_numpy()],
            np.r_[d["home_pts"].to_numpy(), d["away_pts"].to_numpy()])


def fit_sd(d: pd.DataFrame, model: str) -> float:
    f, y = _long(d, model)
    return min(SD_GRID, key=lambda s: float(crps(f, np.full_like(f, s), y).mean()))


def _slope(f: np.ndarray, y: np.ndarray) -> dict:
    b, a = np.polyfit(f, y, 1)
    return {"slope": round(float(b), 3), "intercept": round(float(a), 2)}


def side_metrics(d: pd.DataFrame, model: str, sd: float) -> dict:
    out = {}
    for side, (f, y) in {"home": (d[f"{model}_h"].to_numpy(), d["home_pts"].to_numpy()),
                         "away": (d[f"{model}_a"].to_numpy(), d["away_pts"].to_numpy()),
                         "pooled": _long(d, model)}.items():
        e = y - f
        out[side] = {"mae": round(float(np.abs(e).mean()), 3),
                     "rmse": round(float(np.sqrt((e ** 2).mean())), 3),
                     "crps": round(float(crps(f, np.full_like(f, sd), y).mean()), 3),
                     "bias": round(float(e.mean()), 3), **_slope(f, y)}
    eh = d["home_pts"].to_numpy() - d[f"{model}_h"].to_numpy()
    ea = d["away_pts"].to_numpy() - d[f"{model}_a"].to_numpy()
    out["home_away_error_corr"] = round(float(np.corrcoef(eh, ea)[0, 1]), 3)
    return out


def _game_loss(d: pd.DataFrame, model: str, sd: float, kind: str) -> np.ndarray:
    """Per-game loss, the mean of the two sides."""
    fh, fa = d[f"{model}_h"].to_numpy(), d[f"{model}_a"].to_numpy()
    yh, ya = d["home_pts"].to_numpy(), d["away_pts"].to_numpy()
    if kind == "mae":
        return (np.abs(yh - fh) + np.abs(ya - fa)) / 2.0
    s = np.full_like(fh, sd)
    return (crps(fh, s, yh) + crps(fa, s, ya)) / 2.0


def paired(d: pd.DataFrame, a: str, b: str, sds: dict, kind: str) -> dict:
    """Mean per-game loss(a) - loss(b), season-week block bootstrap interval."""
    diff = pd.Series(_game_loss(d, a, sds[a], kind) - _game_loss(d, b, sds[b], kind), index=d.index)
    blocks = d["season"].astype(str) + "-" + d["season_type"] + "-" + d["week"].astype(str)
    sums = diff.groupby(blocks).agg(["sum", "count"])
    idx = np.random.default_rng(BOOT_SEED).integers(0, len(sums), size=(BOOT_DRAWS, len(sums)))
    boot = sums["sum"].to_numpy()[idx].sum(1) / sums["count"].to_numpy()[idx].sum(1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"diff": round(float(diff.mean()), 3), "ci95": [round(float(lo), 3), round(float(hi), 3)],
            "by_season": {int(s): round(float(v), 3) for s, v in diff.groupby(d["season"]).mean().items()}}


def window_report(d: pd.DataFrame, sds: dict, n_implied: int) -> dict:
    return {"games_with_bovada_open": n_implied, "shared_games": int(len(d)),
            "by_season_shared": {int(s): int(n) for s, n in d.groupby("season").size().items()},
            "metrics": {m: side_metrics(d, m, sds[m]) for m in MODELS},
            "paired_implied_minus": {c: {k: paired(d, "implied", c, sds, k) for k in ("mae", "crps")}
                                     for c in ("ridge_v1", "mean")}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args(argv)
    from cfb_paths import DATA_ROOT, PROCESSED

    frames = {s: forecasts(DATA_ROOT, s) for s in POOLED}
    full = pd.concat(frames.values(), ignore_index=True)
    assert full["kickoff"].max() < CUTOFF
    shared = full.dropna(subset=[f"{m}_{s}" for m in MODELS for s in "ha"])
    tune = shared[shared["season"].isin(TUNE)]
    sds = {m: fit_sd(tune, m) for m in MODELS}
    report = {
        "spec": "rankings/docs/specs/2026-10-17-market-implied-score-design.md",
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cutoff": CUTOFF.isoformat(), "provider": OPEN_PROVIDER, "sd_grid": [SD_GRID[0], SD_GRID[-1], 0.5],
        "sd_fitted_on": TUNE, "sd": sds,
        "windows": {
            "2023-2025": window_report(shared[shared["season"].isin(DESCRIBE)], sds,
                                       int(full["season"].isin(DESCRIBE).sum())),
            "2021-2025_pooled_in_sample_sd": window_report(shared, sds, len(full)),
            "2021-2022_fit": window_report(tune, sds, int(full["season"].isin(TUNE).sum())),
        },
        "trial_count": {"baselines": 1, "comparators": 2, "sd_grids": len(MODELS)},
    }
    out = PROCESSED / "ratings" / "market_implied_scores.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
