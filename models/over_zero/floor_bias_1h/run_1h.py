"""Floor Bias 1H driver.

  # APPROX mode (runs now; 1H line = frac * game line):
  python floor_bias_1h/run_1h.py
  python floor_bias_1h/run_1h.py --total-frac 0.52   # isolate censoring

  # REAL mode (true backtest once you have 1H lines):
  python floor_bias_1h/run_1h.py --half-lines my_1h_lines.csv

half-lines CSV columns: game_id,half_spread,half_total
"""

import argparse

from floor_bias_1h import fit_1h, kfold_1h, load_1h, strategy_1h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, nargs="+", default=list(range(2013, 2026)))
    ap.add_argument("--half-lines", default=None,
                    help="CSV game_id,half_spread,half_total for a TRUE backtest")
    ap.add_argument("--total-frac", type=float, default=0.5,
                    help="approx: half_total = frac*game_total (0.5=latent; "
                         "~0.52 de-biases the 1H scoring excess)")
    ap.add_argument("--spread-frac", type=float, default=0.5)
    args = ap.parse_args()

    data = load_1h(args.season, half_lines_csv=args.half_lines,
                   total_frac=args.total_frac, spread_frac=args.spread_frac)
    print(f"Loaded {data.half_spread_est.size:,} first-half games, "
          f"{min(args.season)}-{max(args.season)}")
    print(f"1H line source: {data.source}")
    if data.source != "real":
        print("  *** APPROX lines: mechanism illustration, NOT a validated edge. ***")
        print("  *** Supply --half-lines for a true backtest. ***")

    over = data.over_diag()
    print(f"Baseline 1H over rate: {over:.2f}%  (breakeven 52.38%)\n")

    fit = fit_1h(data)
    print(f"Tobit sigma  dog={fit.tobit_dog.sigma:.2f}  fav={fit.tobit_fav.sigma:.2f}  "
          f"(1H censored: dog={fit.tobit_dog.n_censored}, fav={fit.tobit_fav.n_censored})")
    print(f"Probit P(over)=Phi(const+slope*biasTotals): "
          f"const={fit.probit.const:+.4f}  slope={fit.probit.slope:+.4f} "
          f"(SE {fit.probit.se_slope:.4f}, p={fit.probit.pvalue_slope:.3g})")
    print(f"bias clearing 52.38% hurdle = {fit.probit.bias_for_hurdle():.3f}")

    print("\nIn-sample 'bet the 1H over' by censoring-bias threshold:")
    print(f"  {'thr':>6} {'N':>6} {'win%':>7} {'unit%':>7} {'qtrK%':>8} {'LR(.5238)p':>11}")
    for thr in (1.0, 1.75, 2.5):
        s = strategy_1h(fit, thr)
        if s.n_bets == 0:
            print(f"  >{thr:<5.2f}  (no games)")
            continue
        print(f"  >{thr:<5.2f} {s.n_bets:>6} {s.win_rate*100:>6.2f}% "
              f"{s.unit_return*100:>+6.2f}% {s.qtr_kelly_roi*100:>+7.1f}% "
              f"{s.lr_breakeven[1]:>11.3f}")

    print("\n5-fold OOS (bet 1H over where P>52.38% and bias>1.0):")
    print(f"  {'fold':>5} {'N':>6} {'win%':>7} {'unit%':>7}")
    tot_n = tot_w = 0
    for i, (nb, wins, ur) in enumerate(kfold_1h(data), 1):
        if nb == 0:
            print(f"  {i:>5}  (no bets)")
            continue
        tot_n += nb; tot_w += wins
        print(f"  {i:>5} {nb:>6} {wins/nb*100:>6.2f}% {ur*100:>+6.2f}%")
    if tot_n:
        print(f"  {'TOT':>5} {tot_n:>6} {tot_w/tot_n*100:>6.2f}%")


if __name__ == "__main__":
    main()
