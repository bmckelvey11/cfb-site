"""Where P1 Glicko's forecast errors sit, on seasons already scored. Reads no market data.

    CFB_DATA_ROOT=... python -m scripts.glicko_diagnostics [--seasons 2014-2025]

Each check reads the residual e = margin - P1 forecast (home minus away, points) and the
z-score e / sd, with sd from SIGMA_PRED_P1. Nothing is tuned, so this spends no holdout.
2026 is excluded by default: it belongs to P1's sealed confirmation and to the bundle
holdout declared in docs/superpowers/specs/2026-10-16-glicko-p3-bundles-design.md.

  D1 scale      slope of e on the forecast; != 0 means ratings are too spread or too compressed
  D2 fcs_gap    mean e in FBS-vs-FCS games, FBS side, by season (does the FBS-FCS gap drift?)
  D3 coverage   68% / 95% coverage by game type (FBS-FBS, FBS-FCS, neutral, postseason, OT,
                week 1-3 / 4-7 / 8+)
  D4 home_edge  mean e in non-neutral games by season: positive means 2.0 is too small then
  D5 switchers  mean e for a team in its first season after a conference change (team side)
  D6 overtime   mean |e| and coverage in OT games vs regulation games

Means carry a season-week block bootstrap 95% interval (2,000 draws). Writes
data/processed/ratings/glicko_diagnostics.json.
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from scripts.glicko_p2_eval import forecast
from scripts.glicko_pool_eval import fcs_seed_pool, load_pool_games
from scripts.glicko_ratings import FBS, SIGMA_PRED_P1, events

DRAWS, SEED = 2000, 11


def _boot(values: pd.Series, clusters: pd.Series, stat=np.mean) -> dict:
    """Point value and season-week block bootstrap 95% interval of stat(values)."""
    v = values.to_numpy(float)
    groups = [v[idx] for idx in clusters.groupby(clusters).indices.values()]
    rng = np.random.default_rng(SEED)
    draws = [stat(np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))]))
             for _ in range(DRAWS)]
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"n": int(len(v)), "value": round(float(stat(v)), 3), "ci95": [round(float(lo), 3), round(float(hi), 3)]}


def _slope(d: pd.DataFrame) -> dict:
    x, y = d["mhat"].to_numpy(float), d["e"].to_numpy(float)
    xy = np.column_stack([x, y])
    groups = [xy[idx] for idx in d["cluster"].groupby(d["cluster"]).indices.values()]

    def fit(a):
        return float(np.polyfit(a[:, 0], a[:, 1], 1)[0])

    rng = np.random.default_rng(SEED)
    draws = [fit(np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))]))
             for _ in range(DRAWS)]
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"n": int(len(d)), "slope": round(fit(xy), 4), "ci95": [round(float(lo), 4), round(float(hi), 4)]}


def _cov(d: pd.DataFrame) -> dict:
    z = d["z"].abs()
    return {"n": int(len(d)), "cov68": round(float((z <= 0.9945).mean()), 3),
            "cov95": round(float((z <= 1.96).mean()), 3), "mae": round(float(d["e"].abs().mean()), 2)}


def overtime_ids(root, seasons) -> set[int]:
    """Games whose line scores run past four periods."""
    out = set()
    for s in seasons:
        for g in json.loads((root / "raw" / f"games_{s}.json").read_text(encoding="utf-8")):
            if len(g.get("homeLineScores") or []) > 4:
                out.add(g["id"])
    return out


def switchers(g: pd.DataFrame) -> set[tuple[int, str]]:
    """(season, team) for a team whose most common conference differs from last season's."""
    rows = pd.concat([g[["season", "home", "home_conf"]].set_axis(["season", "team", "conf"], axis=1),
                      g[["season", "away", "away_conf"]].set_axis(["season", "team", "conf"], axis=1)])
    conf = rows.dropna().groupby(["season", "team"])["conf"].agg(lambda c: c.mode().iloc[0])
    prev = conf.rename(lambda s: s + 1, level=0)
    both = pd.concat([conf, prev], axis=1, keys=["now", "prev"]).dropna()
    return set(both.index[both["now"] != both["prev"]])


def diagnose(d: pd.DataFrame, ot: set[int], moved: set[tuple[int, str]]) -> dict:
    fbs_fbs = (d["home_div"] == FBS) & (d["away_div"] == FBS)
    fbs_fcs = d["home_div"] != d["away_div"]
    reg = d["season_type"] == "regular"
    out = {"D1_scale": {"fbs_fbs": _slope(d[fbs_fbs & reg]), "fbs_fcs": _slope(d[fbs_fcs])}}

    f = d[fbs_fcs].copy()
    f["e_fbs"] = np.where(f["home_div"] == FBS, f["e"], -f["e"])
    out["D2_fcs_gap"] = {int(s): _boot(x["e_fbs"], x["cluster"]) for s, x in f.groupby("season")}

    is_ot = d["game_id"].isin(ot)
    types = {"fbs_fbs_regular": fbs_fbs & reg, "fbs_fcs": fbs_fcs, "neutral": d["neutral"],
             "postseason": ~reg, "overtime": is_ot, "wk1_3": reg & (d["week"] <= 3),
             "wk4_7": reg & d["week"].between(4, 7), "wk8plus": reg & (d["week"] >= 8)}
    out["D3_coverage"] = {k: _cov(d[m]) for k, m in types.items()}

    h = d[fbs_fbs & reg & ~d["neutral"]]
    out["D4_home_edge"] = {int(s): _boot(x["e"], x["cluster"]) for s, x in h.groupby("season")}

    side = pd.concat([d.assign(team=d["home"], e_team=d["e"]), d.assign(team=d["away"], e_team=-d["e"])])
    in_moved = np.array([(s, t) in moved for s, t in zip(side["season"], side["team"])], dtype=bool)
    side = side[in_moved & (side["season_type"] == "regular").to_numpy()]
    out["D5_switchers"] = {"all_games": _boot(side["e_team"], side["cluster"]) if len(side) else None,
                           "wk1_4": _boot(side.loc[side["week"] <= 4, "e_team"],
                                          side.loc[side["week"] <= 4, "cluster"]) if len(side) else None,
                           "team_seasons": len({(s, t) for s, t in zip(side["season"], side["team"])})}

    out["D6_overtime"] = {"overtime": _cov(d[is_ot]), "regulation": _cov(d[~is_ot])}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seasons", default="2014-2025")
    args = ap.parse_args(argv)
    a, b = (int(x) for x in args.seasons.split("-"))

    from cfb_paths import DATA_ROOT, PROCESSED

    g, _ = load_pool_games(DATA_ROOT, b, [])
    g = g.reset_index(drop=True)
    f = forecast(g, events(g), fcs_seed_pool(g), None)
    d = g.assign(mhat=f["mhat"], sd=np.sqrt(f["rd2"] + SIGMA_PRED_P1 ** 2))
    d["e"] = d["margin"] - d["mhat"]
    d["z"] = d["e"] / d["sd"]
    d["cluster"] = d["season"].astype(str) + "-" + d["season_type"] + "-" + d["week"].astype(str)
    d = d[d["season"].between(a, b) & (d["season"] != 2020)]

    report = {"seasons": [a, b], "excluded": [2020, 2026], "sigma_pred": SIGMA_PRED_P1,
              **diagnose(d, overtime_ids(DATA_ROOT, range(a, b + 1)), switchers(g))}
    out = PROCESSED / "ratings" / "glicko_diagnostics.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
