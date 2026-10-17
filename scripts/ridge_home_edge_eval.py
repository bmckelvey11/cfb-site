"""ridge_v1's home edge: fitted each week (free), carried from last season, or fixed at 2.4.

    python -m scripts.ridge_home_edge_eval

Declared in rankings/docs/specs/2026-10-17-ridge-home-edge-design.md. Every variant is the
weekly possession ridge with ridge_v1's lambdas; only the home term h differs:

    free    fitted each week, unpenalized (ridge_v1 unchanged)
    carry   fixed at the previous season's end-of-regular-season free fit; 2021 carries 2019
    fixed   fixed at 2.4 points of margin, h = 2.4 / (2 * mean possessions per team)

Scored on completed FBS-vs-FBS games (regular + postseason, week 1 skipped) as final points
per side: regulation points from weekly_forecast._parts plus half the overtime constant.
Pick on 2014-2019 (each variant's SD fitted there), check on 2021-2025 with SDs fixed.
Paired differences use the baseline's season-week block bootstrap. Reads nothing after
2026-10-16. Writes processed/ratings/ridge_home_edge.json.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.market_implied_scores import (
    BOOT_DRAWS, BOOT_SEED, CUTOFF, SD_GRID, bovada_opens, fit_sd, implied_scores, paired,
    scored_games, side_metrics,
)

VARIANTS = ("free", "carry", "fixed")
H_FIXED_POINTS = 2.4                       # Benz, Bliss and Lopez, FBS 2023 (arXiv 2401.16392)
PICK = [2014, 2015, 2016, 2017, 2018, 2019]
CHECK = [2021, 2022, 2023, 2024, 2025]
SKIP_CARRY = {2020}                        # empty stadiums: never carried forward


def carry_season(season: int) -> int:
    """The season whose end-of-regular-season h is carried into `season`."""
    s = season - 1
    while s in SKIP_CARRY:
        s -= 1
    return s


def h_from_points(points: float, fit_set: pd.DataFrame) -> float:
    """Points of margin -> points per possession: the margin moves by 2 * h * N."""
    return points / (2.0 * float(fit_set["N"].mean()))


def season_end_h(root: Path, season: int) -> float:
    """The free fit's h on every non-gated regular-season game of `season`."""
    from scripts.weekly_rankings import RIDGE_V1
    from scripts.weekly_ratings import fit_ridge
    from scripts.weekly_ratings_eval import load

    g, _ = load(root, [season], [])
    return fit_ridge(g[~g["gated"]], *RIDGE_V1).h


def forecasts(root: Path, season: int, h_carry: float) -> tuple[pd.DataFrame, list[dict]]:
    """One row per scored game with every variant's (home, away) forecast and the implied
    scores where a Bovada open exists; plus the free fit's h by week."""
    from scripts.weekly_forecast import _parts
    from scripts.weekly_rankings import RIDGE_V1
    from scripts.weekly_ratings import fit_ridge, fit_set
    from scripts.weekly_ratings_eval import load

    raw = root / "raw"
    g = scored_games(raw, season)
    fit_games, _ = load(root, [season], [])
    opens = bovada_opens(raw, season) if (raw / f"lines_{season}.json").exists() else {}
    g["implied_h"] = g["implied_a"] = np.nan
    for i, gid in g["game_id"].items():
        if gid in opens:
            g.at[i, "implied_h"], g.at[i, "implied_a"] = implied_scores(*opens[gid])
    for v in VARIANTS:
        g[f"{v}_h"] = g[f"{v}_a"] = np.nan
    h_log = []
    for (stype, week), idx in g.groupby(["season_type", "week"]).groups.items():
        fs = fit_set(fit_games, g.loc[idx, "kickoff"].min())
        if len(fs) == 0:
            continue
        fits = {"free": fit_ridge(fs, *RIDGE_V1),
                "carry": fit_ridge(fs, *RIDGE_V1, h_fixed=h_carry),
                "fixed": fit_ridge(fs, *RIDGE_V1, h_fixed=h_from_points(H_FIXED_POINTS, fs))}
        h_log.append({"season": season, "season_type": stype, "week": int(week),
                      "n_fit_games": int(len(fs)),
                      "free_h_points": round(2.0 * fits["free"].h * float(fs["N"].mean()), 3)})
        for v, r in fits.items():
            for i in idx:
                _, ph, pa = _parts(r, g.at[i, "home"], g.at[i, "away"], bool(g.at[i, "neutral"]))
                g.at[i, f"{v}_h"], g.at[i, f"{v}_a"] = ph + r.c / 2.0, pa + r.c / 2.0
    return g, h_log


def margin_metrics(d: pd.DataFrame, model: str) -> dict:
    """Home margin and total: bias is actual minus forecast; positive bias on the margin
    means the forecast gave home teams too little."""
    m_f = d[f"{model}_h"] - d[f"{model}_a"]
    m_y = d["home_pts"] - d["away_pts"]
    t_f = d[f"{model}_h"] + d[f"{model}_a"]
    t_y = d["home_pts"] + d["away_pts"]
    return {"margin_bias": round(float((m_y - m_f).mean()), 3),
            "margin_mae": round(float((m_y - m_f).abs().mean()), 3),
            "margin_bias_true_home": round(float((m_y - m_f)[~d["neutral"]].mean()), 3),
            "total_mae": round(float((t_y - t_f).abs().mean()), 3)}


def week_bucket(d: pd.DataFrame) -> pd.Series:
    w = d["week"]
    return pd.Series(np.where(d["season_type"] != "regular", "post",
                              np.where(w <= 4, "2-4", np.where(w <= 8, "5-8", "9+"))), index=d.index)


def window(d: pd.DataFrame, sds: dict) -> dict:
    return {
        "games": int(len(d)),
        "by_season": {int(s): int(n) for s, n in d.groupby("season").size().items()},
        "metrics": {v: {**side_metrics(d, v, sds[v]), **margin_metrics(d, v)} for v in VARIANTS},
        "paired_minus_free": {v: {k: paired(d, v, "free", sds, k) for k in ("crps", "mae")}
                              for v in VARIANTS if v != "free"},
        "free_margin_bias_by_week": {b: round(float(((x["home_pts"] - x["away_pts"])
                                                      - (x["free_h"] - x["free_a"])).mean()), 3)
                                     for b, x in d.groupby(week_bucket(d))},
    }


def vs_implied(d: pd.DataFrame) -> dict:
    """MAE only: implied has no SD fitted on the pick window."""
    sds = dict.fromkeys(("implied",) + VARIANTS, 1.0)
    return {"games": int(len(d)),
            "implied": margin_metrics(d, "implied"),
            "paired_mae_minus_implied": {v: paired(d, v, "implied", sds, "mae") for v in VARIANTS}}


def pick(sds: dict, tune: pd.DataFrame) -> tuple[str, dict]:
    from scripts.glicko_ratings_eval import crps
    loss = {}
    for v in VARIANTS:
        s = np.full(len(tune), sds[v])
        loss[v] = float(((crps(tune[f"{v}_h"].to_numpy(), s, tune["home_pts"].to_numpy())
                          + crps(tune[f"{v}_a"].to_numpy(), s, tune["away_pts"].to_numpy())) / 2).mean())
    return min(loss, key=loss.get), {v: round(x, 4) for v, x in loss.items()}


def adopt(choice: str, check: dict) -> bool:
    """The spec's rule: pick is not free and its 2021-25 CRPS interval vs free is below 0."""
    return choice != "free" and check["paired_minus_free"][choice]["crps"]["ci95"][1] < 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args(argv)
    from cfb_paths import DATA_ROOT, PROCESSED

    seasons = PICK + CHECK
    carried = {s: carry_season(s) for s in seasons}
    h_end = {s: season_end_h(DATA_ROOT, s) for s in sorted(set(carried.values()))}
    frames, h_log = [], []
    for s in seasons:
        f, log = forecasts(DATA_ROOT, s, h_end[carried[s]])
        frames.append(f)
        h_log += log
    full = pd.concat(frames, ignore_index=True)
    assert full["kickoff"].max() < CUTOFF
    scored = full.dropna(subset=[f"{v}_{s}" for v in VARIANTS for s in "ha"])
    tune = scored[scored["season"].isin(PICK)]
    check = scored[scored["season"].isin(CHECK)]
    sds = {v: fit_sd(tune, v) for v in VARIANTS}
    choice, tune_loss = pick(sds, tune)
    check_report = window(check, sds)
    report = {
        "spec": "rankings/docs/specs/2026-10-17-ridge-home-edge-design.md",
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cutoff": CUTOFF.isoformat(), "h_fixed_points": H_FIXED_POINTS,
        "carried_h_points_note": "end-of-season free h, points per possession",
        "season_end_h_ppp": {int(s): round(h, 5) for s, h in h_end.items()},
        "carried_from": carried,
        "sd": sds, "sd_grid": [SD_GRID[0], SD_GRID[-1], 0.5], "sd_fitted_on": PICK,
        "pick": {"variant": choice, "mean_game_crps": tune_loss},
        "adopt": adopt(choice, check_report),
        "windows": {"2014-2019_pick": window(tune, sds), "2021-2025_check": check_report},
        "vs_implied_2021-2025": vs_implied(check.dropna(subset=["implied_h", "implied_a"])),
        "free_h_by_week": h_log,
        "bootstrap": {"draws": BOOT_DRAWS, "seed": BOOT_SEED, "blocks": "season-type-week"},
        "trial_count": {"variants": len(VARIANTS), "sd_grid_points": len(SD_GRID)},
    }
    out = PROCESSED / "ratings" / "ridge_home_edge.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("sd", "pick", "adopt", "season_end_h_ppp")}, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
