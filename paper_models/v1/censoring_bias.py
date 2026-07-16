"""Recreation of the models in Arscott (2022), "Market efficiency and censoring
bias in college football gambling" (SSRN 4197428).

Every model the paper discusses is implemented here as a pure function over
numpy arrays, so it can be driven by synthetic data (see demo_reproduce.py) or
by real closing lines + scores.

Notation follows the paper:
    spreadEst   = point spread line, underdog perspective (favorite favored => positive)
    totalsEst   = team totals (over/under) line
    trueSpread  = favPoints - dogPoints   (actual margin)
    trueTotals  = favPoints + dogPoints   (actual total)

Equation numbers in docstrings refer to the paper.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import optimize, stats

NORM = stats.norm  # standard normal; NORM.pdf = phi, NORM.cdf = Phi


# ---------------------------------------------------------------------------
# 1. Implied team points  (Eqs. 6, 7)
# ---------------------------------------------------------------------------
def implied_team_points(spread_est, totals_est):
    """Underdog and favorite expected points jointly implied by the two lines.

        dogPointEst = (totalsEst - spreadEst) / 2          (Eq. 6)
        favPointEst = dogPointEst + spreadEst              (Eq. 7)
    """
    spread_est = np.asarray(spread_est, float)
    totals_est = np.asarray(totals_est, float)
    dog_est = (totals_est - spread_est) / 2.0
    fav_est = dog_est + spread_est
    return dog_est, fav_est


# ---------------------------------------------------------------------------
# 2 & 3. OLS bias tests  (Eqs. 3, 4, 8, 9)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OLSFit:
    alpha: float          # intercept
    beta: float           # slope
    se_alpha: float
    se_beta: float
    resid_std: float
    r2: float
    n: int
    f_stat: float         # joint test  alpha == 0  AND  beta == 1
    f_pvalue: float


def ols_line_test(y, x):
    """Regress actual outcome y on line estimate x: y = alpha + beta*x + e.

    Implements Eqs. (3)/(4) (lines vs. actual spread/total) and Eqs. (8)/(9)
    (implied team points vs. actual team points). The efficiency null is the
    JOINT hypothesis alpha == 0 and beta == 1, tested with an F statistic.
    """
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    n = y.size
    X = np.column_stack([np.ones(n), x])
    beta_hat, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta_hat
    dof = n - 2
    sigma2 = resid @ resid / dof
    xtx_inv = np.linalg.inv(X.T @ X)
    cov = sigma2 * xtx_inv
    se = np.sqrt(np.diag(cov))

    # Joint Wald/F test of R*b == r, with R = I, r = [0, 1].
    R = np.eye(2)
    r = np.array([0.0, 1.0])
    diff = R @ beta_hat - r
    wald = diff @ np.linalg.inv(R @ cov @ R.T) @ diff
    f_stat = wald / 2.0
    f_pvalue = stats.f.sf(f_stat, 2, dof)

    sst = np.sum((y - y.mean()) ** 2)
    r2 = 1.0 - resid @ resid / sst
    return OLSFit(
        alpha=beta_hat[0], beta=beta_hat[1],
        se_alpha=se[0], se_beta=se[1],
        resid_std=np.sqrt(resid @ resid / dof),
        r2=r2, n=n, f_stat=f_stat, f_pvalue=f_pvalue,
    )


# ---------------------------------------------------------------------------
# 4. Tobit Type-1, left-censored at 0  (Eqs. 10, 11)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TobitFit:
    alpha: float
    beta: float
    sigma: float
    se_alpha: float
    se_beta: float
    se_log_sigma: float
    loglik: float
    n: int
    n_censored: int


def tobit_left_censored(y, x, censor=0.0):
    """MLE of  y* = alpha + beta*x + e,  e ~ N(0, sigma^2),  observed
    y = max(censor, y*).  This is Tobin (1958)'s Type-1 Tobit.

    Log-likelihood (left-censoring at c):
        uncensored (y > c):  log phi((y - mu)/sigma) - log sigma
        censored   (y == c): log Phi((c - mu)/sigma)
    Parameterized in [alpha, beta, log sigma] so sigma stays positive.
    """
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    n = y.size
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

    # Start from OLS on the observed (uncensored) points.
    start = ols_line_test(y, x)
    x0 = np.array([start.alpha, start.beta, np.log(max(start.resid_std, 1e-3))])
    res = optimize.minimize(neg_loglik, x0, method="BFGS")
    a, b, log_s = res.x

    # Standard errors from the inverse Hessian (BFGS gives an approximation).
    cov = res.hess_inv
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    return TobitFit(
        alpha=a, beta=b, sigma=float(np.exp(log_s)),
        se_alpha=se[0], se_beta=se[1], se_log_sigma=se[2],
        loglik=-res.fun, n=n, n_censored=int(cens.sum()),
    )


# ---------------------------------------------------------------------------
# 5. Censoring bias  (Eqs. 12, 13)  -- the central contribution
# ---------------------------------------------------------------------------
def _team_censor_bias(mu, sigma):
    """Expected left-censoring bias for one team's points.

    For latent x* ~ N(mu, sigma^2) censored at 0, the bias of the censored
    expectation relative to the latent mean is (paper footnote 4):

        E[x | x*] - mu = sigma * phi(mu/sigma) - mu * Phi(-mu/sigma)   >= 0
    """
    mu = np.asarray(mu, float)
    z = mu / sigma
    return sigma * NORM.pdf(z) - mu * NORM.cdf(-z)


def censoring_bias(dog_est, fav_est, sigma_dog, sigma_fav):
    """Censoring bias in the spread and totals lines (Eqs. 12, 13).

    Assumes the lines are unbiased apart from censoring (alpha=0, beta=1), so
    each team's latent mean equals its implied point estimate.

        biasTotals = bias_fav + bias_dog   (>= 0, left-censoring inflates totals)
        biasSpread = bias_fav - bias_dog   (can be either sign)
    """
    bias_dog = _team_censor_bias(dog_est, sigma_dog)
    bias_fav = _team_censor_bias(fav_est, sigma_fav)
    bias_totals = bias_fav + bias_dog
    bias_spread = bias_fav - bias_dog
    return bias_spread, bias_totals


# ---------------------------------------------------------------------------
# 6. Probit win model  (Eq. 14)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProbitFit:
    const: float
    slope: float
    se_const: float
    se_slope: float
    loglik: float
    n: int

    def win_prob(self, bias):
        """Fitted P(win=1 | bias) = Phi(const + slope*bias)."""
        return NORM.cdf(self.const + self.slope * np.asarray(bias, float))

    def bias_for_hurdle(self, hurdle=0.5238):
        """Bias level at which fitted win prob equals the break-even hurdle."""
        return (NORM.ppf(hurdle) - self.const) / self.slope


def probit_win(win, bias):
    """Estimate Pr(win=1 | bias) = Phi(const + slope*bias) by MLE (Eq. 14).

    `win` is a 0/1 array (dogWins or overWins); pushes must be dropped before
    calling so the outcome is binomial.
    """
    win = np.asarray(win, float)
    bias = np.asarray(bias, float)
    n = win.size
    X = np.column_stack([np.ones(n), bias])

    def neg_loglik(params):
        eta = X @ params
        ll = np.sum(win * NORM.logcdf(eta) + (1 - win) * NORM.logcdf(-eta))
        return -ll

    x0 = np.array([NORM.ppf(np.clip(win.mean(), 1e-3, 1 - 1e-3)), 0.0])
    res = optimize.minimize(neg_loglik, x0, method="BFGS")
    se = np.sqrt(np.clip(np.diag(res.hess_inv), 0, None))
    return ProbitFit(
        const=res.x[0], slope=res.x[1],
        se_const=se[0], se_slope=se[1],
        loglik=-res.fun, n=n,
    )


# ---------------------------------------------------------------------------
# 7. Even & Noble (1992) log-likelihood ratio test  (Eq. 5)
# ---------------------------------------------------------------------------
def log_likelihood_ratio(n_wins, n_total, q=0.5):
    """Test observed win rate n/N against benchmark q (fair=0.5, breakeven=0.5238).

        LR = 2 * { log[ (n/N)^n (1-n/N)^(N-n) ]  -  log[ q^n (1-q)^(N-n) ] }
    ~ Chi-square(1). Pushes must already be excluded so outcomes are binomial.
    """
    n, N = float(n_wins), float(n_total)
    phat = n / N
    # Unrestricted minus restricted binomial log-likelihood, times 2.
    ll_hat = n * np.log(phat) + (N - n) * np.log(1 - phat)
    ll_q = n * np.log(q) + (N - n) * np.log(1 - q)
    lr = 2.0 * (ll_hat - ll_q)
    pvalue = stats.chi2.sf(lr, 1)
    return lr, pvalue


# ---------------------------------------------------------------------------
# 8. Implied probability a team wins the game = Phi(spreadEst / sigma_spread)
# ---------------------------------------------------------------------------
def game_win_prob(spread_est, sigma_spread=15.69):
    """Favorite's win probability implied by the spread (paper section 5).

    P(favorite wins) = Phi(spreadEst / sigma_spread); the underdog's is the
    complement, Phi(-spreadEst / sigma_spread). 15.69 is the paper's MLE of the
    point-spread-error standard deviation.
    """
    return NORM.cdf(np.asarray(spread_est, float) / sigma_spread)


# ---------------------------------------------------------------------------
# 9. Betting-strategy returns: unit and Kelly  (Table 5)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StrategyResult:
    n_bets: int
    win_rate: float
    unit_return: float
    kelly_return: float        # return on turnover (profit / total staked)
    kelly_bankroll_roi: float  # compounded bankroll growth at `kelly_fraction`
    kelly_fraction: float      # Kelly fraction used for the bankroll sim
    lr_fair: tuple             # (stat, p) vs q = 0.5000
    lr_breakeven: tuple        # (stat, p) vs q = 0.5238


def kelly_bankroll_roi(over_wins, win_probs, fraction=1.0, *, risk=110.0, payout=100.0):
    """Compounded bankroll ROI from staking `fraction` x full-Kelly each bet,
    sequentially (bets in the given order).

        bet_i   = fraction * f_i * bankroll          (f_i = full Kelly fraction)
        win  ->  bankroll *= 1 + fraction*f_i*b      (b = payout/risk net odds)
        loss ->  bankroll *= 1 - fraction*f_i
    Returns final/initial - 1. Quarter-Kelly is fraction=0.25 (lower variance,
    far smaller drawdowns than full Kelly, at some growth cost).
    """
    w = np.asarray(over_wins, float)
    p = np.asarray(win_probs, float)
    b = payout / risk
    f = np.clip((b * p - (1 - p)) / b, 0.0, None) * fraction
    bankroll = 1.0
    for wi, fi in zip(w, f):
        bankroll *= (1 + fi * b) if wi > 0 else (1 - fi)
    return bankroll - 1.0


def strategy_returns(over_wins, win_probs, *, risk=110.0, payout=100.0,
                     kelly_fraction=0.25):
    """Returns for a series of 'over' bets at standard -110 pricing (Table 5).

    over_wins  : 0/1 outcomes (1 = over hit).
    win_probs  : model win prob per bet (used for Kelly sizing).
    Unit return        = total profit / total staked, every stake = `risk`.
    Kelly return        = profit / total staked at full Kelly (return on turnover;
                          invariant to a flat fraction, so reported at full Kelly).
    Kelly bankroll ROI = compounded bankroll growth staking `kelly_fraction`
                          x full-Kelly each bet in sequence.
    """
    w = np.asarray(over_wins, float)
    p = np.asarray(win_probs, float)
    n = w.size
    wins = int(w.sum())

    # Unit ($1-style flat) series.
    unit_profit = wins * payout - (n - wins) * risk
    unit_return = unit_profit / (n * risk)

    # Full-Kelly return on turnover.
    b = payout / risk
    f = np.clip((b * p - (1 - p)) / b, 0.0, None)
    profit = np.where(w > 0, f * b, -f)
    staked = f.sum()
    kelly_return = profit.sum() / staked if staked > 0 else 0.0

    return StrategyResult(
        n_bets=n,
        win_rate=wins / n,
        unit_return=unit_return,
        kelly_return=kelly_return,
        kelly_bankroll_roi=kelly_bankroll_roi(w, p, kelly_fraction,
                                              risk=risk, payout=payout),
        kelly_fraction=kelly_fraction,
        lr_fair=log_likelihood_ratio(wins, n, q=0.5000),
        lr_breakeven=log_likelihood_ratio(wins, n, q=0.5238),
    )


# ---------------------------------------------------------------------------
# 10. Full pipeline + k-fold cross-validation  (Table 6)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PipelineFit:
    tobit_dog: TobitFit
    tobit_fav: TobitFit
    probit: ProbitFit
    bias_spread: np.ndarray
    bias_totals: np.ndarray
    over_wins: np.ndarray


def fit_pipeline(spread_est, totals_est, fav_points, dog_points):
    """Run the full estimation chain on one dataset: implied points -> Tobit
    sigmas -> censoring bias -> probit on over outcomes."""
    spread_est = np.asarray(spread_est, float)
    totals_est = np.asarray(totals_est, float)
    fav_points = np.asarray(fav_points, float)
    dog_points = np.asarray(dog_points, float)

    dog_est, fav_est = implied_team_points(spread_est, totals_est)
    tob_dog = tobit_left_censored(dog_points, dog_est)
    tob_fav = tobit_left_censored(fav_points, fav_est)

    bias_spread, bias_totals = censoring_bias(
        dog_est, fav_est, tob_dog.sigma, tob_fav.sigma
    )

    true_totals = fav_points + dog_points
    nu = true_totals - totals_est           # totals forecast error (Eq. 2)
    keep = nu != 0                           # drop pushes (binomial outcome)
    over_wins = (nu > 0).astype(float)
    probit = probit_win(over_wins[keep], bias_totals[keep])

    return PipelineFit(
        tobit_dog=tob_dog, tobit_fav=tob_fav, probit=probit,
        bias_spread=bias_spread, bias_totals=bias_totals, over_wins=over_wins,
    )


def kfold_cross_validate(spread_est, totals_est, fav_points, dog_points,
                         k=5, hurdle=0.5238, seed=0):
    """K-fold out-of-sample test of the over strategy (Table 6).

    Train pipeline on k-1 folds, then on the held-out fold bet the over wherever
    the trained probit implies a win prob above `hurdle`. Returns one
    StrategyResult per fold plus the trained sigmas/probit params.
    """
    spread_est = np.asarray(spread_est, float)
    totals_est = np.asarray(totals_est, float)
    fav_points = np.asarray(fav_points, float)
    dog_points = np.asarray(dog_points, float)

    n = spread_est.size
    rng = np.random.default_rng(seed)
    folds = np.array_split(rng.permutation(n), k)

    rows = []
    for i in range(k):
        test_idx = folds[i]
        train_idx = np.concatenate([folds[j] for j in range(k) if j != i])

        fit = fit_pipeline(
            spread_est[train_idx], totals_est[train_idx],
            fav_points[train_idx], dog_points[train_idx],
        )

        # Apply to test fold.
        dog_est_t, fav_est_t = implied_team_points(
            spread_est[test_idx], totals_est[test_idx]
        )
        _, bias_totals_t = censoring_bias(
            dog_est_t, fav_est_t, fit.tobit_dog.sigma, fit.tobit_fav.sigma
        )
        win_probs_t = fit.probit.win_prob(bias_totals_t)

        true_totals_t = fav_points[test_idx] + dog_points[test_idx]
        nu_t = true_totals_t - totals_est[test_idx]
        bet = (win_probs_t > hurdle) & (nu_t != 0)   # drop pushes among bets

        if bet.sum() == 0:
            rows.append((fit, None))
            continue
        result = strategy_returns(
            (nu_t[bet] > 0).astype(float), win_probs_t[bet]
        )
        rows.append((fit, result))
    return rows
