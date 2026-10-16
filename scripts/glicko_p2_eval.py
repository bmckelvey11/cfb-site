"""Audit P1 Glicko and test one declared candidate (P2) against it.

    CFB_DATA_ROOT=... python -m scripts.glicko_p2_eval      # from a feat/glicko-ratings checkout

Declared before scoring (scripts/glicko_p2_declared.json). P1's picks are frozen, not re-tuned.
  P1   FROZEN_P1 on the P1 pool (every completed D-I game), conference offseason targets.
  P2   P1 plus, at each offseason,
         r = target + clamp(w + c*rp_z, 0, 1) * (r_old - target) + b_rp*rp_z + b_rec*rec_z
       rp_z  = z of CFBD returning production (percentPPA) among that season's FBS teams
       rec_z = z of the mean recruiting points of classes s-3..s among that season's FBS teams
       (0 for FCS or a missing row), and a robust update: the innovation margin - mhat is
       clipped at clip*sqrt(S) before the Kalman step.
  sigma_pred  forecast SD sqrt(rd2 + sigma_pred^2); the gain keeps sigma = 15. Changes
       intervals and win probabilities only, never means or ranks. Tuned per model.
Selection: lowest mean CRPS on FBS-vs-FBS regular season 2014-2019 (2013 burn-in).
Score: 2021-2025 (third look for this family), then ONE read of 2026 weeks 1-7, P2 minus P1
paired CRPS and MAE only -- no market data, so P1's sealed 2026 confirmation is untouched.
Paired intervals: season-week block bootstrap, 2,000 draws.
"""
from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from scripts.glicko_pool_eval import fcs_seed_pool, load_pool_games
from scripts.glicko_ratings import FBS, FROZEN_P1, GlickoMargin, events, run
from scripts.glicko_ratings_eval import crps

TUNE = list(range(2014, 2020))
SCORE = [2021, 2022, 2023, 2024, 2025]
HOLDOUT = 2026
INF = float("inf")
GRID = {"b_rp": (0.0, 1.0, 2.0, 3.0), "b_rec": (0.0, 1.5, 3.0, 4.5),
        "c": (0.0, 0.05, 0.1), "w": (0.6, 0.7, 0.8), "clip": (INF, 3.0, 2.5, 2.0)}
SIGMA_PRED = tuple(np.arange(11.0, 16.01, 0.5).round(1))


def _z(d: dict[str, float]) -> dict[str, float]:
    v = np.array(list(d.values()), float)
    mu, sd = v.mean(), v.std()
    return {k: (x - mu) / sd for k, x in d.items()} if sd > 0 else {k: 0.0 for k in d}


def load_features(raw: Path, fbs_by_season: dict[int, set[str]]) -> dict[int, dict[str, tuple[float, float]]]:
    """{season: {team: (rp_z, rec_z)}} among that season's FBS teams. Both are known before
    the first kickoff: returning production describes last season's players still rostered,
    and recruiting classes sign by February."""
    rec = {}
    for p in raw.glob("recruiting_teams_*.json"):
        for r in json.loads(p.read_text()):
            rec[(int(r["year"]), r["team"])] = float(r["points"])
    out = {}
    for s, fbs in fbs_by_season.items():
        path = raw / f"returning_production_{s}.json"
        rp = ({r["team"]: float(r["percentPPA"]) for r in json.loads(path.read_text())
               if r["team"] in fbs and r.get("percentPPA") is not None} if path.exists() else {})
        r4 = {t: float(np.mean(v)) for t in fbs
              if (v := [rec[(y, t)] for y in range(s - 3, s + 1) if (y, t) in rec])}
        rpz, recz = (_z(rp) if rp else {}), (_z(r4) if r4 else {})
        out[s] = {t: (rpz.get(t, 0.0), recz.get(t, 0.0)) for t in fbs}
    return out


class GlickoPrior(GlickoMargin):
    """P2. With b_rp = b_rec = c = 0, w = 0.7 and clip = inf it is P1 exactly."""

    def __init__(self, *, b_rp=0.0, b_rec=0.0, c=0.0, clip=INF, feats=None, **kw):
        super().__init__(**kw)
        self.b_rp, self.b_rec, self.c, self.clip = b_rp, b_rec, c, clip
        self.feats, self._s = feats or {}, None

    def season_start(self, ended, t):
        self._s = ended + 1
        super().season_start(ended, t)

    def _offseason(self, k, t):
        rp, rc = self.feats.get(self._s, {}).get(k, (0.0, 0.0))
        target = self._target(self.div[k], self.conf.get(k))
        w = min(1.0, max(0.0, self.w + self.c * rp))
        self.r[k] = target + w * (self.r[k] - target) + self.b_rp * rp + self.b_rec * rc
        self.u2[k] += self.delta2
        self.tl[k] = t

    def update(self, h, a, neutral, margin, t):
        mhat, s, _ = self.forecast(h, a, neutral, t)
        e = max(-self.cap, min(self.cap, margin)) - mhat
        lim = self.clip * math.sqrt(s)
        e = max(-lim, min(lim, e))
        kh, ka = self.u2[h] / s, self.u2[a] / s
        self.r[h] += kh * e
        self.r[a] -= ka * e
        self.u2[h] *= 1.0 - kh
        self.u2[a] *= 1.0 - ka


def forecast(g, ev, m0, feats, prm=None) -> pd.DataFrame:
    prm = dict(prm or {})
    pick = {**FROZEN_P1, "w": prm.pop("w", FROZEN_P1["w"])}
    model = GlickoPrior(**pick, m0=m0, feats=feats, **prm) if prm else GlickoMargin(**pick, m0=m0)
    fc = run(model, g, ev)
    return pd.DataFrame({"mhat": fc["mhat"].to_numpy(), "rd2": fc["rd2"].to_numpy()}, index=g.index)


def sd_of(f, sigma_pred=None):
    s2 = FROZEN_P1["sigma"] ** 2 if sigma_pred is None else sigma_pred ** 2
    return np.sqrt(f["rd2"].to_numpy() + s2)


def _logit_slope(x, o) -> float:
    b, X = np.zeros(2), np.column_stack([np.ones_like(x), x])
    for _ in range(25):
        p = 1 / (1 + np.exp(-X @ b))
        b += np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]), X.T @ (o - p))
    return float(b[1])


def metrics(mu, sd, y) -> dict:
    p, o, keep = norm.cdf(mu / sd), (y > 0).astype(float), y != 0
    pc = np.clip(p[keep], 1e-9, 1 - 1e-9)
    z = np.abs((y - mu) / sd)
    return {"n": int(len(y)), "crps": round(float(crps(mu, sd, y).mean()), 4),
            "mae": round(float(np.abs(y - mu).mean()), 4),
            "logloss": round(float(-(o[keep] * np.log(pc) + (1 - o[keep]) * np.log(1 - pc)).mean()), 4),
            "cov68": round(float((z <= 0.9945).mean()), 4), "cov95": round(float((z <= 1.96).mean()), 4),
            "calib_slope": round(_logit_slope(np.log(pc / (1 - pc)), o[keep]), 3)}


def paired(d: pd.DataFrame, a: str, b: str, kind: str, draws=2000, seed=7) -> dict:
    y = d["margin"].to_numpy(float)
    if kind == "crps":
        diff = crps(d[a].to_numpy(), d[a + "_sd"].to_numpy(), y) - crps(d[b].to_numpy(), d[b + "_sd"].to_numpy(), y)
    else:
        diff = np.abs(y - d[a].to_numpy()) - np.abs(y - d[b].to_numpy())
    diff = pd.Series(np.asarray(diff), index=d.index)
    sums = diff.groupby(d["season"].astype(str) + "-" + d["week"].astype(str)).agg(["sum", "count"])
    idx = np.random.default_rng(seed).integers(0, len(sums), size=(draws, len(sums)))
    boot = sums["sum"].to_numpy()[idx].sum(1) / sums["count"].to_numpy()[idx].sum(1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"n": int(len(d)), "diff": round(float(diff.mean()), 4),
            "ci95": [round(float(lo), 4), round(float(hi), 4)],
            "by_season": {int(s): round(float(v), 3) for s, v in diff.groupby(d["season"]).mean().items()}}


def frame(g, mask, fcs: dict) -> pd.DataFrame:
    d = g.loc[mask, ["game_id", "season", "week", "margin"]].copy()
    for name, (f, sp) in fcs.items():
        d[name] = f["mhat"].to_numpy()[mask]
        d[name + "_sd"] = sd_of(f, sp)[mask]
    return d


def main() -> None:
    from cfb_paths import DATA_ROOT, PROCESSED

    g, _ = load_pool_games(DATA_ROOT, HOLDOUT, [])
    m0 = fcs_seed_pool(g)
    gs = g[g["season"] <= max(SCORE)].reset_index(drop=True)
    ev = events(gs)
    fbs = {int(s): set(x["home"][x["home_div"] == FBS]) | set(x["away"][x["away_div"] == FBS])
           for s, x in g.groupby("season")}
    feats = load_features(DATA_ROOT / "raw", fbs)
    base = ((gs["season_type"] == "regular") & (gs["home_div"] == FBS) & (gs["away_div"] == FBS)).to_numpy()
    tune, score = base & gs["season"].isin(TUNE).to_numpy(), base & gs["season"].isin(SCORE).to_numpy()
    y = gs["margin"].to_numpy(float)
    loss = lambda f, m, sp=None: float(crps(f["mhat"].to_numpy()[m], sd_of(f, sp)[m], y[:len(m)][m]).mean())

    p1 = forecast(gs, ev, m0, feats)
    identity = forecast(gs, ev, m0, feats, {"b_rp": 0.0, "b_rec": 0.0, "c": 0.0, "w": 0.7, "clip": INF})
    assert np.allclose(identity["mhat"], p1["mhat"]) and np.allclose(identity["rd2"], p1["rd2"]), \
        "GlickoPrior with neutral settings must reproduce P1"

    gt = gs[gs["season"] <= max(TUNE)].reset_index(drop=True)   # tuning never replays past 2019
    evt, nt = events(gt), len(gt)
    lt = lambda f: loss(f, tune[:nt])
    assert np.allclose(forecast(gt, evt, m0, feats)["mhat"], p1["mhat"].to_numpy()[:nt])
    trials = []
    for vals in itertools.product(*GRID.values()):
        prm = dict(zip(GRID, vals))
        trials.append((lt(forecast(gt, evt, m0, feats, prm)), prm))
    trials.sort(key=lambda t: t[0])
    best_loss, pick = trials[0]
    boundary = {a: ("low" if pick[a] == v[0] else "high") for a, v in GRID.items()
                if pick[a] in (v[0], v[-1])}
    p2 = forecast(gs, ev, m0, feats, pick)
    sp1 = min(SIGMA_PRED, key=lambda s: loss(p1, tune, s))
    sp2 = min(SIGMA_PRED, key=lambda s: loss(p2, tune, s))

    # ---- one scoring run on 2021-2025 ----
    d = frame(gs, score, {"p1": (p1, None), "p1cal": (p1, sp1), "p2": (p2, None), "p2cal": (p2, sp2)})
    early = d["week"] <= 4
    pair = {"crps": paired(d, "p2", "p1", "crps"), "mae": paired(d, "p2", "p1", "mae"),
            "crps_wk1_4": paired(d[early], "p2", "p1", "crps"), "mae_wk1_4": paired(d[early], "p2", "p1", "mae"),
            "crps_wk5plus": paired(d[~early], "p2", "p1", "crps"), "mae_wk5plus": paired(d[~early], "p2", "p1", "mae"),
            "p1cal_vs_p1_crps": paired(d, "p1cal", "p1", "crps"),
            "p2cal_vs_p1cal_crps": paired(d, "p2cal", "p1cal", "crps")}

    # ---- stress: each P2 axis to its neighbouring grid values; 2021-25 CRPS must still improve
    stress = {}
    for axis, vals in GRID.items():
        i = vals.index(pick[axis])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                f = forecast(gs, ev, m0, feats, {**pick, axis: vals[j]})
                ds = frame(gs, score, {"p1": (p1, None), "s": (f, None)})
                r = paired(ds, "s", "p1", "crps")
                stress[f"{axis}={vals[j]}"] = {"diff": r["diff"], "ci95": r["ci95"], "improves": r["ci95"][1] < 0}

    # ---- one read of 2026 weeks 1-7: P2 minus P1, CRPS and MAE only ----
    gh = g.reset_index(drop=True)
    evh = events(gh)
    h1, h2 = forecast(gh, evh, m0, feats), forecast(gh, evh, m0, feats, pick)
    hm = ((gh["season"] == HOLDOUT) & (gh["season_type"] == "regular") & (gh["home_div"] == FBS)
          & (gh["away_div"] == FBS) & (gh["week"] <= 7)).to_numpy()
    dh = frame(gh, hm, {"p1": (h1, None), "p2": (h2, None)})
    holdout = {"crps": paired(dh, "p2", "p1", "crps"), "mae": paired(dh, "p2", "p1", "mae"),
               "p1": metrics(dh["p1"].to_numpy(), dh["p1_sd"].to_numpy(), dh["margin"].to_numpy(float)),
               "p2": metrics(dh["p2"].to_numpy(), dh["p2_sd"].to_numpy(), dh["margin"].to_numpy(float))}

    mae_ok = pair["mae"]["ci95"][1] <= 0 or pair["mae"]["ci95"][0] <= 0 <= pair["mae"]["ci95"][1]
    adopt = {"crps_improves": pair["crps"]["ci95"][1] < 0, "mae_not_worse": mae_ok,
             "holdout_crps_le_0": holdout["crps"]["diff"] <= 0,
             "stress_stable": all(v["improves"] for v in stress.values())}
    adopt["ADOPT"] = all(adopt.values())

    report = {
        "seasons": {"burn_in": 2013, "tune": TUNE, "score": SCORE, "holdout": f"{HOLDOUT} weeks 1-7"},
        "m0": m0, "identity_check": "GlickoPrior(neutral) == P1: passed",
        "trials": {"prior_grid": len(trials), "sigma_pred_grid": 2 * len(SIGMA_PRED),
                   "stress": len(stress), "scoring_runs_2021_25": 1, "holdout_reads": 1},
        "tuning": {"p1_crps": round(loss(p1, tune), 4), "p2_crps": round(best_loss, 4), "p2_pick": pick,
                   "p2_boundary": boundary, "sigma_pred_p1": sp1, "sigma_pred_p2": sp2,
                   "p1cal_crps": round(loss(p1, tune, sp1), 4), "p2cal_crps": round(loss(p2, tune, sp2), 4),
                   "top5": [(round(l, 4), p) for l, p in trials[:5]]},
        "score_2021_25": {n: metrics(d[n].to_numpy(), d[n + "_sd"].to_numpy(), d["margin"].to_numpy(float))
                          for n in ("p1", "p1cal", "p2", "p2cal")},
        "score_2021_25_wk1_4": {n: metrics(d.loc[early, n].to_numpy(), d.loc[early, n + "_sd"].to_numpy(),
                                           d.loc[early, "margin"].to_numpy(float)) for n in ("p1", "p2")},
        "paired_2021_25_p2_minus_p1": pair, "stress": stress, "holdout_2026_wk1_7": holdout,
        "adopt_rule": adopt,
    }
    out = PROCESSED / "ratings" / "glicko_p2_eval.json"
    out.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=1, default=str))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
