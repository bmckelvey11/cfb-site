"""Does PT's `phwin` beat real moneyline prices?

EXPLORATORY. Not registered in `prereg-line-movement.md`. Follows `eval_phwin_accuracy.py`,
which found phwin is a real forecast (AUC 0.80) but is beaten and encompassed by the spread.
That study could not price anything -- the PT panel carries no moneyline. This one joins the
warehouse's moneylines and asks the betting question directly.

TWO ARMS ON THE IDENTICAL BET SET. phwin is encompassed by the spread, so "phwin beats the
moneyline" would be confounded with "the spread beats the moneyline". Both are therefore run:

  phwin arm    bet when phwin says the offered price is +EV
  spread arm   same rule, but the probability comes from a logit of home-win on the panel's
               `line`, fit WALK-FORWARD on strictly prior seasons

If both arms profit, the edge belongs to the spread, not to phwin.

Orientation: `base.load()` orients `y` and `line` to PT's home team, which is not always CFBD's
home team. `moneyline_home` is CFBD's. The swap is applied on `orientation_flipped == 1` and
asserted to have fired.

Prices: American odds are converted to decimal per book BEFORE any aggregation -- averaging
American odds across the +/-100 discontinuity is meaningless. Best price is the primary series
(it is what a shopper gets) but the book panel thickens over time, so per-season book counts are
printed beside it and the median series is reported as the stable comparison.

    python research/spread/scripts/eval_phwin_moneyline.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402

OUT = base.OUT_DIR / "phwin_moneyline.json"
N_BOOT = 2000
RNG = np.random.default_rng(20260917)
EV_THRESHOLDS = [0.0, 0.02]


def american_to_decimal(a) -> np.ndarray:
    a = np.asarray(a, float)
    return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def logistic(x):
    return 1.0 / (1.0 + np.exp(-x))


def fit_logit(x: np.ndarray, y: np.ndarray, iters: int = 50) -> np.ndarray:
    X = np.column_stack([np.ones(len(x)), x])
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = logistic(X @ b).clip(1e-9, 1 - 1e-9)
        W = p * (1 - p)
        step = np.linalg.solve((X * W[:, None]).T @ X + 1e-8 * np.eye(X.shape[1]), X.T @ (y - p))
        b += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return b


def cluster_ci(x: np.ndarray, clusters: np.ndarray, n_boot: int = N_BOOT):
    """Season-cluster bootstrap CI for a mean."""
    uniq = np.unique(clusters)
    if len(uniq) < base.MIN_CLUSTERS or len(x) == 0:
        return float("nan"), float("nan")
    idx = {c: np.flatnonzero(clusters == c) for c in uniq}
    vals = []
    for _ in range(n_boot):
        take = np.concatenate([idx[c] for c in RNG.choice(uniq, len(uniq), replace=True)])
        if len(take):
            vals.append(x[take].mean())
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def grade(p_model, dec_h, dec_a, won_home, seasons, thr):
    """Bet whichever side the model makes +EV at the offered price. ROI per unit staked."""
    ev_h = p_model * (dec_h - 1) - (1 - p_model)
    ev_a = (1 - p_model) * (dec_a - 1) - p_model
    take_a = (ev_a > thr) & (ev_a >= ev_h)
    take_h = (ev_h > thr) & ~take_a
    m = take_h | take_a
    if m.sum() == 0:
        return {"bets": 0}
    win = np.where(take_h[m], won_home[m] == 1, won_home[m] == 0)
    dec = np.where(take_h[m], dec_h[m], dec_a[m])
    profit = np.where(win, dec - 1, -1.0)
    lo, hi = cluster_ci(profit, seasons[m])
    return {"bets": int(m.sum()), "roi": float(profit.mean()), "lo": lo, "hi": hi,
            "win_rate": float(win.mean()), "home_share": float(take_h[m].mean())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-season", type=int, default=2021)
    ap.add_argument("--to-season", type=int, default=2025)
    ap.add_argument("--cluster", choices=["season", "week"], default=None,
                    help="bootstrap cluster level; default season, auto-falls to week when "
                         "fewer than MIN_CLUSTERS seasons are in range")
    a = ap.parse_args()

    df, _ = base.load()
    d = df[df.phwin.notna() & df.line.notna()
           & df.season.between(a.from_season, a.to_season)].copy()

    con = duckdb.connect(str(base.cfb_paths.DB_PATH), read_only=True)
    raw = con.execute(
        "select l.game_id, l.provider_key, l.moneyline_home, l.moneyline_away "
        "from core.fact_game_line l join core.fact_game f using(game_id) "
        "where f.season between ? and ? "
        "and l.moneyline_home is not null and l.moneyline_away is not null",
        [a.from_season, a.to_season]).df()
    raw["dec_h_cfbd"] = american_to_decimal(raw.moneyline_home)
    raw["dec_a_cfbd"] = american_to_decimal(raw.moneyline_away)

    agg = raw.groupby("game_id").agg(
        n_books=("provider_key", "size"),
        best_h_cfbd=("dec_h_cfbd", "max"), best_a_cfbd=("dec_a_cfbd", "max"),
        med_h_cfbd=("dec_h_cfbd", "median"), med_a_cfbd=("dec_a_cfbd", "median")).reset_index()
    d = d.merge(agg, on="game_id", how="inner")

    f = (d.orientation_flipped == 1).to_numpy()
    assert f.sum() > 0, "no flipped rows in the joined sample -- the swap check never fired"
    for tag in ("best", "med"):
        dh_c = d[tag + "_h_cfbd"].to_numpy(float)
        da_c = d[tag + "_a_cfbd"].to_numpy(float)
        d[tag + "_h"] = np.where(f, da_c, dh_c)    # PT-home side
        d[tag + "_a"] = np.where(f, dh_c, da_c)

    y = (d.y > 0).astype(int).to_numpy()           # PT-home won outright
    season_arr = d.season.to_numpy(int)
    level = a.cluster or ("season" if d.season.nunique() >= base.MIN_CLUSTERS else "week")
    # `wk` is season*100 + pt_week, already built by base.load()
    seasons = season_arr if level == "season" else d.wk.to_numpy(int)
    print("bootstrap clusters: %s (%d distinct)" % (level, len(np.unique(seasons))))
    phwin = d.phwin.to_numpy(float)
    line = d.line.to_numpy(float)

    out = {"n": len(d), "seasons": [int(season_arr.min()), int(season_arr.max())],
           "cluster_level": level, "n_clusters": int(len(np.unique(seasons))),
           "n_flipped": int(f.sum()), "base_home_win_rate": float(y.mean())}
    print("n = %d games (%d-%d), %d orientation-flipped and swapped"
          % (len(d), season_arr.min(), season_arr.max(), int(f.sum())))
    print("PT-home win rate %.4f" % y.mean())
    print("")
    print("  season   games   mean books/game")
    per = d.groupby("season").agg(games=("game_id", "size"), books=("n_books", "mean"))
    for s, r in per.iterrows():
        print("  %d  %7d   %8.2f" % (int(s), int(r.games), r.books))
    out["per_season"] = [{"season": int(s), "games": int(r.games), "mean_books": float(r.books)}
                         for s, r in per.iterrows()]

    over = 1 / d.med_h.to_numpy(float) + 1 / d.med_a.to_numpy(float)
    print("")
    print("median-price overround: mean %.4f  median %.4f  (1.00 = no vig)"
          % (over.mean(), np.median(over)))
    out["overround_mean"] = float(over.mean())

    # spread arm: walk-forward logit of home-win on the panel's own (PT-oriented) line
    mkt = np.full(len(d), np.nan)
    for s in sorted(set(season_arr)):
        hist = df[df.line.notna() & (df.season < s)]
        if len(hist) < 200:
            continue
        b = fit_logit(hist.line.to_numpy(float), (hist.y > 0).astype(int).to_numpy())
        te = season_arr == s
        mkt[te] = logistic(b[0] + b[1] * line[te])
    assert np.isfinite(mkt).all(), "spread arm has unscored games"

    for price, tag in [("best", "BEST price across books"), ("med", "MEDIAN price")]:
        dh, da = d[price + "_h"].to_numpy(float), d[price + "_a"].to_numpy(float)
        print("")
        print("=== %s ===" % tag)
        for thr in EV_THRESHOLDS:
            r_ph = grade(phwin, dh, da, y, seasons, thr)
            r_mk = grade(mkt, dh, da, y, seasons, thr)
            out["%s_ev%g" % (price, thr)] = {"phwin": r_ph, "spread": r_mk}
            for nm, r in [("phwin ", r_ph), ("spread", r_mk)]:
                if r["bets"] == 0:
                    print("  EV>%2.0f%%  %s: no bets" % (thr * 100, nm))
                    continue
                print("  EV>%2.0f%%  %s: %5d bets  ROI %+.4f [%+.4f, %+.4f]  win %.3f  home %.2f"
                      % (thr * 100, nm, r["bets"], r["roi"], r["lo"], r["hi"],
                         r["win_rate"], r["home_share"]))

    # Per-season, best price, EV>2%. The book panel thickens from 1.00 to 6.56 books a game, so
    # "best of N" is not one series across seasons; a pooled best-price ROI can be line shopping
    # appearing only where there are books to shop. This prints the per-season path behind it.
    print("")
    print("PER SEASON -- best price, EV>2%%, the series behind the pooled number")
    print("  season  books/gm   phwin bets      ROI    spread bets      ROI")
    rows = []
    dh, da = d["best_h"].to_numpy(float), d["best_a"].to_numpy(float)
    for s in sorted(set(season_arr)):
        m0 = season_arr == s
        rec = {"season": int(s), "mean_books": float(d.n_books[m0].mean())}
        cells = []
        for nm, pm in [("phwin", phwin), ("spread", mkt)]:
            r = grade(pm[m0], dh[m0], da[m0], y[m0], seasons[m0], 0.02)
            rec[nm] = r
            cells.append("%5d  %+.4f" % (r["bets"], r["roi"]) if r["bets"] else "   no bets    ")
        rows.append(rec)
        print("  %d    %5.2f      %s    %s" % (int(s), rec["mean_books"], cells[0], cells[1]))
    out["per_season_best_ev2"] = rows
    print("  Per-season CIs are omitted: one season is one cluster, so they are not inference.")

    OUT.write_text(json.dumps(out, indent=2))
    print("")
    print("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
