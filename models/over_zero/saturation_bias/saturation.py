"""Saturation Bias model -- the ceiling-side mirror of Arscott (2022).

Arscott's censoring bias comes from the FLOOR: team points can't go below 0, so
realized totals are biased UP -> bet the over. v1-v3 in this repo confirm it.

This model explores the OTHER side. Scoring has no hard cap, but a SOFT ceiling:
finite drives/clock cap realized points, and very high totals lines overshoot
(the >66 under-rate of 54% in the v3 exploration). Model each team's points as
right-saturated at a ceiling C:

    observed = min(C, latent),   latent ~ N(teamEst, sigma^2)

The expected bias mirrors the floor case (derivation by reflecting X -> C-X):

    saturationBiasTeam = E[min(C,X)] - mu = -[ sigma*phi(d/sigma) - d*Phi(-d/sigma) ]
        where d = C - mu   (distance of expected points below the ceiling)

This is <= 0 and only material when mu is within ~1-2 sigma of C, i.e. for
high-scoring teams. Summed over both teams:

    saturationBiasTotals = saturationBiasTeam(fav) + saturationBiasTeam(dog)  <= 0

so realized totals are biased DOWN -> the under is underpriced where this bias
is large (high totals lines).

CRITICAL DIFFERENCE from the paper: the floor at 0 is *observed* -- real games
pile up at 0 points, so a left-censored Tobit identifies it. There is NO pile-up
at any scoring ceiling, so C is NOT identified by the score distribution. Here C
is a hyperparameter chosen by out-of-sample predictive fit (grid search on OOS
log-loss). That makes this model weaker / more speculative than the paper's, by
construction. Treat results as a lead, not a proven edge.

Shared core (Tobit sigmas, loader helpers, Kelly) imported from ../v2.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import statsmodels.api as sm
from scipy.stats import norm as NORM

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v2"))
from models_v2 import (  # noqa: E402
    implied_team_points,
    kelly_bankroll_roi,
    load_from_raw,
    log_likelihood_ratio,
    tobit_left_censored_v2,
)


# ---------------------------------------------------------------------------
# Saturation (ceiling) bias
# ---------------------------------------------------------------------------
def _floor_bias(mu, sigma):
    """Left-censoring-at-0 bias, E[max(0,X)]-mu >= 0 (paper's quantity)."""
    z = mu / sigma
    return sigma * NORM.pdf(z) - mu * NORM.cdf(-z)


def saturation_team_bias(mu, sigma, ceiling):
    """E[min(C,X)] - mu  <= 0.  Mirror of the floor bias at distance d = C - mu."""
    d = ceiling - np.asarray(mu, float)
    return -_floor_bias(d, sigma)


def saturation_totals(dog_est, fav_est, sigma_dog, sigma_fav, ceiling):
    """Total downward (ceiling) bias; returned as a POSITIVE magnitude so larger
    => stronger under signal (it is the negative of the summed signed bias)."""
    sb = saturation_team_bias(dog_est, sigma_dog, ceiling) \
        + saturation_team_bias(fav_est, sigma_fav, ceiling)
    return -sb   # >= 0 magnitude of downward bias


# ---------------------------------------------------------------------------
# Probit (standardized single feature), reused shape from v3
# ---------------------------------------------------------------------------
@dataclass
class Probit1:
    const: float
    slope: float
    se_slope: float
    pvalue: float
    mean: float
    std: float
    llf: float

    def prob(self, x):
        z = (np.asarray(x, float) - self.mean) / self.std
        return NORM.cdf(self.const + self.slope * z)


def fit_probit1(x, y):
    x = np.asarray(x, float)
    m, s = x.mean(), x.std()
    X = sm.add_constant((x - m) / s, has_constant="add")
    res = sm.Probit(np.asarray(y, float), X).fit(disp=False)
    return Probit1(const=res.params[0], slope=res.params[1], se_slope=res.bse[1],
                   pvalue=res.pvalues[1], mean=m, std=s, llf=res.llf)


# ---------------------------------------------------------------------------
# Choose ceiling C by OOS log-loss (the only way C is identified)
# ---------------------------------------------------------------------------
def select_ceiling(spread_est, totals_est, fav_points, dog_points,
                   ceilings, k=5, seed=0):
    """For each candidate ceiling, run k-fold: train probit (under ~ saturation
    bias) on k-1 folds, score OOS log-loss on the held-out fold. Return the C
    with the lowest mean OOS log-loss and the full table."""
    spread_est = np.asarray(spread_est, float)
    totals_est = np.asarray(totals_est, float)
    fav_points = np.asarray(fav_points, float)
    dog_points = np.asarray(dog_points, float)
    n = spread_est.size
    rng = np.random.default_rng(seed)
    folds = np.array_split(rng.permutation(n), k)

    nu = (fav_points + dog_points) - totals_est
    under = (nu < 0).astype(float)
    keep = nu != 0

    table = []
    for C in ceilings:
        losses = []
        for i in range(k):
            te = folds[i]
            tr = np.concatenate([folds[j] for j in range(k) if j != i])
            d_tr, f_tr = implied_team_points(spread_est[tr], totals_est[tr])
            s1 = tobit_left_censored_v2(dog_points[tr], d_tr).sigma
            s2 = tobit_left_censored_v2(fav_points[tr], f_tr).sigma
            sb_tr = saturation_totals(d_tr, f_tr, s1, s2, C)
            ktr = keep[tr]
            model = fit_probit1(sb_tr[ktr], under[tr][ktr])

            d_te, f_te = implied_team_points(spread_est[te], totals_est[te])
            sb_te = saturation_totals(d_te, f_te, s1, s2, C)
            kte = keep[te]
            p = np.clip(model.prob(sb_te[kte]), 1e-6, 1 - 1e-6)
            yt = under[te][kte]
            losses.append(-np.mean(yt * np.log(p) + (1 - yt) * np.log(1 - p)))
        table.append((C, float(np.mean(losses))))
    best = min(table, key=lambda t: t[1])[0]
    return best, table


# ---------------------------------------------------------------------------
# k-fold OOS strategy: bet the UNDER where predicted P(under) > hurdle
# ---------------------------------------------------------------------------
@dataclass
class UnderFold:
    n_bets: int
    n_wins: int
    win_rate: float
    unit_return: float
    qtr_kelly_roi: float


def kfold_under_strategy(spread_est, totals_est, fav_points, dog_points,
                         ceiling, k=5, hurdle=0.5238, seed=0):
    spread_est = np.asarray(spread_est, float)
    totals_est = np.asarray(totals_est, float)
    fav_points = np.asarray(fav_points, float)
    dog_points = np.asarray(dog_points, float)
    n = spread_est.size
    rng = np.random.default_rng(seed)
    folds = np.array_split(rng.permutation(n), k)

    nu = (fav_points + dog_points) - totals_est
    under = (nu < 0).astype(float)
    keep = nu != 0

    out = []
    for i in range(k):
        te = folds[i]
        tr = np.concatenate([folds[j] for j in range(k) if j != i])
        d_tr, f_tr = implied_team_points(spread_est[tr], totals_est[tr])
        s1 = tobit_left_censored_v2(dog_points[tr], d_tr).sigma
        s2 = tobit_left_censored_v2(fav_points[tr], f_tr).sigma
        sb_tr = saturation_totals(d_tr, f_tr, s1, s2, ceiling)
        ktr = keep[tr]
        model = fit_probit1(sb_tr[ktr], under[tr][ktr])

        d_te, f_te = implied_team_points(spread_est[te], totals_est[te])
        sb_te = saturation_totals(d_te, f_te, s1, s2, ceiling)
        p = model.prob(sb_te)
        bet = keep[te] & (p > hurdle)
        nb = int(bet.sum())
        if nb == 0:
            out.append(UnderFold(0, 0, 0.0, 0.0, 0.0))
            continue
        w = under[te][bet]
        wins = int(w.sum())
        out.append(UnderFold(
            n_bets=nb, n_wins=wins, win_rate=wins / nb,
            unit_return=(wins * 100 - (nb - wins) * 110) / (nb * 110),
            qtr_kelly_roi=kelly_bankroll_roi(w, p[bet], 0.25),
        ))
    return out
