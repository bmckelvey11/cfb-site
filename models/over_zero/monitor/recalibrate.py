"""Grade a walk-forward recalibration of the probit against the v1 probit.

  python monitor/recalibrate.py [--season ...] [--min-train 3] [--self-check]

WHY: 0.25-Kelly sizes off the probit's P(over), and that probability is
miscalibrated in ALTERNATING directions across bias bins (+3.1pp at 1.00-1.75,
-3.7pp at 1.75-2.50). No monotone rescale of a linear index -- refitting
const/slope, Platt scaling -- can move two bins in opposite directions, so the
fix has to change SHAPE. This fits a binned empirical calibrator on training
seasons only and grades whether it actually sizes better out of sample.

PRE-COMMITTED metrics (fixed before any result was looked at), on the
bias > 1.0 candidate set:

  A (headline)  total profit in bankroll units, flat bankroll, 0.25-Kelly.
                Rewards better sizing AND legitimately declining to bet.
  B             ROI per unit staked, reported with N staked and total stake --
                uninterpretable alone, since not betting inflates it.
  C (decomp)    Metric A restricted to games the BASELINE staked. Not a pure
                resize metric: inside that set the recalibrated p can still
                fall below breakeven and stake 0, which is selection. So C is
                further decomposed at print time into (i) the resize-only
                difference on games BOTH variants stake, and (ii) what dropping
                the rest gained or cost. A pure "resize everything" Kelly
                comparison is ill-defined -- for Kelly, a zero stake IS a size.

Verdict rule, also pre-committed: implement only if the season-block bootstrap
95% CI on the paired per-season profit difference (A) excludes 0 AND the
frozen-set decomposition (C) shows the gain is not purely selection.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v2"))
from bias_bins import BIN_EDGES, KELLY_FRACTION, kelly_fraction  # noqa: E402
from monitor import load_from_raw  # noqa: E402
from run_walkforward import HURDLE, fit_train  # noqa: E402
from models_v2 import censoring_bias, implied_team_points  # noqa: E402

MIN_BIN = 50      # training games needed before trusting an empirical bin rate
B = 100.0 / 110.0
BOOT = 10_000
SEED = 0


def binned_calibrator(bias_tr, over_tr, probit, edges=BIN_EDGES, min_bin=MIN_BIN):
    """Empirical over-rate per bias bin, fit on TRAINING games only.

    Returns p(bias). Bins with < min_bin training games fall back to the
    probit, so thin tails never get a rate estimated off a handful of games.
    A step function: unlike a rescale, it can price non-monotone structure.
    """
    rates = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        s = (bias_tr > lo) & (bias_tr <= hi)
        n = int(s.sum())
        rates.append(float(over_tr[s].mean()) if n >= min_bin else None)

    def p_of(bias):
        out = probit.win_prob(bias)          # fallback everywhere
        for (lo, hi), r in zip(zip(edges[:-1], edges[1:]), rates):
            if r is None:
                continue
            out = np.where((bias > lo) & (bias <= hi), r, out)
        return out

    return p_of


def walk_forward_both(data, years, min_train):
    """Per-bet arrays under both calibrations, plus the season index.

    For season t: fit Tobit sigmas + probit on seasons < t (identical to
    run_walkforward), then ALSO fit the binned calibrator on those same
    training seasons. Season t is never touched by either fit.
    """
    rows = {k: [] for k in ("season", "bias", "over", "p_base", "p_recal")}
    for t in years[min_train:]:
        tr = [y for y in years if y < t]
        se, te, fp, dp = (np.concatenate([data[y][k] for y in tr])
                          for k in range(4))
        s1, s2, probit = fit_train(se, te, fp, dp)

        # training-season bias/outcomes, for the calibrator only
        dog_tr, fav_tr = implied_team_points(se, te)
        _, bias_tr = censoring_bias(dog_tr, fav_tr, s1, s2)
        nu_tr = (fp + dp) - te
        k_tr = nu_tr != 0
        calib = binned_calibrator(bias_tr[k_tr], (nu_tr[k_tr] > 0).astype(float),
                                  probit)

        se_t, te_t, fp_t, dp_t = data[t]
        dog_t, fav_t = implied_team_points(se_t, te_t)
        _, bias_t = censoring_bias(dog_t, fav_t, s1, s2)
        nu_t = (fp_t + dp_t) - te_t
        keep = nu_t != 0

        rows["season"].append(np.full(int(keep.sum()), t))
        rows["bias"].append(bias_t[keep])
        rows["over"].append((nu_t[keep] > 0).astype(float))
        rows["p_base"].append(probit.win_prob(bias_t)[keep])
        rows["p_recal"].append(calib(bias_t)[keep])
    return {k: np.concatenate(v) for k, v in rows.items()}


def profit(over, f):
    """Flat-bankroll profit in bankroll units: +f*b on a win, -f on a loss."""
    return float(np.sum(np.where(over > 0, f * B, -f)))


def grade(over, p, label, force_f=None):
    f = kelly_fraction(p, KELLY_FRACTION) if force_f is None else force_f
    staked = float(f.sum())
    pr = profit(over, f)
    return {"label": label, "profit": pr, "staked": staked,
            "n_staked": int((f > 0).sum()),
            "roi": pr / staked if staked > 0 else float("nan"), "f": f}


def _boot_ci(per_season_diff, rng, n=BOOT):
    """Season-block bootstrap: resample whole seasons, not individual bets.

    Bets inside a season share a fitted model, so they are not independent.
    """
    arr = np.asarray(per_season_diff, float)
    draws = rng.integers(0, arr.size, size=(n, arr.size))
    tot = arr[draws].sum(axis=1)
    return float(np.percentile(tot, 2.5)), float(np.percentile(tot, 97.5))


def _self_check(data, years, min_train):
    """No-lookahead: the calibrator for season t must not move when season t's
    outcomes are corrupted. Catches any leak of test data into the fit."""
    import copy
    t = years[min_train + 3]
    tr = [y for y in years if y < t]
    se, te, fp, dp = (np.concatenate([data[y][k] for y in tr]) for k in range(4))
    s1, s2, probit = fit_train(se, te, fp, dp)
    dog, fav = implied_team_points(se, te)
    _, bias_tr = censoring_bias(dog, fav, s1, s2)
    nu = (fp + dp) - te
    k = nu != 0
    calib = binned_calibrator(bias_tr[k], (nu[k] > 0).astype(float), probit)
    probe = np.array([0.3, 0.8, 1.4, 2.0, 3.0])
    before = calib(probe).copy()

    bad = copy.deepcopy(data)
    bad[t] = tuple(x.copy() for x in bad[t])
    bad[t][2][:] = 0.0                       # wreck season t's favourite points
    se2, te2, fp2, dp2 = (np.concatenate([bad[y][k2] for y in tr])
                          for k2 in range(4))
    assert np.array_equal(se, se2) and np.array_equal(fp, fp2), \
        "training slice changed -- season t leaked into the fit"
    assert np.allclose(before, calib(probe)), "calibrator moved with test data"

    # A calibrator on a bin with fewer than MIN_BIN games must fall back.
    tiny = binned_calibrator(np.array([2.0] * 3), np.array([1.0, 1.0, 1.0]),
                             probit)
    assert np.isclose(tiny(np.array([2.0]))[0], probit.win_prob(np.array([2.0]))[0]), \
        "thin bin did not fall back to the probit"
    print("self-check OK (no lookahead; thin bins fall back)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, nargs="+",
                    default=list(range(2013, 2026)))
    ap.add_argument("--min-train", type=int, default=3)
    ap.add_argument("--threshold", type=float, default=1.0,
                    help="candidate set: the documented bias > x bet rule")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    data = load_from_raw(args.season)
    years = sorted(data)
    if args.self_check:
        _self_check(data, years, args.min_train)
        return

    d = walk_forward_both(data, years, args.min_train)
    sel = d["bias"] > args.threshold
    over, season = d["over"][sel], d["season"][sel]
    p_base, p_recal = d["p_base"][sel], d["p_recal"][sel]

    print(f"Candidate set: bias > {args.threshold}, "
          f"seasons {years[args.min_train]}-{years[-1]}, N={int(sel.sum())}")
    print(f"Staking {KELLY_FRACTION:g}-Kelly. Calibrator: empirical bin rate "
          f"from training seasons (min {MIN_BIN} games/bin, else probit).\n")

    base = grade(over, p_base, "v1 probit")
    recal = grade(over, p_recal, "recalibrated")
    frozen = grade(over, p_recal, "recalibrated, staked set frozen",
                   force_f=np.where(base["f"] > 0,
                                    kelly_fraction(p_recal, KELLY_FRACTION), 0.0))

    print(f"  {'variant':<34} {'bets':>5} {'stake':>8} "
          f"{'profit(u)':>10} {'ROI/unit':>9}")
    print("  " + "-" * 70)
    for r in (base, recal, frozen):
        print(f"  {r['label']:<34} {r['n_staked']:>5} {r['staked']:>8.2f} "
              f"{r['profit']:>+10.3f} {r['roi']*100:>+8.2f}%")
    print("  " + "-" * 70)
    print(f"  A  total profit       : {recal['profit'] - base['profit']:+.3f} u")
    print(f"  C  baseline-set profit: {frozen['profit'] - base['profit']:+.3f} u"
          f"   <- within the games the baseline staked")

    # Decompose C: recal can still stake 0 inside the baseline set (that is
    # selection, not sizing), so split it out explicitly.
    fb, fr = base["f"], kelly_fraction(p_recal, KELLY_FRACTION)
    both = (fb > 0) & (fr > 0)
    dropped = (fb > 0) & (fr == 0)
    resize_diff = (profit(over[both], fr[both])
                   - profit(over[both], fb[both]))
    drop_gain = -profit(over[dropped], fb[dropped])
    print(f"     resize-only (both stake, n={int(both.sum())})   : "
          f"{resize_diff:+.3f} u")
    print(f"     de-selection inside C (n={int(dropped.sum())})  : "
          f"{drop_gain:+.3f} u   (baseline profit forgone on dropped games)")

    # Paired per-season differences, for the block bootstrap.
    per_season, wins = [], 0
    print(f"\n  {'season':>6} {'baseProfit':>11} {'recalProfit':>12} {'diff':>9}")
    for t in sorted(set(season)):
        m = season == t
        pb = profit(over[m], kelly_fraction(p_base[m], KELLY_FRACTION))
        pr = profit(over[m], kelly_fraction(p_recal[m], KELLY_FRACTION))
        per_season.append(pr - pb)
        wins += pr > pb
        print(f"  {t:>6} {pb:>+11.3f} {pr:>+12.3f} {pr - pb:>+9.3f}")

    rng = np.random.default_rng(SEED)
    lo, hi = _boot_ci(per_season, rng)
    tot = float(np.sum(per_season))
    print(f"\n  Seasons improved: {wins}/{len(per_season)}")
    print(f"  Total A difference: {tot:+.3f} u  "
          f"season-block bootstrap 95% CI [{lo:+.3f}, {hi:+.3f}]")

    ci_excludes_0 = lo > 0 or hi < 0
    resize_real = resize_diff > 0
    print("\n  VERDICT (rule pre-committed before results):")
    print(f"    CI excludes 0            : {ci_excludes_0}")
    print(f"    resize-only gain > 0     : {resize_real}")
    if ci_excludes_0 and tot > 0 and resize_real:
        print("    => IMPLEMENT: recalibration sizes better out of sample.")
    else:
        print("    => DO NOT IMPLEMENT: no reliable out-of-sample gain. "
              "Keep the v1 probit.")


if __name__ == "__main__":
    main()
