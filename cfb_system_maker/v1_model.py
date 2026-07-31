"""V1 over/under model: vendored recreation of Arscott (2022), "Market
efficiency and censoring bias in college football gambling" (SSRN 4197428).

Ported from over-zero/v1/censoring_bias.py (fit_pipeline path only -- no
betting-strategy/Kelly code, since cfb-site only needs P(over) per game).
Fits once on historical games.csv (see cli.py's ``refit-v1`` command), caches
the fitted params to data/processed/v1_fit.json, then scores any game
(played or upcoming) from spread/total alone -- no scores needed to score.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy import optimize, stats

from cfb_system_maker.models import GameRecord

NORM = stats.norm


def implied_team_points(spread_est, totals_est):
    """dogPointEst = (totalsEst - spreadEst) / 2; favPointEst = dogPointEst + spreadEst."""
    spread_est = np.asarray(spread_est, float)
    totals_est = np.asarray(totals_est, float)
    dog_est = (totals_est - spread_est) / 2.0
    fav_est = dog_est + spread_est
    return dog_est, fav_est


def _ols_start(y, x):
    """OLS start values for the Tobit MLE (not used standalone here)."""
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    n = y.size
    X = np.column_stack([np.ones(n), x])
    beta_hat, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta_hat
    return beta_hat[0], beta_hat[1], np.sqrt(resid @ resid / max(n - 2, 1))


@dataclass(frozen=True)
class TobitFit:
    alpha: float
    beta: float
    sigma: float


def _tobit_left_censored(y, x, censor=0.0) -> TobitFit:
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    cens = y <= censor
    obs = ~cens

    def neg_loglik(params):
        a, b, log_s = params
        s = np.exp(log_s)
        mu = a + b * x
        ll = 0.0
        z_obs = (y[obs] - mu[obs]) / s
        ll += np.sum(NORM.logpdf(z_obs) - log_s)
        z_cen = (censor - mu[cens]) / s
        ll += np.sum(NORM.logcdf(z_cen))
        return -ll

    a0, b0, s0 = _ols_start(y, x)
    x0 = np.array([a0, b0, np.log(max(s0, 1e-3))])
    res = optimize.minimize(neg_loglik, x0, method="BFGS")
    a, b, log_s = res.x
    return TobitFit(alpha=float(a), beta=float(b), sigma=float(np.exp(log_s)))


def _team_censor_bias(mu, sigma):
    mu = np.asarray(mu, float)
    z = mu / sigma
    return sigma * NORM.pdf(z) - mu * NORM.cdf(-z)


def censoring_bias(dog_est, fav_est, sigma_dog, sigma_fav):
    """biasTotals = bias_fav + bias_dog (>= 0, left-censoring inflates totals)."""
    bias_dog = _team_censor_bias(dog_est, sigma_dog)
    bias_fav = _team_censor_bias(fav_est, sigma_fav)
    return bias_dog + bias_fav


@dataclass(frozen=True)
class ProbitFit:
    const: float
    slope: float

    def win_prob(self, bias):
        return NORM.cdf(self.const + self.slope * np.asarray(bias, float))


def _probit_win(win, bias) -> ProbitFit:
    win = np.asarray(win, float)
    bias = np.asarray(bias, float)
    n = win.size
    X = np.column_stack([np.ones(n), bias])

    def neg_loglik(params):
        eta = X @ params
        return -np.sum(win * NORM.logcdf(eta) + (1 - win) * NORM.logcdf(-eta))

    x0 = np.array([NORM.ppf(np.clip(win.mean(), 1e-3, 1 - 1e-3)), 0.0])
    res = optimize.minimize(neg_loglik, x0, method="BFGS")
    return ProbitFit(const=float(res.x[0]), slope=float(res.x[1]))


@dataclass(frozen=True)
class V1Fit:
    tobit_dog_sigma: float
    tobit_fav_sigma: float
    probit_const: float
    probit_slope: float
    n_games: int

    def to_json(self) -> dict[str, Any]:
        return {
            "tobit_dog_sigma": self.tobit_dog_sigma,
            "tobit_fav_sigma": self.tobit_fav_sigma,
            "probit_const": self.probit_const,
            "probit_slope": self.probit_slope,
            "n_games": self.n_games,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "V1Fit":
        return cls(
            tobit_dog_sigma=float(data["tobit_dog_sigma"]),
            tobit_fav_sigma=float(data["tobit_fav_sigma"]),
            probit_const=float(data["probit_const"]),
            probit_slope=float(data["probit_slope"]),
            n_games=int(data["n_games"]),
        )


def fit_v1(games: list[GameRecord]) -> V1Fit:
    """Fit on played games only (spread/total/home_points/away_points all present,
    spread != 0). Mirrors over-zero v1/run_on_project_data.py's ``load()``."""
    spread_l, total_l, fav_l, dog_l = [], [], [], []
    for g in games:
        if g.spread is None or g.total is None or g.home_points is None or g.away_points is None:
            continue
        if g.spread == 0:
            continue
        if g.spread < 0:
            fav, dog = float(g.home_points), float(g.away_points)
        else:
            fav, dog = float(g.away_points), float(g.home_points)
        spread_l.append(abs(g.spread))
        total_l.append(float(g.total))
        fav_l.append(fav)
        dog_l.append(dog)

    spread_est = np.array(spread_l)
    totals_est = np.array(total_l)
    fav_points = np.array(fav_l)
    dog_points = np.array(dog_l)

    dog_est, fav_est = implied_team_points(spread_est, totals_est)
    tob_dog = _tobit_left_censored(dog_points, dog_est)
    tob_fav = _tobit_left_censored(fav_points, fav_est)

    bias_totals = censoring_bias(dog_est, fav_est, tob_dog.sigma, tob_fav.sigma)
    true_totals = fav_points + dog_points
    nu = true_totals - totals_est
    keep = nu != 0
    over_wins = (nu > 0).astype(float)
    probit = _probit_win(over_wins[keep], bias_totals[keep])

    return V1Fit(
        tobit_dog_sigma=tob_dog.sigma,
        tobit_fav_sigma=tob_fav.sigma,
        probit_const=probit.const,
        probit_slope=probit.slope,
        n_games=int(spread_est.size),
    )


def score_v1(games: list[GameRecord], fit: V1Fit) -> dict[int, float]:
    """P(over) per game_id. Needs only spread/total (no scores) -- works for
    played and upcoming games alike. Skips pick'em (spread == 0) or missing lines."""
    scorable = [g for g in games if g.spread is not None and g.total is not None and g.spread != 0]
    if not scorable:
        return {}
    spread_est = np.array([abs(g.spread) for g in scorable])
    totals_est = np.array([float(g.total) for g in scorable])
    dog_est, fav_est = implied_team_points(spread_est, totals_est)
    bias_totals = censoring_bias(dog_est, fav_est, fit.tobit_dog_sigma, fit.tobit_fav_sigma)
    probit = ProbitFit(const=fit.probit_const, slope=fit.probit_slope)
    win_probs = probit.win_prob(bias_totals)
    return {g.game_id: float(p) for g, p in zip(scorable, win_probs)}


def v1_fit_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / "processed" / "v1_fit.json"


def save_v1_fit(data_dir: str | Path, fit: V1Fit) -> Path:
    path = v1_fit_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fit.to_json(), indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_v1_fit(data_dir: str | Path) -> V1Fit | None:
    path = v1_fit_path(data_dir)
    if not path.exists():
        return None
    return V1Fit.from_json(json.loads(path.read_text(encoding="utf-8")))
