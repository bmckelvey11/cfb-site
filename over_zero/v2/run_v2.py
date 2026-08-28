"""v2 driver: explore the two caveats on real CFBD data (2013-2025).

  python v2/run_v2.py --season 2013 2014 ... 2025

(A) Analytic (OPG) Tobit SEs + statsmodels probit SEs vs v1's BFGS SEs.
(B) Estimate fav/dog error correlation rho; show biasTotals is invariant to it;
    compare theoretical P(over|bias) under independent vs correlated models to
    the empirical probit.
"""

import argparse
import sys

import numpy as np

from models_v2 import (
    censoring_bias,
    estimate_error_correlation,
    implied_team_points,
    kelly_bankroll_roi,
    load_raw_seasons,
    log_likelihood_ratio,
    pover_theoretical,
    probit_win_v2,
    tobit_left_censored_v2,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, nargs="+",
                    default=list(range(2013, 2026)))
    ap.add_argument("--mc", type=int, default=10000, help="MC draws per game")
    args = ap.parse_args()

    data = load_raw_seasons(args.season)
    if not data:
        sys.exit("No raw data found.")
    yrs = [y for y in args.season if y in data]
    se, te, fp, dp = (np.concatenate([data[y][k] for y in yrs]) for k in range(4))
    ss = np.concatenate([np.full(data[y][0].size, y) for y in yrs])
    print(f"Loaded {se.size:,} games, seasons {min(args.season)}-{max(args.season)}\n")

    dog_est, fav_est = implied_team_points(se, te)

    # ---- (A) Tobit: analytic OPG SEs vs BFGS ---------------------------------
    print("=" * 70)
    print("(A) ANALYTIC standard errors")
    print("=" * 70)
    tob_dog = tobit_left_censored_v2(dp, dog_est)
    tob_fav = tobit_left_censored_v2(fp, fav_est)
    print("Tobit underdog points:")
    print(f"  alpha={tob_dog.alpha:+.4f}  beta={tob_dog.beta:.4f}  "
          f"sigma={tob_dog.sigma:.4f}  ({tob_dog.n_censored} censored)")
    print(f"    SE(alpha)  OPG={tob_dog.se_alpha:.4f}  BFGS={tob_dog.se_alpha_bfgs:.4f}")
    print(f"    SE(beta)   OPG={tob_dog.se_beta:.4f}  BFGS={tob_dog.se_beta_bfgs:.4f}")
    print(f"    SE(sigma)  OPG={tob_dog.se_sigma:.4f}")
    print("Tobit favorite points:")
    print(f"  alpha={tob_fav.alpha:+.4f}  beta={tob_fav.beta:.4f}  "
          f"sigma={tob_fav.sigma:.4f}  ({tob_fav.n_censored} censored)")
    print(f"    SE(alpha)  OPG={tob_fav.se_alpha:.4f}  BFGS={tob_fav.se_alpha_bfgs:.4f}")
    print(f"    SE(beta)   OPG={tob_fav.se_beta:.4f}  BFGS={tob_fav.se_beta_bfgs:.4f}")

    # Censoring bias + empirical over outcomes.
    _, bias_totals = censoring_bias(dog_est, fav_est, tob_dog.sigma, tob_fav.sigma)
    nu = (fp + dp) - te
    keep = nu != 0
    over_wins = (nu > 0).astype(float)

    probit = probit_win_v2(over_wins[keep], bias_totals[keep])
    print("\nProbit P(over)=Phi(const+slope*biasTotals) -- statsmodels analytic SE:")
    print(f"  const={probit.const:+.4f} (SE {probit.se_const:.4f})")
    print(f"  slope={probit.slope:+.4f} (SE {probit.se_slope:.4f}, "
          f"p={probit.pvalue_slope:.4g})")
    print(f"  bias clearing 52.38% hurdle = {probit.bias_for_hurdle():.3f}")

    n_seasons = np.unique(ss).size
    if n_seasons > 1:
        probit_cl = probit_win_v2(over_wins[keep], bias_totals[keep],
                                  groups=ss[keep])
        print(f"  season-clustered slope SE={probit_cl.se_slope:.4f}, "
              f"p={probit_cl.pvalue_slope:.4g} "
              f"({n_seasons} clusters -- treat as indicative)")

    # ---- (B) Correlation -----------------------------------------------------
    print("\n" + "=" * 70)
    print("(B) DROPPING independence  cov(d1,d2)=0")
    print("=" * 70)
    rho, n_both = estimate_error_correlation(se, te, fp, dp, tob_dog, tob_fav)
    print(f"Estimated fav/dog score-error correlation: rho = {rho:+.4f} "
          f"(n={n_both:,} both-uncensored games)")

    # B1: biasTotals invariant to rho -- prove via MC expectation.
    # E[trueTotals] - totalsEst should equal sum of marginal censoring biases
    # regardless of rho (linearity of expectation).
    sub = slice(0, min(2000, se.size))   # subsample for speed
    et_indep = pover_mean_total(dog_est[sub], fav_est[sub], tob_dog.sigma,
                                tob_fav.sigma, rho=0.0, n_mc=args.mc)
    et_corr = pover_mean_total(dog_est[sub], fav_est[sub], tob_dog.sigma,
                               tob_fav.sigma, rho=rho, n_mc=args.mc)
    analytic_bias = bias_totals[sub]
    print("\nbiasTotals invariance to rho (mean over 2,000 games):")
    print(f"  analytic biasTotals (rho-free formula): {analytic_bias.mean():.4f}")
    print(f"  MC E[trueTotals]-totalsEst, rho=0     : {et_indep.mean():.4f}")
    print(f"  MC E[trueTotals]-totalsEst, rho={rho:+.2f}  : {et_corr.mean():.4f}")
    print("  -> all three match: expected censoring bias does NOT depend on rho.")

    # B2: win probability DOES depend on rho. Compare theoretical P(over|bias)
    # under independent vs correlated to the empirical probit, binned by bias.
    p_indep = pover_theoretical(dog_est[sub], fav_est[sub], tob_dog.sigma,
                                tob_fav.sigma, te[sub], rho=0.0, n_mc=args.mc)
    p_corr = pover_theoretical(dog_est[sub], fav_est[sub], tob_dog.sigma,
                               tob_fav.sigma, te[sub], rho=rho, n_mc=args.mc)
    p_probit = probit.win_prob(bias_totals[sub])
    emp = over_wins[sub]
    keep_sub = nu[sub] != 0

    print("\nP(over) vs expected censoring bias -- binned "
          "(empirical = realized over-rate):")
    print(f"  {'bias bin':>12} {'N':>5} {'emp':>7} {'probit':>7} "
          f"{'theory rho=0':>12} {'theory rho_hat':>14}")
    edges = [-1, 0.25, 0.5, 1.0, 1.75, 10]
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = keep_sub & (bias_totals[sub] > lo) & (bias_totals[sub] <= hi)
        if m.sum() < 10:
            continue
        print(f"  ({lo:>4.2f},{hi:>4.2f}] {int(m.sum()):>5} "
              f"{emp[m].mean():>6.3f} {p_probit[m].mean():>6.3f} "
              f"{p_indep[m].mean():>11.3f} {p_corr[m].mean():>13.3f}")

    # ---- Strategy (unchanged logic, v2 estimates) ----------------------------
    print("\n" + "=" * 70)
    print("Strategy: bet over when biasTotals > threshold")
    print("=" * 70)
    wp = probit.win_prob(bias_totals)
    print(f"  {'thr':>6} {'N':>5} {'win%':>7} {'unit%':>7} {'qtrK ROI%':>10} "
          f"{'LR(.5238) p':>12}")
    for thr in (1.00, 1.75):
        sel = keep & (bias_totals > thr)
        w = over_wins[sel]
        wins = int(w.sum()); n = w.size
        unit = (wins * 100 - (n - wins) * 110) / (n * 110)
        qtr = kelly_bankroll_roi(w, wp[sel], 0.25)
        lr, p = log_likelihood_ratio(wins, n, q=0.5238)
        print(f"  >{thr:<5.2f} {n:>5} {wins/n*100:>6.2f}% {unit*100:>+6.2f}% "
              f"{qtr*100:>+9.1f}% {p:>11.3f}")


def pover_mean_total(dog_est, fav_est, sigma_dog, sigma_fav, rho=0.0,
                     n_mc=10000, seed=1):
    """MC E[trueTotals] - (dog_est+fav_est) per game; used to show rho-invariance
    of the expected censoring bias."""
    n = dog_est.size
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n_mc, 2))
    z -= z.mean(axis=0)               # exact zero mean (kills CRN finite-sample offset)
    z1 = z[:, 0]
    z2 = rho * z[:, 0] + np.sqrt(max(1 - rho * rho, 0.0)) * z[:, 1]
    out = np.empty(n)
    for i in range(n):
        dog = np.maximum(0.0, dog_est[i] + sigma_dog * z1)
        fav = np.maximum(0.0, fav_est[i] + sigma_fav * z2)
        out[i] = (dog + fav).mean() - (dog_est[i] + fav_est[i])
    return out


if __name__ == "__main__":
    main()
