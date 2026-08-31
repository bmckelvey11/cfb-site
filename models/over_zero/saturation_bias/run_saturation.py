"""Saturation Bias model driver -- the under-side / ceiling analog.

  python saturation_bias/run_saturation.py [--season 2013 ... 2025]
"""

import argparse

import numpy as np

from saturation import (
    fit_probit1,
    implied_team_points,
    kfold_under_strategy,
    load_from_raw,
    saturation_totals,
    select_ceiling,
    tobit_left_censored_v2,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, nargs="+", default=list(range(2013, 2026)))
    args = ap.parse_args()

    se, te, fp, dp = load_from_raw(args.season)
    nu = (fp + dp) - te
    keep = nu != 0
    under = (nu < 0).astype(float)
    print(f"Loaded {se.size:,} games, {min(args.season)}-{max(args.season)}")
    print(f"Baseline under-win rate: {under[keep].mean()*100:.2f}%  (breakeven 52.38%)\n")

    # ---- 1. Pick the ceiling C by OOS log-loss (C is not otherwise identified)
    print("=" * 68)
    print("1. Select scoring ceiling C by out-of-sample log-loss")
    print("=" * 68)
    ceilings = list(range(38, 71, 4))
    bestC, table = select_ceiling(se, te, fp, dp, ceilings)
    print(f"  {'C (per-team)':>13} {'OOS logloss':>12}")
    for C, ll in table:
        mark = "  <- best" if C == bestC else ""
        print(f"  {C:>13} {ll:>12.5f}{mark}")
    print(f"\n  Selected ceiling C = {bestC} points/team")

    # ---- 2. In-sample probit: under ~ saturation bias -------------------------
    d, f = implied_team_points(se, te)
    s1 = tobit_left_censored_v2(dp, d).sigma
    s2 = tobit_left_censored_v2(fp, f).sigma
    sb = saturation_totals(d, f, s1, s2, bestC)
    model = fit_probit1(sb[keep], under[keep])
    print("\n" + "=" * 68)
    print("2. Probit  P(under) = Phi(const + slope * saturationBias)")
    print("=" * 68)
    print(f"  const={model.const:+.4f}  slope={model.slope:+.4f} "
          f"(SE {model.se_slope:.4f}, p={model.pvalue:.3g})")
    # under-win rate by saturation-bias qu, in-sample
    print("\n  under-win% by saturation-bias quartile (in-sample):")
    qs = np.quantile(sb[keep], [0, .25, .5, .75, 1.0])
    sbk, uk = sb[keep], under[keep]
    for lo, hi in zip(qs[:-1], qs[1:]):
        m = (sbk >= lo) & (sbk <= hi)
        print(f"    bias [{lo:5.3f},{hi:5.3f}]  N={int(m.sum()):>5}  "
              f"under%={uk[m].mean()*100:.2f}")

    # ---- 3. OOS k-fold under strategy ----------------------------------------
    print("\n" + "=" * 68)
    print("3. 5-fold OOS: bet the UNDER where predicted P(under) > 52.38%")
    print("=" * 68)
    folds = kfold_under_strategy(se, te, fp, dp, bestC)
    print(f"  {'fold':>5} {'bets':>6} {'win%':>7} {'unit%':>7} {'qtrK%':>8}")
    tot_n = tot_w = 0
    for i, r in enumerate(folds, 1):
        if r.n_bets == 0:
            print(f"  {i:>5}  (no bets cleared hurdle)")
            continue
        tot_n += r.n_bets; tot_w += r.n_wins
        print(f"  {i:>5} {r.n_bets:>6} {r.win_rate*100:>6.2f}% "
              f"{r.unit_return*100:>+6.2f}% {r.qtr_kelly_roi*100:>+7.1f}%")
    if tot_n:
        print(f"  {'TOTAL':>5} {tot_n:>6} {tot_w/tot_n*100:>6.2f}%")
    else:
        print("  No bets cleared the hurdle out-of-sample.")


if __name__ == "__main__":
    main()
