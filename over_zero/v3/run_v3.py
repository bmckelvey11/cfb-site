"""v3 driver: is the over-edge censoring, or just 'low total / lopsided'?

  python v3/run_v3.py [--season 2013 ... 2025]
"""

import argparse

import numpy as np

from models_v3 import (
    build_features,
    fit_probit,
    implied_team_points,
    kfold_compare,
    load_from_raw,
    log_likelihood_ratio,
    tobit_left_censored_v2,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, nargs="+", default=list(range(2013, 2026)))
    args = ap.parse_args()

    se, te, fp, dp = load_from_raw(args.season)
    print(f"Loaded {se.size:,} games, {min(args.season)}-{max(args.season)}\n")

    dog_est, fav_est = implied_team_points(se, te)
    s1 = tobit_left_censored_v2(dp, dog_est).sigma
    s2 = tobit_left_censored_v2(fp, fav_est).sigma
    feats, ow, keep = build_features(se, te, fp, dp, s1, s2)

    # ---- 1. Univariate probits: which single feature predicts the over? ------
    print("=" * 72)
    print("1. Univariate probit per feature (standardized; in-sample)")
    print("=" * 72)
    print(f"  {'feature':>12} {'slope':>8} {'SE':>7} {'p':>10} {'pseudoR2':>9}")
    single = {}
    for name in ("biasTotals", "totalsEst", "spreadEst", "dogPointEst"):
        m = fit_probit(feats, [name], ow, keep)
        single[name] = m
        print(f"  {name:>12} {m.params[1]:>+8.4f} {m.bse[1]:>7.4f} "
              f"{m.pvalues[1]:>10.2e} {m.pseudo_r2*100:>8.3f}%")
    print("  (biasTotals slope >0 = over more likely; totalsEst/dogPointEst <0")
    print("   would mean lower totals -> over more likely.)")

    # ---- 2. Multivariate: does biasTotals survive controlling for totalsEst? -
    print("\n" + "=" * 72)
    print("2. Multivariate probit (standardized features, in-sample)")
    print("=" * 72)
    for spec in (["biasTotals", "totalsEst"],
                 ["biasTotals", "totalsEst", "spreadEst"]):
        m = fit_probit(feats, spec, ow, keep)
        print(f"\n  spec = {spec}   pseudoR2={m.pseudo_r2*100:.3f}%")
        print(f"    {'term':>12} {'coef':>9} {'SE':>7} {'p':>10}")
        labels = ["const"] + spec
        for lab, c, s, pv in zip(labels, m.params, m.bse, m.pvalues):
            print(f"    {lab:>12} {c:>+9.4f} {s:>7.4f} {pv:>10.2e}")

    # ---- 3. Out-of-sample k-fold bake-off ------------------------------------
    print("\n" + "=" * 72)
    print("3. 5-fold OOS bake-off (bet over where predicted P>52.38%)")
    print("=" * 72)
    specs = {
        "v1: biasTotals":        ["biasTotals"],
        "totalsEst only":        ["totalsEst"],
        "bias+totals":           ["biasTotals", "totalsEst"],
        "bias+totals+spread":    ["biasTotals", "totalsEst", "spreadEst"],
    }
    res = kfold_compare(se, te, fp, dp, specs)
    print(f"  {'spec':>20} {'bets':>6} {'win%':>7} {'unit%':>7} "
          f"{'qtrK%':>8} {'logloss':>8}")
    for name, folds in res.items():
        nb = sum(f.n_bets for f in folds)
        wins = sum(f.n_wins for f in folds)
        wr = wins / nb if nb else 0.0
        # pooled unit return and mean logloss across folds (bet-weighted)
        unit = sum(f.unit_return * f.n_bets for f in folds) / nb if nb else 0.0
        qk = np.mean([f.qtr_kelly_roi for f in folds if f.n_bets])
        ll = np.nansum([f.mean_logloss * f.n_bets for f in folds]) / nb if nb else np.nan
        print(f"  {name:>20} {nb:>6} {wr*100:>6.2f}% {unit*100:>+6.2f}% "
              f"{qk*100:>+7.1f}% {ll:>8.4f}")

    # ---- 4. Verdict cue: censoring nonlinearity beyond the line level? -------
    print("\n" + "=" * 72)
    print("4. Does the censoring TRANSFORM beat the raw total level?")
    print("=" * 72)
    # Compare in-sample fit: biasTotals alone vs totalsEst alone vs both.
    b = single["biasTotals"].pseudo_r2
    t = single["totalsEst"].pseudo_r2
    both = fit_probit(feats, ["biasTotals", "totalsEst"], ow, keep).pseudo_r2
    print(f"  pseudoR2  biasTotals={b*100:.3f}%  totalsEst={t*100:.3f}%  "
          f"both={both*100:.3f}%")
    print(f"  incremental pseudoR2 of biasTotals over totalsEst alone: "
          f"{(both - t)*100:+.3f} pp")
    print(f"  incremental pseudoR2 of totalsEst over biasTotals alone: "
          f"{(both - b)*100:+.3f} pp")


if __name__ == "__main__":
    main()
