"""Arscott (2022) recreation -- v3.

v2 surfaced a puzzle: the realized over-edge rises with expected censoring bias
MORE steeply than pure-censoring theory predicts. Because biasTotals is high
exactly when totalsEst is low (and the game is lopsided), the obvious worry is
that "censoring bias" is just a repackaging of "low total / lopsided game."

v3 disentangles them. It asks:
  - Which single line-derived feature best predicts the over out-of-sample:
    the censoring bias, the total level, the spread, or the underdog's implied
    points?
  - In a MULTIVARIATE probit, does biasTotals carry signal beyond totalsEst
    (i.e. does censoring's nonlinearity matter), or does totalsEst absorb it?
  - Out-of-sample, does a richer model beat v1's single-feature rule?

Shared core (Tobit, censoring bias, Kelly, loader) is imported from v2 so v1
stays frozen and v2 stays the SE/correlation reference.
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
    censoring_bias,
    implied_team_points,
    kelly_bankroll_roi,
    load_from_raw,
    log_likelihood_ratio,
    tobit_left_censored_v2,
)


# ---------------------------------------------------------------------------
# Feature construction
# ---------------------------------------------------------------------------
def build_features(spread_est, totals_est, fav_points, dog_points,
                   sigma_dog, sigma_fav):
    """Per-game candidate predictors of the over, plus the realized outcome.

    Returns (feature_dict, over_wins, keep_mask). All features are derivable
    from the two betting lines alone (publicly available pre-game).
    """
    spread_est = np.asarray(spread_est, float)
    totals_est = np.asarray(totals_est, float)
    dog_est, fav_est = implied_team_points(spread_est, totals_est)
    _, bias_totals = censoring_bias(dog_est, fav_est, sigma_dog, sigma_fav)

    feats = {
        "biasTotals": bias_totals,
        "totalsEst": totals_est,
        "spreadEst": spread_est,
        "dogPointEst": dog_est,
    }
    nu = (fav_points + dog_points) - totals_est
    over_wins = (nu > 0).astype(float)
    keep = nu != 0                          # drop pushes
    return feats, over_wins, keep


# ---------------------------------------------------------------------------
# Probit (uni- or multivariate) via statsmodels, with standardized inputs
# ---------------------------------------------------------------------------
@dataclass
class ProbitMV:
    names: list
    params: np.ndarray          # [const, b1, b2, ...] in standardized-feature space
    bse: np.ndarray
    pvalues: np.ndarray
    means: np.ndarray           # feature means (for standardization)
    stds: np.ndarray
    llf: float
    llnull: float
    n: int

    @property
    def pseudo_r2(self):
        return 1.0 - self.llf / self.llnull

    def _design(self, feats):
        cols = [(np.asarray(feats[n], float) - m) / s
                for n, m, s in zip(self.names, self.means, self.stds)]
        return sm.add_constant(np.column_stack(cols), has_constant="add")

    def win_prob(self, feats):
        return NORM.cdf(self._design(feats) @ self.params)


def fit_probit(feats, names, over_wins, keep):
    """Fit P(over)=Phi(b0 + sum b_k z_k), z = standardized features."""
    cols, means, stds = [], [], []
    for n in names:
        v = np.asarray(feats[n], float)[keep]
        m, s = v.mean(), v.std()
        cols.append((v - m) / s)
        means.append(m); stds.append(s)
    X = sm.add_constant(np.column_stack(cols), has_constant="add")
    y = over_wins[keep]
    res = sm.Probit(y, X).fit(disp=False)
    null = sm.Probit(y, np.ones((y.size, 1))).fit(disp=False)
    return ProbitMV(
        names=list(names), params=res.params, bse=res.bse, pvalues=res.pvalues,
        means=np.array(means), stds=np.array(stds),
        llf=res.llf, llnull=null.llf, n=int(y.size),
    )


# ---------------------------------------------------------------------------
# Out-of-sample k-fold bake-off across model specs / rules
# ---------------------------------------------------------------------------
@dataclass
class FoldResult:
    n_bets: int
    n_wins: int
    win_rate: float
    unit_return: float
    qtr_kelly_roi: float
    mean_logloss: float         # over held-out bets (lower better)


def _unit_return(wins, n):
    return (wins * 100 - (n - wins) * 110) / (n * 110) if n else 0.0


def kfold_compare(spread_est, totals_est, fav_points, dog_points,
                  specs, k=5, hurdle=0.5238, seed=0):
    """For each named spec (list of feature names, or a callable rule), train on
    k-1 folds and bet the over on the held-out fold where the model's predicted
    P(over) > hurdle. Sigmas are re-estimated per training fold.

    `specs`: dict name -> list[str] feature names for a probit spec.
    Returns dict name -> list[FoldResult] (one per fold).
    """
    spread_est = np.asarray(spread_est, float)
    totals_est = np.asarray(totals_est, float)
    fav_points = np.asarray(fav_points, float)
    dog_points = np.asarray(dog_points, float)
    n = spread_est.size
    rng = np.random.default_rng(seed)
    folds = np.array_split(rng.permutation(n), k)

    out = {name: [] for name in specs}
    for i in range(k):
        te_idx = folds[i]
        tr_idx = np.concatenate([folds[j] for j in range(k) if j != i])

        # Tobit sigmas from training fold.
        dog_tr, fav_tr = implied_team_points(spread_est[tr_idx], totals_est[tr_idx])
        s1 = tobit_left_censored_v2(dog_points[tr_idx], dog_tr).sigma
        s2 = tobit_left_censored_v2(fav_points[tr_idx], fav_tr).sigma

        f_tr, ow_tr, keep_tr = build_features(
            spread_est[tr_idx], totals_est[tr_idx],
            fav_points[tr_idx], dog_points[tr_idx], s1, s2)
        f_te, ow_te, keep_te = build_features(
            spread_est[te_idx], totals_est[te_idx],
            fav_points[te_idx], dog_points[te_idx], s1, s2)

        for name, names in specs.items():
            model = fit_probit(f_tr, names, ow_tr, keep_tr)
            p = model.win_prob(f_te)
            bet = keep_te & (p > hurdle)
            nb = int(bet.sum())
            if nb == 0:
                out[name].append(FoldResult(0, 0, 0.0, 0.0, 0.0, np.nan))
                continue
            w = ow_te[bet]
            wins = int(w.sum())
            pe = np.clip(p[bet], 1e-6, 1 - 1e-6)
            logloss = -np.mean(w * np.log(pe) + (1 - w) * np.log(1 - pe))
            out[name].append(FoldResult(
                n_bets=nb, n_wins=wins, win_rate=wins / nb,
                unit_return=_unit_return(wins, nb),
                qtr_kelly_roi=kelly_bankroll_roi(w, p[bet], 0.25),
                mean_logloss=logloss,
            ))
    return out
