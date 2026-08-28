"""Edge-decay monitor for the Floor Bias model.

If books are correcting totals for censoring bias (the paper predicts the anomaly
dies as the finding spreads), the signature is: the probit slope on biasTotals
trends toward 0, the bias needed to clear the 52.38% hurdle rises, and the
over-win% in the bias>1.0 bucket drifts toward 50%.

This computes those statistics per season and over trailing windows, with
confidence intervals, plus a trend test on the per-season slope -- so decay is
measured, not guessed.

Estimator core imported from ../v2.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v2"))
from models_v2 import (  # noqa: E402
    censoring_bias,
    implied_team_points,
    load_raw_seasons as load_from_raw,
    probit_win_v2,
    tobit_left_censored_v2,
)

HURDLE = 0.5238


def _wilson(wins, n, z=1.96):
    """Wilson 95% CI for a binomial proportion."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = wins / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (center - half, center + half)


@dataclass
class WindowStat:
    label: str
    n_games: int
    sigma_dog: float
    sigma_fav: float
    slope: float
    se_slope: float
    slope_ci: tuple
    p_slope: float
    hurdle_bias: float        # bias needed to clear 52.38%
    n_bets: int               # games with biasTotals > 1.0
    win_rate: float
    win_ci: tuple             # Wilson CI on that win rate
    profitable: bool          # win_ci lower bound > 52.38%
    alive: bool               # slope CI excludes 0


def window_stat(label, se, te, fp, dp, bet_threshold=1.0):
    dog_est, fav_est = implied_team_points(se, te)
    td = tobit_left_censored_v2(dp, dog_est)
    tf = tobit_left_censored_v2(fp, fav_est)
    _, bias = censoring_bias(dog_est, fav_est, td.sigma, tf.sigma)

    nu = (fp + dp) - te
    keep = nu != 0
    over = (nu > 0).astype(float)
    pr = probit_win_v2(over[keep], bias[keep])
    ci = (pr.slope - 1.96 * pr.se_slope, pr.slope + 1.96 * pr.se_slope)

    sel = keep & (bias > bet_threshold)
    nb = int(sel.sum())
    wins = int(over[sel].sum())
    wr = wins / nb if nb else float("nan")
    wci = _wilson(wins, nb)

    return WindowStat(
        label=label, n_games=se.size, sigma_dog=td.sigma, sigma_fav=tf.sigma,
        slope=pr.slope, se_slope=pr.se_slope, slope_ci=ci, p_slope=pr.pvalue_slope,
        hurdle_bias=pr.bias_for_hurdle(HURDLE),
        n_bets=nb, win_rate=wr, win_ci=wci,
        profitable=(wci[0] > HURDLE) if nb else False,
        alive=(ci[0] > 0),
    )


def per_season(data):
    return [window_stat(str(yr), *data[yr]) for yr in sorted(data)]


def trailing_windows(data, width=3):
    years = sorted(data)
    out = []
    for i in range(width - 1, len(years)):
        win = years[i - width + 1:i + 1]
        cat = [np.concatenate([data[y][k] for y in win]) for k in range(4)]
        out.append(window_stat(f"{win[0]}-{win[-1]}", *cat))
    return out


def slope_trend(stats_list):
    """OLS of per-season slope on season index. Negative & significant => decay."""
    yrs = np.array([float(s.label) for s in stats_list])
    sl = np.array([s.slope for s in stats_list])
    x = yrs - yrs.mean()
    res = stats.linregress(x, sl)
    return res.slope, res.pvalue, res.rvalue ** 2
