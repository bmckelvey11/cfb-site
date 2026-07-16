"""Arscott (2022) recreation -- v2.

v2 tightens two caveats flagged in v1:

  (A) ANALYTIC standard errors. v1 reported SEs from the BFGS inverse-Hessian
      approximation. v2 derives the analytic score of the Tobit log-likelihood
      and forms the covariance from the outer product of gradients (OPG / BHHH)
      -- an analytic information-matrix estimator. The probit uses statsmodels,
      whose SEs come from the analytic observed information. Both are compared
      back to v1's BFGS SEs so you can see whether v1's "fine for inference
      here" claim held.

  (B) DROP the independence assumption cov(d1, d2) = 0. v2 estimates the
      correlation rho between favorite and underdog score errors and propagates
      it. Central finding (also derivable on paper): the expected censoring bias
      is a MARGINAL quantity, so `biasTotals` is invariant to rho. Correlation
      only reshapes the totals-error variance -> the win probability for a given
      bias. v2 computes theoretical P(over | bias) under independent vs.
      correlated bivariate-normal censoring and compares both to the empirical
      probit (which already embeds the true correlation).

Shared, unchanged-from-v1 pieces (implied points, OLS test, censoring bias,
LL-ratio, Kelly) are reproduced here so v2 is self-contained and v1 stays frozen.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import statsmodels.api as sm
from scipy import optimize, stats

NORM = stats.norm


# ===========================================================================
# Shared with v1 (verbatim behavior)
# ===========================================================================
def implied_team_points(spread_est, totals_est):
    spread_est = np.asarray(spread_est, float)
    totals_est = np.asarray(totals_est, float)
    dog_est = (totals_est - spread_est) / 2.0
    fav_est = dog_est + spread_est
    return dog_est, fav_est


def _team_censor_bias(mu, sigma):
    mu = np.asarray(mu, float)
    z = mu / sigma
    return sigma * NORM.pdf(z) - mu * NORM.cdf(-z)


def censoring_bias(dog_est, fav_est, sigma_dog, sigma_fav):
    bias_dog = _team_censor_bias(dog_est, sigma_dog)
    bias_fav = _team_censor_bias(fav_est, sigma_fav)
    return bias_fav - bias_dog, bias_fav + bias_dog  # spread, totals


def log_likelihood_ratio(n_wins, n_total, q=0.5):
    n, N = float(n_wins), float(n_total)
    phat = n / N
    ll_hat = n * np.log(phat) + (N - n) * np.log(1 - phat)
    ll_q = n * np.log(q) + (N - n) * np.log(1 - q)
    lr = 2.0 * (ll_hat - ll_q)
    return lr, stats.chi2.sf(lr, 1)


def kelly_bankroll_roi(over_wins, win_probs, fraction=0.25, *, risk=110.0, payout=100.0):
    w = np.asarray(over_wins, float)
    p = np.asarray(win_probs, float)
    b = payout / risk
    f = np.clip((b * p - (1 - p)) / b, 0.0, None) * fraction
    bankroll = 1.0
    for wi, fi in zip(w, f):
        bankroll *= (1 + fi * b) if wi > 0 else (1 - fi)
    return bankroll - 1.0


# ===========================================================================
# (A) Tobit with ANALYTIC score + OPG covariance
# ===========================================================================
@dataclass(frozen=True)
class TobitFitV2:
    alpha: float
    beta: float
    sigma: float
    # analytic (OPG) standard errors:
    se_alpha: float
    se_beta: float
    se_sigma: float
    # v1's BFGS inverse-Hessian SEs, for comparison:
    se_alpha_bfgs: float
    se_beta_bfgs: float
    loglik: float
    n: int
    n_censored: int


def _tobit_scores(params, y, x, censor, obs, cens):
    """Per-observation score (gradient of log-lik) in params [alpha, beta, log_sigma].

    Derived analytically. With mu = alpha + beta*x, sigma = exp(log_sigma):
      uncensored (y>c):  z=(y-mu)/sigma
                         dl/dmu  =  z/sigma
                         dl/dlogsigma = z^2 - 1
      censored  (y==c):  a=(mu-c)/sigma,  lam = phi(a)/Phi(-a)   [inverse Mills]
                         dl/dmu  = -lam/sigma
                         dl/dlogsigma = a*lam
    Chain: dl/dalpha = dl/dmu;  dl/dbeta = dl/dmu * x.
    """
    a0, b0, log_s = params
    s = np.exp(log_s)
    mu = a0 + b0 * x
    n = y.size
    dmu = np.empty(n)
    dls = np.empty(n)

    z = (y[obs] - mu[obs]) / s
    dmu[obs] = z / s
    dls[obs] = z * z - 1.0

    a = (mu[cens] - censor) / s
    lam = NORM.pdf(a) / NORM.cdf(-a)         # inverse Mills ratio
    dmu[cens] = -lam / s
    dls[cens] = a * lam

    g_alpha = dmu
    g_beta = dmu * x
    g_logs = dls
    return np.column_stack([g_alpha, g_beta, g_logs])  # n x 3


def tobit_left_censored_v2(y, x, censor=0.0):
    """Tobit MLE with analytic-score OPG standard errors (+ BFGS SEs for compare)."""
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    n = y.size
    cens = y <= censor
    obs = ~cens

    def neg_loglik(p):
        a0, b0, log_s = p
        s = np.exp(log_s)
        mu = a0 + b0 * x
        ll = np.sum(NORM.logpdf((y[obs] - mu[obs]) / s) - log_s)
        ll += np.sum(NORM.logcdf((censor - mu[cens]) / s))
        return -ll

    def neg_grad(p):
        return -_tobit_scores(p, y, x, censor, obs, cens).sum(axis=0)

    # OLS start.
    X = np.column_stack([np.ones(n), x])
    bhat, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ bhat
    x0 = np.array([bhat[0], bhat[1], np.log(max(resid.std(), 1e-3))])

    res = optimize.minimize(neg_loglik, x0, jac=neg_grad, method="BFGS")
    a0, b0, log_s = res.x
    sigma = float(np.exp(log_s))

    # Analytic OPG covariance: V = (sum_i s_i s_i')^{-1}, params [a, b, log_s].
    S = _tobit_scores(res.x, y, x, censor, obs, cens)
    opg = S.T @ S
    cov_opg = np.linalg.inv(opg)
    se_opg = np.sqrt(np.clip(np.diag(cov_opg), 0, None))
    # delta method: se(sigma) = sigma * se(log_sigma)
    se_sigma = sigma * se_opg[2]

    # BFGS inverse-Hessian SEs (what v1 reported), in [a, b, log_s] space.
    se_bfgs = np.sqrt(np.clip(np.diag(res.hess_inv), 0, None))

    return TobitFitV2(
        alpha=a0, beta=b0, sigma=sigma,
        se_alpha=se_opg[0], se_beta=se_opg[1], se_sigma=se_sigma,
        se_alpha_bfgs=se_bfgs[0], se_beta_bfgs=se_bfgs[1],
        loglik=-res.fun, n=n, n_censored=int(cens.sum()),
    )


# ===========================================================================
# (A) Probit via statsmodels -> analytic observed-information SEs
# ===========================================================================
@dataclass(frozen=True)
class ProbitFitV2:
    const: float
    slope: float
    se_const: float
    se_slope: float
    pvalue_slope: float
    loglik: float
    n: int

    def win_prob(self, bias):
        return NORM.cdf(self.const + self.slope * np.asarray(bias, float))

    def bias_for_hurdle(self, hurdle=0.5238):
        return (NORM.ppf(hurdle) - self.const) / self.slope


def probit_win_v2(win, bias):
    """Probit P(win)=Phi(const+slope*bias) with statsmodels (analytic SEs)."""
    win = np.asarray(win, float)
    X = sm.add_constant(np.asarray(bias, float))
    model = sm.Probit(win, X).fit(disp=False)
    return ProbitFitV2(
        const=model.params[0], slope=model.params[1],
        se_const=model.bse[0], se_slope=model.bse[1],
        pvalue_slope=model.pvalues[1],
        loglik=model.llf, n=win.size,
    )


# ===========================================================================
# (B) Favorite/underdog error correlation + correlation-aware win probability
# ===========================================================================
def estimate_error_correlation(spread_est, totals_est, fav_points, dog_points,
                               tob_dog, tob_fav, censor=0.0):
    """Pearson correlation of favorite vs underdog score errors, on games where
    BOTH teams are uncensored (scored > 0). Errors are residuals about each
    team's Tobit fit. Censored games are excluded because their latent error is
    unobserved; censoring is rare (~3-5% of teams) so this is a clean estimate.
    """
    spread_est = np.asarray(spread_est, float)
    totals_est = np.asarray(totals_est, float)
    fav_points = np.asarray(fav_points, float)
    dog_points = np.asarray(dog_points, float)

    dog_est, fav_est = implied_team_points(spread_est, totals_est)
    r_dog = dog_points - (tob_dog.alpha + tob_dog.beta * dog_est)
    r_fav = fav_points - (tob_fav.alpha + tob_fav.beta * fav_est)
    both = (dog_points > censor) & (fav_points > censor)
    rho = np.corrcoef(r_dog[both], r_fav[both])[0, 1]
    return rho, int(both.sum())


def pover_theoretical(dog_est, fav_est, sigma_dog, sigma_fav, totals_est,
                      rho=0.0, n_mc=20000, seed=0):
    """Theoretical P(trueTotals > totalsEst) per game under a censored bivariate
    normal score model with correlation rho. Monte-Carlo (rho=0 -> independent).

    Latent (dog*, fav*) ~ N([dog_est, fav_est], cov with corr rho), each censored
    at 0; trueTotals = max(0,dog*) + max(0,fav*).
    """
    dog_est = np.asarray(dog_est, float)
    fav_est = np.asarray(fav_est, float)
    totals_est = np.asarray(totals_est, float)
    n = dog_est.size
    rng = np.random.default_rng(seed)

    # Draw standard correlated pairs once, reuse across games (common random
    # numbers) so independent vs. correlated comparison isn't MC noise.
    z = rng.standard_normal((n_mc, 2))
    z -= z.mean(axis=0)                # exact zero mean (kills CRN finite-sample offset)
    z_corr = np.empty_like(z)
    z_corr[:, 0] = z[:, 0]
    z_corr[:, 1] = rho * z[:, 0] + np.sqrt(max(1 - rho * rho, 0.0)) * z[:, 1]

    p = np.empty(n)
    for i in range(n):
        dog = np.maximum(0.0, dog_est[i] + sigma_dog * z_corr[:, 0])
        fav = np.maximum(0.0, fav_est[i] + sigma_fav * z_corr[:, 1])
        p[i] = np.mean(dog + fav > totals_est[i])
    return p
