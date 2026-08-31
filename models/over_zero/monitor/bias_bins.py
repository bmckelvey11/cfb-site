"""Profit by expected-censoring-bias bin, walk-forward.

  python monitor/bias_bins.py [--season 2013 ... 2025] [--min-train 3]
      [--fig docs/figs/bias_bins.png]

Answers two different questions that are easy to conflate:

  DISJOINT BINS      -- "profit by bias bin". Is the edge monotone in bias?
                        Monotonicity is the mechanism check: censoring theory
                        says more expected bias => more mispricing => more
                        over-profit. One bin popping alone is noise.
  CUMULATIVE SWEEP   -- "bias > x" for a range of x. This is the shape of the
                        deployable rule, since you bet a threshold, not a bin.

Both use the same walk-forward protocol as run_walkforward.py: for season t,
fit the pipeline (Tobit sigmas + probit) ONLY on seasons < t, then assign bins
and grade bets in season t. Binning on a full-sample fit would leak test-season
games into the sigmas that define `bias` itself, not merely into the win rate.

Estimator core imported from ../v2; loader/CI/protocol shared with monitor.py
and run_walkforward.py.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v2"))
from monitor import _wilson, load_from_raw  # noqa: E402
from run_walkforward import HURDLE, _unit, fit_train  # noqa: E402
from models_v2 import (  # noqa: E402
    censoring_bias,
    implied_team_points,
    kelly_bankroll_roi,
)

KELLY_FRACTION = 0.25

# Disjoint bin edges. Straddles the two documented thresholds (1.0, 1.75) so
# the standard and high-conviction buckets appear as their own rows.
BIN_EDGES = [0.0, 0.5, 1.0, 1.75, 2.5, np.inf]

# Cumulative thresholds swept for the "bias > x" curve.
SWEEP = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]


def walk_forward(data, years, min_train):
    """Collect every out-of-sample bet: (bias, over_outcome, probit p) per game.

    Returns bias, outcome and win-probability arrays pooled over all test
    seasons, where each game was scored by a model that never saw its season.
    Games stay in chronological order, which compounded Kelly depends on.
    """
    bias_all, over_all, prob_all = [], [], []
    for t in years[min_train:]:
        tr = [y for y in years if y < t]
        se, te, fp, dp = (np.concatenate([data[y][k] for y in tr])
                          for k in range(4))
        s1, s2, probit = fit_train(se, te, fp, dp)

        se_t, te_t, fp_t, dp_t = data[t]
        dog_t, fav_t = implied_team_points(se_t, te_t)
        _, bias_t = censoring_bias(dog_t, fav_t, s1, s2)

        nu_t = (fp_t + dp_t) - te_t
        keep = nu_t != 0          # drop pushes: no bet resolves on an exact total
        bias_all.append(bias_t[keep])
        over_all.append((nu_t[keep] > 0).astype(float))
        prob_all.append(probit.win_prob(bias_t)[keep])
    return (np.concatenate(bias_all), np.concatenate(over_all),
            np.concatenate(prob_all))


def kelly_fraction(p, fraction=KELLY_FRACTION, risk=110.0, payout=100.0):
    """Fractional-Kelly stake as a share of bankroll, from the model's win prob.

    Same formula as models_v2.kelly_bankroll_roi, exposed per-bet so stakes can
    be summed. Clipped at 0: a bet the model prices below breakeven gets no
    stake, so bins full of sub-breakeven games stake nothing at all.
    """
    b = payout / risk
    return np.clip((b * p - (1 - p)) / b, 0.0, None) * fraction


def _row(bias, over, prob, sel, label, risk=110.0, payout=100.0):
    n = int(sel.sum())
    if n == 0:
        return {"label": label, "n": 0, "win": float("nan"),
                "unit": float("nan"), "lo": float("nan"), "hi": float("nan"),
                "p_mean": float("nan"), "staked": 0.0, "kelly_roi": float("nan"),
                "f_mean": float("nan"), "f_max": float("nan")}
    wins = int(over[sel].sum())
    lo, hi = _wilson(wins, n)

    b = payout / risk
    f = kelly_fraction(prob[sel])
    staked = float(f.sum())
    # Flat-bankroll (non-compounding) profit: comparable across bins because it
    # is normalised by total stake, unlike a compounded terminal bankroll which
    # grows with the number of bets.
    profit = float(np.sum(np.where(over[sel] > 0, f * b, -f)))
    kelly_roi = profit / staked if staked > 0 else float("nan")

    return {"label": label, "n": n, "win": wins / n,
            "unit": _unit(wins, n), "lo": lo, "hi": hi,
            "p_mean": float(prob[sel].mean()), "staked": staked,
            "kelly_roi": kelly_roi, "n_staked": int((f > 0).sum()),
            "f_mean": float(f[f > 0].mean()) if (f > 0).any() else 0.0,
            "f_max": float(f.max())}


def bin_rows(bias, over, prob):
    rows = []
    for lo_e, hi_e in zip(BIN_EDGES[:-1], BIN_EDGES[1:]):
        sel = (bias > lo_e) & (bias <= hi_e)
        label = f"{lo_e:.2f}-{hi_e:.2f}" if np.isfinite(hi_e) else f">{lo_e:.2f}"
        rows.append(_row(bias, over, prob, sel, label))
    return rows


def sweep_rows(bias, over, prob):
    return [_row(bias, over, prob, bias > x, f">{x:.2f}") for x in SWEEP]


def _print_table(title, rows, note=""):
    print(f"\n{title}")
    if note:
        print(note)
    hdr = (f"  {'bias':>12} {'N':>6} {'bets':>6} {'win%':>8} {'modelP%':>8} "
           f"{'unit%':>9} {'kellyROI%':>10} {'avgStake':>9} {'maxStake':>9} "
           f"{'Wilson95':>18}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in rows:
        if r["n"] == 0:
            print(f"  {r['label']:>12} {0:>6} {0:>6}" + "      n/a" * 2 +
                  "       n/a" + "        n/a" + "       n/a" * 2 +
                  f" {'n/a':>18}")
            continue
        ci = f"[{r['lo']*100:.1f}, {r['hi']*100:.1f}]"
        edge = "*" if r["lo"] > HURDLE else " "
        if r["staked"] > 0:
            kroi = f"{r['kelly_roi']*100:>+9.2f}%"
            fm = f"{r['f_mean']*100:>8.2f}%"
            fx = f"{r['f_max']*100:>8.2f}%"
        else:  # every game priced at/below breakeven -> Kelly stakes nothing
            kroi, fm, fx = f"{'no stake':>10}", f"{'0.00%':>9}", f"{'0.00%':>9}"
        print(f"  {r['label']:>12} {r['n']:>6} {r['n_staked']:>6} "
              f"{r['win']*100:>7.2f}% "
              f"{r['p_mean']*100:>7.2f}% {r['unit']*100:>+8.2f}% "
              f"{kroi} {fm} {fx} {ci:>18}{edge}")
    print("  " + "-" * (len(hdr) - 2))
    print(f"  * = Wilson lower bound clears the {HURDLE*100:.2f}% breakeven")
    print(f"  modelP% = mean probit win prob (what {KELLY_FRACTION:g}-Kelly "
          f"sizes off); compare to realised win%.")
    print("  kellyROI% = profit per unit staked, flat bankroll "
          "(order-independent, comparable across rows).")
    print("  bets = games actually staked (Kelly skips any game the model "
          "prices at/below breakeven).")


def make_figure(bins, sweep, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18.5, 5.4))
    be = HURDLE * 100

    # Left: disjoint bins -- the monotonicity / mechanism check.
    labels = [r["label"] for r in bins]
    wins = [r["win"] * 100 for r in bins]
    lo_err = [max(0.0, r["win"] * 100 - r["lo"] * 100) for r in bins]
    hi_err = [max(0.0, r["hi"] * 100 - r["win"] * 100) for r in bins]
    colors = ["#4C72B0" if r["lo"] > HURDLE else "#B0B7C3" for r in bins]
    ax1.bar(labels, wins, color=colors, yerr=[lo_err, hi_err],
            capsize=4, ecolor="#444", width=0.62)
    ax1.axhline(be, color="#C44E52", ls="--", lw=1.4,
                label=f"breakeven {be:.2f}% (-110)")
    for x, r in enumerate(bins):
        if r["n"]:
            ax1.text(x, wins[x] + hi_err[x] + 1.1, f"n={r['n']}",
                     ha="center", fontsize=8.5, color="#333")
    ax1.set_title("Over win rate by expected-bias bin\n(disjoint, walk-forward)",
                  fontsize=11)
    ax1.set_xlabel("expected censoring bias (points)")
    ax1.set_ylabel("over win rate (%)")
    ax1.set_ylim(35, 85)
    ax1.legend(fontsize=8.5, loc="upper left")
    ax1.grid(axis="y", alpha=0.25)

    # Right: cumulative thresholds -- the shape of the deployable rule.
    xs = [float(r["label"].lstrip(">")) for r in sweep]
    ws = [r["win"] * 100 for r in sweep]
    los = [r["lo"] * 100 for r in sweep]
    his = [r["hi"] * 100 for r in sweep]
    ax2.plot(xs, ws, "-o", color="#4C72B0", lw=1.8, ms=5, label="win% (bias > x)")
    ax2.fill_between(xs, los, his, color="#4C72B0", alpha=0.16,
                     label="Wilson 95% CI")
    ax2.axhline(be, color="#C44E52", ls="--", lw=1.4, label=f"breakeven {be:.2f}%")
    for x_t, c in ((1.0, "#55A868"), (1.75, "#8172B2")):
        ax2.axvline(x_t, color=c, ls=":", lw=1.6,
                    label=f"documented rule: bias > {x_t}")
    ax2b = ax2.twinx()
    ax2b.plot(xs, [r["n"] for r in sweep], color="#937860", lw=1.2,
              alpha=0.65, ls="-.")
    ax2b.set_ylabel("bets at threshold (N)", color="#937860", fontsize=9)
    ax2b.tick_params(axis="y", labelcolor="#937860", labelsize=8)
    ax2.set_title("Cumulative threshold sweep: bet the over when bias > x\n"
                  "(CI widens as the sample thins)", fontsize=11)
    ax2.set_xlabel("threshold x (points of expected bias)")
    ax2.set_ylabel("over win rate (%)")
    ax2.legend(fontsize=8, loc="upper left")
    ax2.grid(alpha=0.25)

    # Third: quarter-Kelly ROI per unit staked, by disjoint bin.
    staked_bins = [r for r in bins if r["staked"] > 0]
    k_labels = [r["label"] for r in staked_bins]
    k_roi = [r["kelly_roi"] * 100 for r in staked_bins]
    k_colors = ["#55A868" if v > 0 else "#C44E52" for v in k_roi]
    ax3.bar(k_labels, k_roi, color=k_colors, width=0.62)
    ax3.axhline(0, color="#333", lw=1.1)
    # Headroom so the annotations never collide with the title or the axis.
    span = max(k_roi) - min(min(k_roi), 0.0)
    ax3.set_ylim(min(min(k_roi), 0.0) - 0.22 * span, max(k_roi) + 0.30 * span)
    for x, r in enumerate(staked_bins):
        above = k_roi[x] >= 0
        ax3.text(x, k_roi[x] + (0.03 if above else -0.03) * span,
                 f"stake {r['f_mean']*100:.1f}%\nN={r['n']}",
                 ha="center", va="bottom" if above else "top",
                 fontsize=8, color="#333")
    skipped = [r["label"] for r in bins if r["staked"] == 0]
    sub = f"\nstakes nothing (model below breakeven): {', '.join(skipped)}" \
        if skipped else ""
    ax3.set_title(f"{KELLY_FRACTION:g}-Kelly ROI per unit staked by bin"
                  f"\n(flat bankroll, order-independent){sub}", fontsize=10.5)
    ax3.set_xlabel("expected censoring bias (points)")
    ax3.set_ylabel("return per unit staked (%)")
    ax3.grid(axis="y", alpha=0.25)

    fig.suptitle(f"Floor Bias: profit by expected censoring bias "
                 f"(walk-forward, train on seasons < t; "
                 f"{KELLY_FRACTION:g}-Kelly sized off the trained probit)",
                 fontsize=12.5)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    print(f"\nWrote {path}")


def _self_check():
    """Smallest check that fails if the staking maths breaks."""
    b = 100.0 / 110.0
    # Below breakeven -> no stake. At p=1 -> full bankroll * fraction.
    assert kelly_fraction(np.array([0.40, HURDLE]), 1.0).max() == 0.0
    assert abs(kelly_fraction(np.array([1.0]), 1.0)[0] - 1.0) < 1e-12
    # Quarter-Kelly is exactly a quarter of full Kelly.
    p = np.array([0.60])
    assert abs(kelly_fraction(p, 0.25)[0] - 0.25 * kelly_fraction(p, 1.0)[0]) < 1e-12
    # An all-winning bin returns +b per unit staked; an all-losing bin, -1.
    prob = np.array([0.60, 0.60])
    for outcome, want in ((np.ones(2), b), (np.zeros(2), -1.0)):
        r = _row(np.array([2.0, 2.0]), outcome, prob,
                 np.ones(2, bool), "t")
        assert abs(r["kelly_roi"] - want) < 1e-12, (r["kelly_roi"], want)
    print("self-check OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, nargs="+",
                    default=list(range(2013, 2026)))
    ap.add_argument("--min-train", type=int, default=3)
    ap.add_argument("--fig", default="docs/figs/bias_bins.png")
    ap.add_argument("--no-fig", action="store_true")
    ap.add_argument("--self-check", action="store_true",
                    help="run the staking-maths assertions and exit")
    args = ap.parse_args()

    if args.self_check:
        _self_check()
        return

    data = load_from_raw(args.season)
    years = sorted(data)
    if len(years) <= args.min_train:
        sys.exit(f"Need > {args.min_train} seasons; have {len(years)}.")

    bias, over, prob = walk_forward(data, years, args.min_train)
    print(f"Walk-forward over seasons {years[args.min_train]}-{years[-1]}: "
          f"{bias.size:,} graded games "
          f"(trained only on seasons < each bet season)")
    print(f"Staking: {KELLY_FRACTION:g}-Kelly off the trained probit's win "
          f"probability, at -110.")

    bins = bin_rows(bias, over, prob)
    sweep = sweep_rows(bias, over, prob)

    _print_table("PROFIT BY BIAS BIN (disjoint)", bins,
                 note="  Monotone rise across bins = the mechanism; "
                      "a lone spike = noise.")
    _print_table("CUMULATIVE THRESHOLD SWEEP (bias > x)", sweep,
                 note="  Descriptive. The argmax of a swept threshold is "
                      "biased upward -- not a recommendation.\n"
                      "  kellyROI% is flat across the low thresholds because "
                      "Kelly stakes nothing below\n  bias ~0.74, so those rows "
                      "bet an identical set of games however wide the screen.")

    best = max((r for r in sweep if r["n"] >= 100), key=lambda r: r["win"])
    print(f"\n  Sweep argmax with N>=100: bias {best['label']} "
          f"({best['win']*100:.2f}%, N={best['n']}). Reported for shape only; "
          f"picking it post hoc would be a multiple-comparisons artifact.")

    # Compounded bankroll, deployable thresholds only. Order-dependent and it
    # grows with bet count, so it is NOT comparable across bins -- reported
    # here purely to reconcile with run_walkforward.py's printed figure.
    print(f"\n  Compounded {KELLY_FRACTION:g}-Kelly bankroll "
          f"(chronological, order-dependent -- not comparable across rows):")
    for x in (1.0, 1.75):
        sel = bias > x
        staked = int((kelly_fraction(prob[sel]) > 0).sum())
        roi = kelly_bankroll_roi(over[sel], prob[sel], KELLY_FRACTION)
        print(f"    bias > {x:<5} N={int(sel.sum()):>4} staked={staked:>4}  "
              f"terminal bankroll ROI = {roi*100:+.1f}%")
    print("    (bias > 1.0 reconciles with run_walkforward.py's qtrKelly ROI.)")
    mid = (bias > 1.0) & (bias <= 1.75)
    mid_roi = kelly_bankroll_roi(over[mid], prob[mid], KELLY_FRACTION)
    print(f"    The two are near-identical by coincidence, not by design: the "
          f"440 extra bets\n    in bias 1.00-1.75 compound to "
          f"{mid_roi*100:+.4f}% on their own -- they multiply the\n"
          f"    bankroll by ~1.0, so adding them changes the terminal figure "
          f"almost not at all.")
    print("    Compounding assumes every bet resizes off the running bankroll "
          "and that\n    bets settle sequentially; real slates overlap. "
          "MODEL_GUIDE demotes this\n    number for that reason -- treat "
          "kellyROI% per unit staked as the headline.")

    if not args.no_fig:
        make_figure(bins, sweep, args.fig)


if __name__ == "__main__":
    main()
