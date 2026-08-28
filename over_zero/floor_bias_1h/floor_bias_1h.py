"""Floor Bias model -- FIRST HALF extension.

The full-game Floor Bias model (../v1) exploits left-censoring of team points at
0: realized totals skew up -> bet the over. Halves have ~half the expected
points, so each team's mean sits much closer to the 0 floor; censoring binds
harder (13.8% of 1H underdog scores are 0, vs 3.5% full game) and the expected
censoring bias is ~2.3x larger. So the over edge should be stronger on 1H totals.

DATA REALITY: CFBD provides 1H scores (quarter line-scores, 1H = Q1+Q2) but NOT
1H betting lines. This module is therefore built to run two ways:

  * REAL lines  -- pass --half-lines path.csv (columns: game_id,half_spread,
    half_total). The model then runs a TRUE backtest on the real 1H market.
  * APPROX lines -- default. The 1H line is taken as frac * game line. With
    total_frac = spread_frac = 0.5 this is exactly the paper's latent-symmetric
    prediction (implied 1H team points = full implied points / 2). NOTE: actual
    1H scoring runs ~1.1 pt ABOVE half the game, so a 0.5 total_frac lets that
    structural excess inflate the apparent over edge on top of true censoring.
    Set total_frac ~ 0.52 to de-bias the half-scoring excess and isolate the
    censoring effect. Treat APPROX numbers as mechanism illustration, not a
    validated edge.

Shared estimator core (Tobit, censoring bias, probit, Kelly) imported from ../v2.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v2"))
from models_v2 import (  # noqa: E402
    censoring_bias,
    implied_team_points,
    kelly_bankroll_roi,
    log_likelihood_ratio,
    pick_line,
    probit_win_v2,
    tobit_left_censored_v2,
)

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


# ---------------------------------------------------------------------------
# Data loading: join 1H scores (games) with a 1H line (real CSV or approx)
# ---------------------------------------------------------------------------
@dataclass
class Data1H:
    half_spread_est: np.ndarray   # underdog perspective, >= 0
    half_total_est: np.ndarray
    fav_1h: np.ndarray            # favorite first-half points
    dog_1h: np.ndarray            # underdog first-half points
    source: str                   # "real" or "approx(frac=...)"

    def over_diag(self):
        """Baseline 1H over rate (%), pushes excluded."""
        nu = (self.fav_1h + self.dog_1h) - self.half_total_est
        keep = nu != 0
        return (nu[keep] > 0).mean() * 100


def _read_half_lines(path):
    """game_id -> (half_spread, half_total) from a user CSV."""
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                out[int(row["game_id"])] = (
                    float(row["half_spread"]), float(row["half_total"]))
            except (KeyError, ValueError, TypeError):
                continue
    return out


def load_1h(seasons, raw_dir=RAW_DIR, half_lines_csv=None,
            total_frac=0.5, spread_frac=0.5):
    """Build first-half dataset.

    Favorite/underdog are assigned by the full-game spread sign (the only spread
    we have when approximating). 1H points = sum of the first two quarter
    line-scores.
    """
    real = _read_half_lines(half_lines_csv) if half_lines_csv else None
    hs, ht, f1, d1 = [], [], [], []

    for season in seasons:
        gpath = Path(raw_dir) / f"games_{season}.json"
        lpath = Path(raw_dir) / f"lines_{season}.json"
        if not gpath.exists() or not lpath.exists():
            print(f"  (missing raw files for {season})")
            continue

        # game spread/total per id (consensus or first book with both fields).
        game_line = {}
        for x in json.loads(lpath.read_text(encoding="utf-8")):
            picked = pick_line(x)
            if picked is not None:
                game_line[x["id"]] = picked

        for g in json.loads(gpath.read_text(encoding="utf-8")):
            gid = g.get("id")
            hl, al = g.get("homeLineScores"), g.get("awayLineScores")
            if gid not in game_line or not hl or not al or len(hl) < 2 or len(al) < 2:
                continue
            if None in hl[:2] or None in al[:2]:     # null quarter entries
                continue
            game_spread, game_total = game_line[gid]
            if game_spread == 0:
                continue
            home_1h, away_1h = sum(hl[:2]), sum(al[:2])

            # 1H line: real if supplied, else fraction of the game line.
            if real is not None:
                if gid not in real:
                    continue
                half_spread, half_total = real[gid]
                if half_spread == 0:
                    continue
                fav_perspective = half_spread < 0
            else:
                half_spread = game_spread * spread_frac
                half_total = game_total * total_frac
                fav_perspective = game_spread < 0

            # favorite = negative-spread side.
            if fav_perspective:
                fav_pts, dog_pts = home_1h, away_1h
            else:
                fav_pts, dog_pts = away_1h, home_1h

            hs.append(abs(half_spread))
            ht.append(half_total)
            f1.append(float(fav_pts))
            d1.append(float(dog_pts))

    src = "real" if real is not None else f"approx(total_frac={total_frac},spread_frac={spread_frac})"
    return Data1H(np.array(hs), np.array(ht), np.array(f1), np.array(d1), src)


# ---------------------------------------------------------------------------
# Pipeline (mirrors v1, on 1H quantities)
# ---------------------------------------------------------------------------
@dataclass
class Pipeline1H:
    tobit_dog: object
    tobit_fav: object
    probit: object
    bias_totals: np.ndarray
    over_wins: np.ndarray
    keep: np.ndarray


def fit_1h(data: Data1H):
    dog_est, fav_est = implied_team_points(data.half_spread_est, data.half_total_est)
    tob_dog = tobit_left_censored_v2(data.dog_1h, dog_est)
    tob_fav = tobit_left_censored_v2(data.fav_1h, fav_est)
    _, bias_totals = censoring_bias(dog_est, fav_est, tob_dog.sigma, tob_fav.sigma)

    nu = (data.fav_1h + data.dog_1h) - data.half_total_est
    keep = nu != 0
    over_wins = (nu > 0).astype(float)
    probit = probit_win_v2(over_wins[keep], bias_totals[keep])
    return Pipeline1H(tob_dog, tob_fav, probit, bias_totals, over_wins, keep)


@dataclass
class Strat1H:
    threshold: float
    n_bets: int
    win_rate: float
    unit_return: float
    qtr_kelly_roi: float
    lr_breakeven: tuple


def strategy_1h(fit: Pipeline1H, threshold=1.0):
    sel = fit.keep & (fit.bias_totals > threshold)
    w = fit.over_wins[sel]
    n = w.size
    if n == 0:
        return Strat1H(threshold, 0, 0.0, 0.0, 0.0, (float("nan"), float("nan")))
    wins = int(w.sum())
    wp = fit.probit.win_prob(fit.bias_totals[sel])
    return Strat1H(
        threshold=threshold, n_bets=n, win_rate=wins / n,
        unit_return=(wins * 100 - (n - wins) * 110) / (n * 110),
        qtr_kelly_roi=kelly_bankroll_roi(w, wp, 0.25),
        lr_breakeven=log_likelihood_ratio(wins, n, q=0.5238),
    )


def kfold_1h(data: Data1H, k=5, hurdle=0.5238, threshold=1.0, seed=0):
    """Train pipeline on k-1 folds, bet 1H over on held-out fold where the probit
    win prob > hurdle AND bias > threshold. Returns per-fold (n, wins, unit%)."""
    n = data.half_spread_est.size
    rng = np.random.default_rng(seed)
    folds = np.array_split(rng.permutation(n), k)

    def sub(idx):
        return Data1H(data.half_spread_est[idx], data.half_total_est[idx],
                      data.fav_1h[idx], data.dog_1h[idx], data.source)

    rows = []
    for i in range(k):
        te = folds[i]
        tr = np.concatenate([folds[j] for j in range(k) if j != i])
        fit = fit_1h(sub(tr))

        d = sub(te)
        dog_est, fav_est = implied_team_points(d.half_spread_est, d.half_total_est)
        _, bias = censoring_bias(dog_est, fav_est, fit.tobit_dog.sigma, fit.tobit_fav.sigma)
        wp = fit.probit.win_prob(bias)
        nu = (d.fav_1h + d.dog_1h) - d.half_total_est
        bet = (nu != 0) & (wp > hurdle) & (bias > threshold)
        nb = int(bet.sum())
        if nb == 0:
            rows.append((0, 0, 0.0))
            continue
        w = (nu[bet] > 0).astype(float)
        wins = int(w.sum())
        rows.append((nb, wins, (wins * 100 - (nb - wins) * 110) / (nb * 110)))
    return rows
