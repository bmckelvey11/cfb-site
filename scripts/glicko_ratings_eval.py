"""Tune and score Glicko-margin ratings against Elo-MOV, Glicko-1, CFBD Elo and the open.

    python -m scripts.glicko_ratings_eval --tune-seasons 2014-2019 --score-seasons 2021-2025

Tuning reads 2013 (burn-in) through the last tune season only: CRPS for Glicko-margin,
squared error for Elo-MOV, log loss for Glicko-1, closed-form OLS for the HFA-only and
CFBD-Elo rungs. Scoring replays 2013-2025 with every parameter frozen and scores the
score seasons' regular-season games: margin MAE/RMSE/CRPS, win/loss log loss and Brier,
calibration, interval coverage, paired differences with a season-week cluster bootstrap,
an encompassing slope against the Bovada open, and the declared gates G1-G3 with a
one-step parameter stress. Forecast skill only: no wager is graded.

Writes data/processed/ratings/{glicko_snapshots.csv, glicko_eval.json}.
See docs/superpowers/specs/2026-09-24-glicko-ratings-design.md.
"""
from __future__ import annotations

import argparse
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from scripts.glicko_ratings import (
    FBS, FCS, VERSION, EloMov, Glicko1, GlickoMargin, events, run, to_home_margin,
)
from scripts.pregame_replay_audit import _sha256, load_pool
from scripts.weekly_ratings_eval import BOOT_DRAWS, BOOT_SEED, Z_MDE, _cluster_boot, classify_verdict

INF = float("inf")
OPEN_PROVIDER = "Bovada"
SKIP_SEASONS = (2020,)
BURN_IN = 2013
# Final grids: the declared ones plus one outward step on each edge pick of the pre-score
# boundary step (sigma 11, w 1.0, u0 20; K 60, A 30, w_e 1.0; c 0, delta_g 200, w_g 1.0).
GRIDS = {
    "glicko_margin": {"sigma": (11, 13, 15, 17), "tau": (0, 0.75, 1.5), "w": (0.5, 0.7, 0.9, 1.0),
                      "delta": (3, 6, 9), "cap": (24, 38, INF), "hfa": (2, 2.75, 3.5),
                      "u0": (8, 14, 20)},
    "elo_mov": {"k": (20, 30, 40, 50, 60), "hfa": (30, 50, 70, 90), "w": (0.5, 0.67, 0.85, 1.0)},
    "glicko1": {"c": (0, 10, 20, 35), "delta": (50, 100, 150, 200), "hfa": (40, 65, 90),
                "w": (0.5, 0.7, 0.9, 1.0)},
}
# Edges a grid may not be pushed past (spec, "Pre-score boundary step").
LIMITS = {"tau": (0, INF), "cap": (0, INF), "w": (0, 1), "delta": (0, INF), "sigma": (0, INF),
          "u0": (0, INF), "c": (0, INF), "k": (0, INF)}
SIGN_CHECK = {401520154: 1, 401403868: -1, 401628323: 1}  # game_id -> required sign
NEUTRAL_CHECK = 401628323
BUCKETS = {"1-3": (0, 3), "4-7": (4, 7), "8+": (8, 99)}


# --- loading --------------------------------------------------------------------

def load(root: Path, last: int, sources: list[Path]) -> tuple[pd.DataFrame, dict]:
    """games.csv through `last` plus neutral site, subdivision and CFBD Elo from raw JSON.

    FCS-vs-FCS games are dropped: they exist only from 2022, so the tuned regime never saw
    them (spec, "Game set and event clock").
    """
    pool = load_pool(root, last, sources)
    raw = []
    for s in sorted(pool["season"].unique()):
        path = root / "raw" / f"games_{s}.json"
        sources.append(path)
        for r in json.loads(path.read_text(encoding="utf-8")):
            raw.append({"game_id": r["id"], "neutral": bool(r.get("neutralSite")),
                        "home_div": FBS if r.get("homeClassification") == FBS else FCS,
                        "away_div": FBS if r.get("awayClassification") == FBS else FCS,
                        "home_elo": r.get("homePregameElo"), "away_elo": r.get("awayPregameElo")})
    g = pool.merge(pd.DataFrame(raw).drop_duplicates("game_id"), on="game_id", how="left")
    g = g.rename(columns={"home_team": "home", "away_team": "away"})
    g["margin"] = g["home_points"] - g["away_points"]
    g["close"] = to_home_margin(g["spread"])
    g["fbs_fbs"] = (g["home_div"] == FBS) & (g["away_div"] == FBS)
    fcs_fcs = (g["home_div"] == FCS) & (g["away_div"] == FCS)
    drops = {"fcs_vs_fcs_by_season": {int(s): int(n) for s, n in
                                      g[fcs_fcs].groupby("season").size().items()},
             "missing_raw_match": int(g["neutral"].isna().sum())}
    g = g[~fcs_fcs].sort_values(["kickoff", "game_id"]).reset_index(drop=True)
    return g, drops


def load_market(root: Path, seasons: list[int], sources: list[Path]) -> pd.DataFrame:
    """OPEN_PROVIDER's first row per game, as in core: spreadOpen and both moneylines."""
    out: dict[int, tuple] = {}
    for s in seasons:
        path = root / "raw" / f"lines_{s}.json"
        sources.append(path)
        for g in json.loads(path.read_text(encoding="utf-8")):
            for ln in g.get("lines") or []:
                if ln.get("provider") == OPEN_PROVIDER and g["id"] not in out:
                    out[g["id"]] = (ln.get("spreadOpen"), ln.get("homeMoneyline"),
                                    ln.get("awayMoneyline"))
    m = pd.DataFrame.from_dict(out, orient="index", columns=["spread_open", "ml_home", "ml_away"])
    m = m.apply(pd.to_numeric, errors="coerce").rename_axis("game_id").reset_index()
    m["open"] = to_home_margin(m["spread_open"])
    m["ml_p"] = _devig(m["ml_home"], m["ml_away"])
    return m[["game_id", "open", "ml_p"]]


def _devig(home: pd.Series, away: pd.Series) -> pd.Series:
    """Multiplicative de-vig of two American prices; the home side's no-vig probability."""
    def implied(o):
        return np.where(o < 0, -o / (-o + 100.0), 100.0 / (o + 100.0))
    ih, ia = implied(home.to_numpy(float)), implied(away.to_numpy(float))
    return pd.Series(ih / (ih + ia), index=home.index)


def fcs_seed(g: pd.DataFrame) -> float:
    """m0: minus the mean margin by which FBS teams beat FCS teams in the burn-in season."""
    b = g[(g["season"] == BURN_IN) & ~g["fbs_fbs"]]
    fbs_margin = np.where(b["home_div"] == FBS, b["margin"], -b["margin"])
    return round(-float(np.mean(fbs_margin)), 3)


# --- scores ---------------------------------------------------------------------

def crps(mu, sd, y):
    """CRPS of N(mu, sd^2) at y, in the units of y."""
    z = (y - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def logloss(p, o):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return -(o * np.log(p) + (1 - o) * np.log(1 - p))


def calibration(p, o) -> dict:
    """Intercept and slope of a logistic regression of the outcome on logit(p)."""
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    x = np.column_stack([np.ones(len(p)), np.log(p / (1 - p))])
    if np.ptp(x[:, 1]) < 1e-9:                      # a constant forecast has no slope
        return {"intercept": None, "slope": None}
    beta = np.zeros(2)
    for _ in range(50):
        mu = 1 / (1 + np.exp(-x @ beta))
        step = np.linalg.solve(x.T @ (x * (mu * (1 - mu))[:, None]), x.T @ (o - mu))
        beta += step
        if np.abs(step).max() < 1e-10:
            break
    return {"intercept": round(float(beta[0]), 4), "slope": round(float(beta[1]), 4)}


# --- tuning ---------------------------------------------------------------------

def _points(grid: dict) -> list[dict]:
    return [dict(zip(grid, v)) for v in itertools.product(*grid.values())]


def _boundary(grid: dict, pick: dict) -> dict:
    """Axes whose pick is on a grid edge that could still be pushed outward."""
    out = {}
    for k, vals in grid.items():
        lo, hi = LIMITS.get(k, (-INF, INF))
        if len(vals) > 1 and pick[k] == vals[0] and vals[0] > lo:
            out[k] = "low"
        elif len(vals) > 1 and pick[k] == vals[-1] and vals[-1] < hi:
            out[k] = "high"
    return out


def tune(g: pd.DataFrame, seasons: list[int], m0: float, grids: dict = GRIDS) -> dict:
    """Pick each model's parameters on `seasons` (regular season, FBS vs FBS) only."""
    hist = g[g["season"] <= max(seasons)].reset_index(drop=True)
    ev = events(hist)
    mask = (hist["season"].isin(seasons) & (hist["season_type"] == "regular")
            & hist["fbs_fbs"]).to_numpy()
    y = hist["margin"].to_numpy(float)[mask]
    n_mask = mask & (hist["margin"].to_numpy() != 0)    # win/loss scores skip ties
    won = (hist["margin"].to_numpy()[n_mask] > 0).astype(float)
    out = {"seasons": seasons, "n_games": int(mask.sum())}

    losses = []
    for p in _points(grids["glicko_margin"]):
        f = run(GlickoMargin(**p, m0=m0), hist, ev)
        loss = crps(f["mhat"].to_numpy()[mask], np.sqrt(f["S"].to_numpy()[mask]), y).mean()
        losses.append((float(loss), p))
    out["glicko_margin"] = _pick(losses, grids["glicko_margin"], "mean CRPS")

    losses = []
    for p in _points(grids["elo_mov"]):
        d = run(EloMov(**p, m0=m0), hist, ev)["elo_diff"].to_numpy()[mask]
        b = float(d @ y / (d @ d))
        losses.append((float(np.mean((b * d - y) ** 2)), {**p, "b": b}))
    out["elo_mov"] = _pick(losses, grids["elo_mov"], "mean squared error")
    b = out["elo_mov"]["pick"]["b"]
    d = run(EloMov(**_strip(out["elo_mov"]["pick"]), m0=m0), hist, ev)["elo_diff"].to_numpy()[mask]
    out["elo_mov"]["sd"] = float(np.sqrt(np.mean((b * d - y) ** 2)))

    losses = []
    for p in _points(grids["glicko1"]):
        pr = run(Glicko1(**p, m0=m0), hist, ev)["g1_p"].to_numpy()[n_mask]
        losses.append((float(logloss(pr, won).mean()), p))
    out["glicko1"] = _pick(losses, grids["glicko1"], "mean log loss")

    tp = hist[mask]
    home = (~tp["neutral"]).to_numpy(float)
    h_bar = float(tp.loc[~tp["neutral"], "margin"].mean())
    out["hfa_only"] = {"H": h_bar, "sd": float(np.sqrt(np.mean((y - h_bar * home) ** 2)))}
    x = np.column_stack([(tp["home_elo"] - tp["away_elo"]).to_numpy(float), home])
    assert not np.isnan(x).any(), "CFBD Elo missing on a tuning FBS-vs-FBS game"
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    out["cfbd_elo"] = {"b": float(coef[0]), "H": float(coef[1]),
                       "sd": float(np.sqrt(np.mean((x @ coef - y) ** 2)))}
    return out


def _strip(p: dict) -> dict:
    return {k: v for k, v in p.items() if k != "b"}


def _pick(losses: list[tuple], grid: dict, loss_name: str) -> dict:
    losses.sort(key=lambda t: t[0])
    best, pick = losses[0]
    return {"loss": loss_name, "pick": pick, "best_loss": round(best, 5),
            "grid_points": len(losses), "boundary": _boundary(grid, pick),
            "top10": [{"loss": round(v, 5), **p} for v, p in losses[:10]]}


# --- scoring --------------------------------------------------------------------

def forecasts(g: pd.DataFrame, tuned: dict, m0: float, glk: dict | None = None,
              snaps: list | None = None) -> pd.DataFrame:
    """Every rung's forecast for every game in `g`, parameters frozen from `tuned`."""
    ev = events(g)
    glk = glk or tuned["glicko_margin"]["pick"]
    f = run(GlickoMargin(**glk, m0=m0), g, ev, snaps)
    out = pd.DataFrame({"glk": f["mhat"], "glk_sd": np.sqrt(f["S"]), "rd": np.sqrt(f["rd2"])})
    out["glk_p"] = norm.cdf(out["glk"] / out["glk_sd"])

    em = tuned["elo_mov"]
    e = run(EloMov(**_strip(em["pick"]), m0=m0), g, ev)
    out["elo"], out["elo_sd"], out["elo_p"] = em["pick"]["b"] * e["elo_diff"], em["sd"], e["elo_p"]
    out["g1_p"] = run(Glicko1(**tuned["glicko1"]["pick"], m0=m0), g, ev)["g1_p"]

    home = (~g["neutral"]).astype(float)
    ce, hf = tuned["cfbd_elo"], tuned["hfa_only"]
    out["cfbd"] = ce["b"] * (g["home_elo"] - g["away_elo"]) + ce["H"] * home
    out["cfbd_sd"], out["cfbd_p"] = ce["sd"], norm.cdf(out["cfbd"] / ce["sd"])
    out["hfa"], out["hfa_sd"] = hf["H"] * home, hf["sd"]
    out["hfa_p"] = norm.cdf(out["hfa"] / hf["sd"])
    return out


def scored_frame(g, fc, market, seasons) -> tuple[pd.DataFrame, dict]:
    d = pd.concat([g, fc], axis=1)
    d = d[d["season"].isin(seasons) & (d["season_type"] == "regular")]
    d = d.merge(market, on="game_id", how="left")
    d["primary"] = d["fbs_fbs"] & d["open"].notna()
    p = d[d["primary"]]
    s_mkt = float(np.sqrt(np.mean((p["open"] - p["margin"]) ** 2)))
    s_close = float(np.sqrt(np.mean((p["close"] - p["margin"]) ** 2)))
    d["open_sd"], d["open_p"] = s_mkt, norm.cdf(d["open"] / s_mkt)
    d["close_sd"], d["close_p"] = s_close, norm.cdf(d["close"] / s_close)
    d["bucket"] = pd.cut(d["week"], [-1, 3, 7, 99], labels=list(BUCKETS)).astype(str)
    return d, {"s_mkt_open": s_mkt, "s_close": s_close}


MARGIN_COLS = ["hfa", "cfbd", "elo", "glk", "open", "close"]
PROB_COLS = ["hfa", "cfbd", "elo", "g1", "glk", "open", "close"]


def margin_table(d: pd.DataFrame, cols=MARGIN_COLS) -> dict:
    out = {}
    for c in cols:
        e = d[c] - d["margin"]
        out[c] = {"n": int(e.notna().sum()), "mae": round(float(e.abs().mean()), 3),
                  "rmse": round(float(np.sqrt((e ** 2).mean())), 3),
                  "bias": round(float(e.mean()), 3),
                  "crps": round(float(crps(d[c], d[f"{c}_sd"], d["margin"]).mean()), 3)}
    return out


def prob_table(d: pd.DataFrame, cols=PROB_COLS) -> dict:
    d = d[d["margin"] != 0]
    o = (d["margin"] > 0).to_numpy(float)
    out = {}
    for c in cols:
        p = d[f"{c}_p"].to_numpy(float)
        out[c] = {"n": len(p), "logloss": round(float(logloss(p, o).mean()), 4),
                  "brier": round(float(np.mean((p - o) ** 2)), 4), **calibration(p, o)}
    return out


def closing_ml(d: pd.DataFrame) -> dict:
    """Secondary, not decision-time: Bovada's de-vigged moneyline against Glicko-margin."""
    d = d[(d["margin"] != 0) & d["ml_p"].notna()]
    return {"label": "not decision-time: Bovada moneyline, no capture time, treated as closing",
            **prob_table(d, ["ml", "glk", "open"])}


def _loss(d: pd.DataFrame, c: str, kind: str) -> pd.Series:
    if kind == "mae":
        return (d[c] - d["margin"]).abs()
    if kind == "crps":
        return crps(d[c], d[f"{c}_sd"], d["margin"])
    return pd.Series(logloss(d[f"{c}_p"].to_numpy(float), (d["margin"] > 0).to_numpy(float)),
                     index=d.index)


def paired(d: pd.DataFrame, a: str, b: str, kind: str) -> dict:
    """loss(a) - loss(b) on the same games; negative means `a` is better."""
    if kind == "logloss":
        d = d[d["margin"] != 0]
    diff = _loss(d, a, kind) - _loss(d, b, kind)
    boot, sums = _cluster_boot(d, {"d": diff, "n": pd.Series(1.0, index=d.index)})
    draws = boot["d"] / boot["n"]
    lo, hi = np.percentile(draws, [2.5, 97.5])
    se = float(draws.std(ddof=1))
    by_season = {int(s): round(float(v), 4) for s, v in diff.groupby(d["season"]).mean().items()}
    return {"kind": kind, "n": int(len(d)), "n_clusters": int(len(sums)),
            "diff": round(float(diff.mean()), 4), "ci95": [round(float(lo), 4), round(float(hi), 4)],
            "se": round(se, 4), "mde80": round(Z_MDE * se, 4), "by_season": by_season,
            "verdict": classify_verdict(lo, hi, list(by_season.values()))}


def encompassing(d: pd.DataFrame, f: str) -> dict:
    """OLS slope beta in (margin - open) = a + beta (forecast - open) + e."""
    x, y = d[f] - d["open"], d["margin"] - d["open"]
    stats = {"n": pd.Series(1.0, index=d.index), "x": x, "y": y, "xx": x * x, "xy": x * y}
    boot, _ = _cluster_boot(d, stats)

    def slope(n, sx, sy, sxx, sxy):
        return (n * sxy - sx * sy) / (n * sxx - sx * sx)

    beta = slope(len(d), x.sum(), y.sum(), (x * x).sum(), (x * y).sum())
    lo, hi = np.percentile(slope(boot["n"], boot["x"], boot["y"], boot["xx"], boot["xy"]),
                           [2.5, 97.5])
    return {"beta": round(float(beta), 4), "ci95": [round(float(lo), 4), round(float(hi), 4)]}


def coverage(d: pd.DataFrame) -> dict:
    z = (d["margin"] - d["glk"]).abs() / d["glk_sd"]

    def cov(zz):
        return {"n": int(len(zz)), "cov68": round(float((zz <= 1).mean()), 4),
                "cov95": round(float((zz <= 1.96).mean()), 4)}

    q = pd.qcut(d["rd"], 5, labels=[f"q{i}" for i in range(1, 6)])
    by_q = {str(k): {**cov(v), "rd_range": [round(float(d.loc[v.index, "rd"].min()), 2),
                                            round(float(d.loc[v.index, "rd"].max()), 2)]}
            for k, v in z.groupby(q, observed=True)}
    return {"pooled": cov(z), "by_rd_quintile": by_q}


def gates(d: pd.DataFrame) -> dict:
    g1_crps, g1_mae = paired(d, "glk", "elo", "crps"), paired(d, "glk", "elo", "mae")
    enc, cov = encompassing(d, "glk"), coverage(d)
    pooled, qs = cov["pooled"], cov["by_rd_quintile"].values()
    g3 = (0.65 <= pooled["cov68"] <= 0.71 and 0.93 <= pooled["cov95"] <= 0.97
          and all(0.90 <= q["cov95"] <= 0.98 for q in qs))
    return {"G1": {"pass": g1_crps["verdict"] == "improves" and g1_mae["verdict"] != "worse",
                   "crps": g1_crps, "mae_guard": g1_mae},
            "G2": {"pass": enc["ci95"][0] > 0, "encompassing": enc},
            "G3": {"pass": bool(g3), "coverage": cov}}


def stress(g, tuned, m0, market, seasons, base: dict) -> dict:
    """Each Glicko-margin parameter moved to its neighbouring grid values, one at a time."""
    grid, pick = GRIDS["glicko_margin"], tuned["glicko_margin"]["pick"]
    runs = {}
    for k, vals in grid.items():
        i = vals.index(pick[k])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                p = {**pick, k: vals[j]}
                d = scored_frame(g, forecasts(g, tuned, m0, glk=p), market, seasons)[0]
                gt = gates(d[d["primary"]])
                runs[f"{k}={vals[j]}"] = {
                    "G1_crps_verdict": gt["G1"]["crps"]["verdict"], "G1_pass": gt["G1"]["pass"],
                    "G2_beta": gt["G2"]["encompassing"], "G2_pass": gt["G2"]["pass"]}
    stable = all(r["G1_pass"] == base["G1"]["pass"] and r["G2_pass"] == base["G2"]["pass"]
                 and r["G1_crps_verdict"] == base["G1"]["crps"]["verdict"] for r in runs.values())
    return {"variants": runs, "n_variants": len(runs), "stable": stable}


def sign_check(g: pd.DataFrame, fc: pd.DataFrame | None = None) -> list[str]:
    """Problems with the declared sign-check games; empty means pass."""
    bad = []
    for gid, want in SIGN_CHECK.items():
        row = g[g["game_id"] == gid]
        if row.empty:
            bad.append(f"{gid}: not in the pool")
            continue
        r = row.iloc[0]
        vals = {"-spread": r["close"], "margin": r["margin"]}
        if fc is not None:
            vals["M_hat"] = fc.loc[row.index[0], "glk"]
        bad += [f"{gid}: {k}={v}" for k, v in vals.items() if np.sign(v) != want]
        if gid == NEUTRAL_CHECK and not r["neutral"]:
            bad.append(f"{gid}: expected a neutral site")
    return bad


def score(d: pd.DataFrame) -> dict:
    p = d[d["primary"]]
    by = {"season": {int(s): margin_table(x) for s, x in p.groupby("season")},
          "bucket": {b: {"margin": margin_table(x), "winloss": prob_table(x)}
                     for b, x in p.groupby("bucket")}}
    pairs = {f"glk_vs_{c}_{k}": paired(p, "glk", c, k)
             for c in ("open", "elo", "cfbd", "hfa") for k in ("mae", "crps")}
    pairs |= {f"{c}_vs_open_mae": paired(p, c, "open", "mae") for c in ("elo", "cfbd")}
    pairs |= {f"glk_vs_{c}_logloss": paired(p, "glk", c, "logloss") for c in ("g1", "open")}
    sec_all = d[d["fbs_fbs"]]
    sec_fcs = d[~d["fbs_fbs"]]
    rungs = [c for c in MARGIN_COLS if c not in ("open", "cfbd")]
    return {
        "populations": {
            "scored_regular_games": int(len(d)), "primary": int(len(p)),
            "primary_clusters": int(p.groupby(["season", "week"]).ngroups),
            "primary_rule": f"FBS vs FBS, regular season, {OPEN_PROVIDER} spreadOpen present",
            "fbs_fbs_any_open": int(len(sec_all)), "fbs_fcs": int(len(sec_fcs))},
        "primary": {
            "margin": margin_table(p), "winloss": prob_table(p), "paired": pairs,
            "encompassing_vs_open": {c: encompassing(p, c) for c in ("glk", "elo", "cfbd")},
            "coverage": coverage(p), "by_season": by["season"], "by_bucket": by["bucket"],
            "closing_moneyline": closing_ml(p)},
        "secondary": {
            "fbs_fbs_no_open_requirement": {"margin": margin_table(sec_all, rungs + ["cfbd"]),
                                            "glk_vs_elo_crps": paired(sec_all, "glk", "elo", "crps")},
            "fbs_vs_fcs": {"margin": margin_table(sec_fcs, rungs),
                           "note": "close is not decision-time"}},
    }


# --- CLI ------------------------------------------------------------------------

def _range(text: str) -> list[int]:
    a, _, b = text.partition("-")
    return list(range(int(a), int(b or a) + 1))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tune-seasons", type=_range, default=_range("2014-2019"))
    ap.add_argument("--score-seasons", type=_range, default=_range("2021-2025"))
    args = ap.parse_args(argv)

    from cfb_paths import DATA_ROOT, PROCESSED

    tune_seasons = [s for s in args.tune_seasons if s not in SKIP_SEASONS]
    score_seasons = [s for s in args.score_seasons if s not in SKIP_SEASONS]
    sources: list[Path] = []
    g, drops = load(DATA_ROOT, max(score_seasons), sources)
    bad = sign_check(g)
    if bad:
        print("sign check failed before fitting:", *bad, sep="\n  ")
        return 1
    m0 = fcs_seed(g)
    tuned = tune(g, tune_seasons, m0)

    snaps: list = []
    fc = forecasts(g, tuned, m0, snaps=snaps)
    bad = sign_check(g, fc)
    if bad:
        print("sign check failed on M_hat; no results written:", *bad, sep="\n  ")
        return 1
    market = load_market(DATA_ROOT, score_seasons, sources)
    d, market_sd = scored_frame(g, fc, market, score_seasons)
    results = score(d)
    verdict = gates(d[d["primary"]])
    stressed = stress(g, tuned, m0, market, score_seasons, verdict)
    go = all(v["pass"] for v in verdict.values()) and stressed["stable"]

    out_dir = PROCESSED / "ratings"
    out_dir.mkdir(parents=True, exist_ok=True)
    snap = pd.DataFrame(snaps, columns=["season", "week", "t", "team", "subdivision", "r", "u",
                                        "n_games"])
    snap.insert(2, "as_of_ts", pd.to_datetime(snap.pop("t"), unit="D", utc=True).map(
        lambda ts: ts.isoformat()))
    snap.assign(version=VERSION).to_csv(out_dir / "glicko_snapshots.csv", index=False)

    grid_points = {k: tuned[k]["grid_points"] for k in GRIDS}
    manifest = {
        "version": VERSION,
        "command": "python -m scripts.glicko_ratings_eval --tune-seasons "
                   f"{tune_seasons[0]}-{tune_seasons[-1]} --score-seasons "
                   f"{score_seasons[0]}-{score_seasons[-1]}",
        "code_sha256": {p: _sha256(Path(__file__).parent / p)
                        for p in ("glicko_ratings.py", "glicko_ratings_eval.py",
                                  "pregame_replay_audit.py", "weekly_ratings_eval.py")},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_root": str(DATA_ROOT),
        "seasons": {"burn_in": BURN_IN, "tune": tune_seasons, "score": score_seasons,
                    "skipped": list(SKIP_SEASONS), "state_runs_through": max(score_seasons)},
        "market": {"provider": OPEN_PROVIDER, "field": "spreadOpen", "sd": market_sd,
                   "note": "open sd fit in sample on primary games (market best case); "
                           "no decision-time moneyline exists"},
        "definitions": {"clock": "forecast at week cutoff; results update at kickoff",
                        "fcs_policy": "FBS-vs-FBS and FBS-vs-FCS in state; FCS-vs-FCS dropped",
                        "scored": "regular season only; postseason updates state"},
        "drops": drops,
        "seeds": {"m0_fcs": m0},
        "grids": {k: {a: list(v) for a, v in grid.items()} for k, grid in GRIDS.items()},
        "tuning": tuned,
        "trial_count": {"tuning_grid_points": grid_points,
                        "closed_form_fits": 2,
                        "total_tuning": sum(grid_points.values()) + 2,
                        "stress_variants": stressed["n_variants"], "scoring_runs": 1},
        "sign_check": {"games": SIGN_CHECK, "result": "pass"},
        "gates": verdict, "stress": stressed, "go": go,
        "bootstrap": {"unit": "season-week", "draws": BOOT_DRAWS, "seed": BOOT_SEED,
                      "interval": "percentile 95%", "mde": "2.8 x bootstrap SE (80% power)"},
        "results": results,
        "source_files": [{"path": str(p), "sha256": _sha256(p)} for p in dict.fromkeys(sources)],
    }
    out = out_dir / "glicko_eval.json"
    out.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")

    print(f"picks: {json.dumps({k: tuned[k]['pick'] for k in GRIDS}, default=str)}")
    print(json.dumps(results["primary"]["margin"], indent=1))
    for k, v in verdict.items():
        print(f"{k}: {'pass' if v['pass'] else 'FAIL'}")
    print(f"stress stable: {stressed['stable']}  ->  {'GO' if go else 'NO-GO'}")
    print(f"manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
