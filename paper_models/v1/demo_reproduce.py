"""Reproduce the headline results of Arscott (2022) on synthetic data calibrated
to the paper's estimated parameters.

The real Goldsheet sample isn't public, so we generate games whose data-
generating process matches the paper: unbiased lines plus left-censoring at 0,
with underdog/favorite score-error standard deviations of sigma1 = 11.28 and
sigma2 = 11.94. If the recreated models are correct they should recover those
sigmas, produce a positive probit slope on totals censoring bias, and show the
over winning >52.38% wherever expected bias exceeds 1.0 point -- the paper's
55.72% result.

Run:  python paper_models/demo_reproduce.py
"""

import numpy as np

from censoring_bias import (
    censoring_bias,
    fit_pipeline,
    game_win_prob,
    implied_team_points,
    kfold_cross_validate,
    ols_line_test,
    strategy_returns,
)

# Paper-estimated parameters (Tables 3, 4).
SIGMA_DOG = 11.28
SIGMA_FAV = 11.94
N_GAMES = 60_000
SEED = 7


def make_data(n=N_GAMES, seed=SEED):
    """Synthetic games matching the paper's DGP: unbiased lines + censoring."""
    rng = np.random.default_rng(seed)

    # Lines drawn to roughly match Table 1 (spread median ~10, totals median ~53).
    spread_est = np.abs(rng.normal(11.0, 8.0, n)) + 0.5     # underdog perspective, > 0
    totals_est = rng.normal(53.0, 8.0, n).clip(20, 100)

    dog_est, fav_est = implied_team_points(spread_est, totals_est)

    # Latent scores: unbiased about the implied estimate, then censored at 0.
    dog_latent = dog_est + rng.normal(0, SIGMA_DOG, n)
    fav_latent = fav_est + rng.normal(0, SIGMA_FAV, n)
    dog_points = np.maximum(0.0, dog_latent)
    fav_points = np.maximum(0.0, fav_latent)
    return spread_est, totals_est, fav_points, dog_points


def main():
    spread_est, totals_est, fav_points, dog_points = make_data()
    true_spread = fav_points - dog_points
    true_totals = fav_points + dog_points

    print("=" * 70)
    print("Arscott (2022) recreation -- synthetic data calibrated to paper")
    print(f"N = {spread_est.size:,} games   (true sigma_dog={SIGMA_DOG}, "
          f"sigma_fav={SIGMA_FAV})")
    print("=" * 70)

    # --- OLS line tests (Eqs 3,4 / Table 2) -----------------------------------
    print("\n[2] OLS line-bias tests (efficiency null: alpha=0, beta=1)")
    sp = ols_line_test(true_spread, spread_est)
    to = ols_line_test(true_totals, totals_est)
    print(f"  spread: a={sp.alpha:+.3f} b={sp.beta:.3f}  resid_sd={sp.resid_std:.2f}"
          f"  F={sp.f_stat:.2f} (p={sp.f_pvalue:.3f})")
    print(f"  totals: a={to.alpha:+.3f} b={to.beta:.3f}  resid_sd={to.resid_std:.2f}"
          f"  F={to.f_stat:.2f} (p={to.f_pvalue:.4f})  <- biased (censoring)")

    # --- Tobit vs OLS on team points (Table 3) --------------------------------
    dog_est, fav_est = implied_team_points(spread_est, totals_est)
    print("\n[3,4] Underdog points: OLS vs Tobit (censoring at 0)")
    ols_dog = ols_line_test(dog_points, dog_est)
    fit = fit_pipeline(spread_est, totals_est, fav_points, dog_points)
    tb = fit.tobit_dog
    print(f"  OLS  : a={ols_dog.alpha:+.3f} b={ols_dog.beta:.3f} "
          f"resid_sd={ols_dog.resid_std:.2f}   (intercept biased up, slope down)")
    print(f"  Tobit: a={tb.alpha:+.3f} b={tb.beta:.3f} sigma={tb.sigma:.2f} "
          f"  ({tb.n_censored:,} censored)  <- recovers sigma_dog")
    print(f"  Tobit favorite sigma = {fit.tobit_fav.sigma:.2f}  <- recovers sigma_fav")

    # --- Probit on censoring bias (Eq 14 / Table 4) ---------------------------
    pf = fit.probit
    print("\n[6] Probit  P(over wins) = Phi(const + slope*biasTotals)")
    print(f"  const={pf.const:+.3f}  slope={pf.slope:+.3f}  "
          f"(slope>0: more bias -> over more likely)")
    print(f"  bias to clear 52.38% hurdle = {pf.bias_for_hurdle(0.5238):.2f} "
          f"(paper: 1.00)")

    # --- Game win probability -------------------------------------------------
    print("\n[8] Implied favorite win prob = Phi(spread/15.69)")
    for s in (3, 7, 14):
        print(f"  spread {s:>2}  ->  {game_win_prob(s):.3f}")

    # --- In-sample strategy (Table 5) -----------------------------------------
    _, bias_totals = censoring_bias(dog_est, fav_est, tb.sigma, fit.tobit_fav.sigma)
    nu = true_totals - totals_est
    keep = nu != 0
    over_wins = (nu > 0).astype(float)
    win_probs = pf.win_prob(bias_totals)

    print("\n[9] In-sample 'bet the over' strategies (standard -110 pricing)")
    print(f"  {'threshold':>10} {'N':>7} {'win%':>7} {'unit%':>7} {'kelly%':>7} "
          f"{'LR(q=.5)':>10} {'LR(q=.5238)':>12}")
    for thr in (1.00, 1.75):
        sel = keep & (bias_totals > thr)
        res = strategy_returns(over_wins[sel], win_probs[sel])
        print(f"  > {thr:<8.2f} {res.n_bets:>7} {res.win_rate*100:>6.2f}% "
              f"{res.unit_return*100:>6.2f}% {res.kelly_return*100:>6.2f}% "
              f"{res.lr_fair[0]:>6.2f}(p{res.lr_fair[1]:.3f}) "
              f"{res.lr_breakeven[0]:>5.2f}(p{res.lr_breakeven[1]:.3f})")
    print("  paper:  >1.00 -> 55.72% win, 6.37% unit, 9.91% kelly")
    print("          >1.75 -> 59.19% win, 13.00% unit, 15.05% kelly")

    # --- K-fold out-of-sample (Table 6) ---------------------------------------
    print("\n[10] 5-fold out-of-sample validation (bet over where Pwin>52.38%)")
    print(f"  {'fold':>5} {'Nbet':>6} {'win%':>7} {'unit%':>7} {'kelly%':>7} "
          f"{'sig1':>6} {'sig2':>6} {'const':>7} {'slope':>7}")
    rows = kfold_cross_validate(spread_est, totals_est, fav_points, dog_points)
    for i, (cvfit, res) in enumerate(rows, 1):
        if res is None:
            print(f"  {i:>5}  (no bets cleared hurdle)")
            continue
        print(f"  {i:>5} {res.n_bets:>6} {res.win_rate*100:>6.2f}% "
              f"{res.unit_return*100:>6.2f}% {res.kelly_return*100:>6.2f}% "
              f"{cvfit.tobit_dog.sigma:>6.2f} {cvfit.tobit_fav.sigma:>6.2f} "
              f"{cvfit.probit.const:>+7.3f} {cvfit.probit.slope:>+7.3f}")


if __name__ == "__main__":
    main()
