"""Walk-forward backtest of the Floor Bias over strategy.

  python monitor/run_walkforward.py [--season 2013 ... 2025] [--min-train 3]
      [--threshold 1.0]

The k-fold CV in v1/v3 shuffles seasons together, so training folds contain
games played after the test games. This is the deployable-protocol check: for
each season t, fit the full pipeline (Tobit sigmas + probit) ONLY on seasons
< t, then bet season t. Two bet rules per test season:

  A (v1 headline rule): bet the over where expected censoring bias > threshold
  B (k-fold rule):      bet the over where trained-probit P(over) > 52.38%

Estimator core imported from ../v2; per-season loader shared with monitor.py.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v2"))
from monitor import _wilson, load_from_raw  # noqa: E402
from models_v2 import (  # noqa: E402
    censoring_bias,
    implied_team_points,
    kelly_bankroll_roi,
    log_likelihood_ratio,
    probit_win_v2,
    tobit_left_censored_v2,
)

HURDLE = 0.5238


def fit_train(se, te, fp, dp):
    """Full v1 pipeline on the training seasons: Tobit sigmas + probit."""
    dog_est, fav_est = implied_team_points(se, te)
    s1 = tobit_left_censored_v2(dp, dog_est).sigma
    s2 = tobit_left_censored_v2(fp, fav_est).sigma
    _, bias = censoring_bias(dog_est, fav_est, s1, s2)
    nu = (fp + dp) - te
    keep = nu != 0
    probit = probit_win_v2((nu > 0).astype(float)[keep], bias[keep])
    return s1, s2, probit


def _unit(wins, n):
    return (wins * 100 - (n - wins) * 110) / (n * 110) if n else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, nargs="+", default=list(range(2013, 2026)))
    ap.add_argument("--min-train", type=int, default=3,
                    help="minimum training seasons before the first bet season")
    ap.add_argument("--threshold", type=float, default=1.0,
                    help="rule A: bet the over where biasTotals > threshold")
    args = ap.parse_args()

    data = load_from_raw(args.season)
    years = sorted(data)
    if len(years) <= args.min_train:
        sys.exit(f"Need > {args.min_train} seasons of data; have {len(years)}.")

    print(f"Loaded {len(years)} seasons: {years[0]}-{years[-1]}")
    print(f"Walk-forward: train on seasons < t, bet season t "
          f"(first bet season {years[args.min_train]}).")
    print(f"Rule A: bias > {args.threshold}.  Rule B: P(over) > {HURDLE:.4f}.\n")

    hdr = (f"  {'season':>6} {'Ntrain':>7} |"
           f" {'betsA':>5} {'win%A':>7} {'unitA%':>7} |"
           f" {'betsB':>5} {'win%B':>7} {'unitB%':>7}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    wA, pA = [], []          # rule A outcomes + trained win probs, chronological
    wB = []
    for t in years[args.min_train:]:
        tr_years = [y for y in years if y < t]
        se, te, fp, dp = (np.concatenate([data[y][k] for y in tr_years])
                          for k in range(4))
        s1, s2, probit = fit_train(se, te, fp, dp)

        se_t, te_t, fp_t, dp_t = data[t]
        dog_t, fav_t = implied_team_points(se_t, te_t)
        _, bias_t = censoring_bias(dog_t, fav_t, s1, s2)
        wp_t = probit.win_prob(bias_t)
        nu_t = (fp_t + dp_t) - te_t
        keep_t = nu_t != 0
        over_t = (nu_t > 0).astype(float)

        selA = keep_t & (bias_t > args.threshold)
        selB = keep_t & (wp_t > HURDLE)
        wA.extend(over_t[selA]); pA.extend(wp_t[selA])
        wB.extend(over_t[selB])

        nA, kA = int(selA.sum()), int(over_t[selA].sum())
        nB, kB = int(selB.sum()), int(over_t[selB].sum())
        wrA = f"{kA/nA*100:6.2f}%" if nA else "   n/a"
        wrB = f"{kB/nB*100:6.2f}%" if nB else "   n/a"
        print(f"  {t:>6} {se.size:>7} |"
              f" {nA:>5} {wrA:>7} {_unit(kA, nA)*100:>+6.2f}% |"
              f" {nB:>5} {wrB:>7} {_unit(kB, nB)*100:>+6.2f}%")

    print("  " + "-" * (len(hdr) - 2))
    for label, w in (("A", wA), ("B", wB)):
        n = len(w)
        if n == 0:
            print(f"  rule {label}: no bets")
            continue
        wins = int(sum(w))
        lo, hi = _wilson(wins, n)
        lr, p = log_likelihood_ratio(wins, n, q=HURDLE)
        line = (f"  POOLED {label}: N={n}  win={wins/n*100:.2f}% "
                f"(Wilson95 [{lo*100:.1f},{hi*100:.1f}])  "
                f"unit={_unit(wins, n)*100:+.2f}%  LR vs breakeven p={p:.3f}")
        if label == "A":
            line += (f"  qtrKelly ROI={kelly_bankroll_roi(np.array(w), np.array(pA), 0.25)*100:+.1f}%"
                     f" (chronological)")
        print(line)
    print("\n  Deployable iff the pooled Wilson lower bound clears "
          f"{HURDLE*100:.2f}%.")


if __name__ == "__main__":
    main()
