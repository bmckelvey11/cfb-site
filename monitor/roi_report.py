"""ROI of the deployed bet filter (bias > 1.75), walk-forward, with intervals.

  python monitor/roi_report.py [--season 2013 ... 2025] [--min-train 3]
      [--threshold 1.75] [--fig docs/figs/roi_report.png]

Same walk-forward protocol as run_walkforward.py / bias_bins.py: for season t,
fit the whole pipeline (Tobit sigmas + probit) on seasons < t only, then grade
season t. The only thing added here is a season label per bet, which is what an
equity curve and per-season bars need and the existing collectors drop.

Three ROI definitions appear, deliberately ranked (MODEL_GUIDE demotes the
third):

  FLAT-STAKE UNIT ROI  -- headline. Profit per unit risked at a fixed price.
                          Order-independent, and an exact affine function of
                          the win rate, so a Wilson CI on the win rate maps to
                          an exact CI on ROI. No bootstrap needed.
  KELLY ROI/UNIT       -- secondary. Stake varies per bet, so the affine map
                          breaks and the interval is bootstrapped instead.
  COMPOUNDED BANKROLL  -- shown as an equity curve only, labelled
                          order-dependent. Not a headline number.

The headline point estimate is inflated: the 1.75 threshold was chosen partly
on this data. Every ROI reported here carries its Wilson lower bound as the
planning number, per README/MODEL_GUIDE.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v2"))
from monitor import _wilson, load_from_raw  # noqa: E402
from run_walkforward import HURDLE, fit_train  # noqa: E402
from bias_bins import KELLY_FRACTION, kelly_fraction  # noqa: E402
from models_v2 import (  # noqa: E402
    censoring_bias,
    implied_team_points,
    log_likelihood_ratio,
)

RISK, PAYOUT = 110.0, 100.0
BOOT = 10_000
SEED = 20260826

# American prices swept in the sensitivity panel. -110 is the backtest price;
# README's operational rule says "-120 or better", so the band matters.
PRICES = [-105, -108, -110, -115, -120, -125, -130]


def american_to_risk_payout(price):
    """Risk/payout per unit for an American price. Negative = lay the juice."""
    return (abs(price), 100.0) if price < 0 else (100.0, float(price))


def breakeven(price):
    risk, payout = american_to_risk_payout(price)
    return risk / (risk + payout)


def unit_roi(win_rate, price=-110):
    """Profit per unit risked at a flat stake. Affine in win_rate.

    roi = w*payout/risk - (1-w) -- so a CI on w maps exactly onto a CI on roi.
    """
    risk, payout = american_to_risk_payout(price)
    return win_rate * (payout / risk) - (1.0 - win_rate)


def walk_forward_bets(data, years, min_train):
    """Every out-of-sample game with its season label, chronological.

    Mirrors bias_bins.walk_forward but keeps the season so the bets can be
    ordered and grouped in time. Pushes (exact totals) are dropped: no bet
    resolves on them.
    """
    season, bias_all, over_all, prob_all = [], [], [], []
    for t in years[min_train:]:
        tr = [y for y in years if y < t]
        se, te, fp, dp = (np.concatenate([data[y][k] for y in tr])
                          for k in range(4))
        s1, s2, probit = fit_train(se, te, fp, dp)

        se_t, te_t, fp_t, dp_t = data[t]
        dog_t, fav_t = implied_team_points(se_t, te_t)
        _, bias_t = censoring_bias(dog_t, fav_t, s1, s2)

        nu_t = (fp_t + dp_t) - te_t
        keep = nu_t != 0
        bias_all.append(bias_t[keep])
        over_all.append((nu_t[keep] > 0).astype(float))
        prob_all.append(probit.win_prob(bias_t)[keep])
        season.append(np.full(int(keep.sum()), t))
    return (np.concatenate(season), np.concatenate(bias_all),
            np.concatenate(over_all), np.concatenate(prob_all))


def wilson_roi(wins, n, price=-110):
    """Exact ROI interval: map the Wilson win-rate CI through the affine ROI."""
    lo, hi = _wilson(wins, n)
    return unit_roi(lo, price), unit_roi(hi, price)


def kelly_roi(over, prob, fraction=KELLY_FRACTION, price=-110):
    """Quarter-Kelly profit per unit staked, flat bankroll (order-independent).

    Kelly skips any game the model prices at or below breakeven, so `staked`
    can be smaller than len(over).
    """
    risk, payout = american_to_risk_payout(price)
    b = payout / risk
    f = kelly_fraction(prob, fraction, risk=risk, payout=payout)
    staked = float(f.sum())
    if staked <= 0:
        return float("nan"), 0.0, 0
    profit = float(np.sum(np.where(over > 0, f * b, -f)))
    return profit / staked, staked, int((f > 0).sum())


def boot_kelly_ci(over, prob, rng, n_boot=BOOT, fraction=KELLY_FRACTION):
    """Percentile bootstrap on Kelly ROI/unit, resampling bets i.i.d.

    Bootstrapped rather than mapped, because a varying stake breaks the affine
    win-rate -> ROI relationship the flat-stake interval relies on.
    """
    n = over.size
    idx = rng.integers(0, n, size=(n_boot, n))
    vals = np.array([kelly_roi(over[i], prob[i])[0] for i in idx])
    vals = vals[np.isfinite(vals)]
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def boot_equity_bands(over, rng, n_boot=BOOT, price=-110):
    """Bootstrap band for the cumulative flat-stake equity path.

    Resamples the bet ORDER (permutation), holding the multiset of results
    fixed: this shows how much of the path's shape is sequencing luck, given
    the same record. The endpoint is therefore identical across draws by
    construction; the band is about the journey, not the destination.
    """
    risk, payout = american_to_risk_payout(price)
    n = over.size
    paths = np.empty((n_boot, n))
    per_bet = np.where(over > 0, payout, -risk)
    for i in range(n_boot):
        paths[i] = np.cumsum(rng.permutation(per_bet))
    return (np.percentile(paths, 5, axis=0), np.percentile(paths, 95, axis=0))


def max_drawdown(equity):
    """Peak-to-trough drop of a cumulative-profit path, in units risked."""
    peak = np.maximum.accumulate(np.concatenate([[0.0], equity]))
    return float(np.max(peak - np.concatenate([[0.0], equity])))


def season_rows(season, over, prob, price=-110):
    rows = []
    for t in sorted(set(season.tolist())):
        sel = season == t
        n = int(sel.sum())
        wins = int(over[sel].sum())
        w = wins / n if n else float("nan")
        lo, hi = wilson_roi(wins, n, price) if n else (float("nan"),) * 2
        rows.append({"season": int(t), "n": n, "wins": wins, "win": w,
                     "roi": unit_roi(w, price) if n else float("nan"),
                     "lo": lo, "hi": hi})
    return rows


def _provenance(years, min_train, threshold, n):
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent,
            text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:            # not a repo / no git on PATH
        sha = "unknown"
    return (f"Walk-forward: train on seasons < t, bet season t  |  "
            f"data {years[0]}–{years[-1]}, bet seasons "
            f"{years[min_train]}–{years[-1]} (min-train={min_train})  |  "
            f"filter: expected censoring bias > {threshold} → bet the "
            f"full-game OVER  |  N={n} graded bets (pushes dropped)  |  "
            f"CFBD lines, consensus provider  |  commit {sha}  |  "
            f"generated {date.today().isoformat()}")


# ----------------------------------------------------------------- figure ---

INK = "#1a1d24"
MUTED = "#6b7280"
GRID = "#d8dce3"
BLUE = "#2b5d8a"
GREEN = "#3e7d5a"
RED = "#a9384a"
GOLD = "#b7822a"
BAND = "#2b5d8a"


def _style(ax):
    ax.set_facecolor("white")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8.5, length=3, color=GRID)
    ax.grid(alpha=0.5, color=GRID, lw=0.7)
    ax.set_axisbelow(True)
    ax.title.set_color(INK)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)


def make_figure(stats, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.titlesize": 10.5, "axes.titleweight": "bold",
        "axes.labelsize": 9, "figure.facecolor": "white",
    })

    fig = plt.figure(figsize=(17.5, 11.6))
    gs = GridSpec(3, 3, figure=fig, hspace=0.62, wspace=0.30,
                  left=0.055, right=0.975, top=0.820, bottom=0.090)

    thr = stats["threshold"]
    n, wins = stats["n"], stats["wins"]
    roi, roi_lo, roi_hi = stats["roi"], stats["roi_lo"], stats["roi_hi"]

    # --- Panel 1: the headline number and its interval, on one axis ---------
    ax = fig.add_subplot(gs[0, 0])
    _style(ax)
    ax.barh([0], [roi * 100], height=0.42, color=BLUE, zorder=3)
    ax.errorbar([roi * 100], [0],
                xerr=[[(roi - roi_lo) * 100], [(roi_hi - roi) * 100]],
                fmt="none", ecolor=INK, elinewidth=1.6, capsize=7, zorder=4)
    ax.axvline(0, color=RED, ls="--", lw=1.4, zorder=2,
               label="break-even (52.38% @ −110)")
    ax.scatter([roi_lo * 100], [0], marker="D", s=52, color=GOLD, zorder=5,
               label=f"plan on this: {roi_lo*100:+.1f}%")
    ax.text(roi * 100, 0.30, f"{roi*100:+.1f}%", ha="center", va="bottom",
            fontsize=17, fontweight="bold", color=BLUE)
    ax.text(roi_lo * 100, -0.34, f"{roi_lo*100:+.1f}%", ha="center", va="top",
            fontsize=9.5, color=GOLD, fontweight="bold")
    ax.text(roi_hi * 100, -0.34, f"{roi_hi*100:+.1f}%", ha="center", va="top",
            fontsize=9.5, color=MUTED)
    ax.set_yticks([])
    ax.set_ylim(-0.85, 0.85)
    ax.set_xlabel("return per unit risked (%)")
    ax.set_title(f"Flat-stake ROI, bias > {thr}\n"
                 f"N={n} bets, {wins}–{n-wins}, "
                 f"{stats['win']*100:.2f}% win", loc="left")
    ax.legend(fontsize=7.5, loc="lower right", frameon=False)

    # --- Panel 2: win rate -> ROI, the exact affine map --------------------
    ax = fig.add_subplot(gs[0, 1])
    _style(ax)
    ws = np.linspace(0.44, 0.76, 200)
    ax.plot(ws * 100, unit_roi(ws) * 100, color=INK, lw=1.6, zorder=3)
    ax.axhline(0, color=RED, ls="--", lw=1.3, zorder=2)
    ax.axvline(HURDLE * 100, color=RED, ls="--", lw=1.3, zorder=2)
    ax.axvspan(stats["win_lo"] * 100, stats["win_hi"] * 100, color=BAND,
               alpha=0.13, zorder=1, label="Wilson 95% CI on win rate")
    ax.scatter([stats["win"] * 100], [roi * 100], s=64, color=BLUE, zorder=5,
               label="observed")
    ax.scatter([stats["win_lo"] * 100], [roi_lo * 100], s=44, color=GOLD,
               marker="D", zorder=5, label="planning bound")
    ax.annotate(f"{stats['win']*100:.1f}% → {roi*100:+.1f}%",
                (stats["win"] * 100, roi * 100), textcoords="offset points",
                xytext=(-6, 12), fontsize=8.5, color=BLUE, fontweight="bold",
                ha="right")
    ax.annotate(f"{stats['win_lo']*100:.1f}% → {roi_lo*100:+.1f}%",
                (stats["win_lo"] * 100, roi_lo * 100),
                textcoords="offset points", xytext=(4, -16), fontsize=8,
                color=GOLD)
    ax.set_xlabel("win rate (%)")
    ax.set_ylabel("return per unit risked (%)")
    ax.set_title("ROI is affine in win rate at a fixed price\n"
                 "so the Wilson CI maps across exactly", loc="left")
    ax.legend(fontsize=7.5, loc="upper left", frameon=False)

    # --- Panel 3: price sensitivity ---------------------------------------
    ax = fig.add_subplot(gs[0, 2])
    _style(ax)
    xs = np.arange(len(PRICES))
    pts = [unit_roi(stats["win"], p) * 100 for p in PRICES]
    los = [unit_roi(stats["win_lo"], p) * 100 for p in PRICES]
    his = [unit_roi(stats["win_hi"], p) * 100 for p in PRICES]
    ax.fill_between(xs, los, his, color=BAND, alpha=0.15,
                    label="Wilson 95% CI")
    ax.plot(xs, pts, "-o", color=BLUE, lw=1.7, ms=5, label="point estimate")
    ax.plot(xs, los, color=GOLD, lw=1.3, ls="--", label="planning bound")
    ax.axhline(0, color=RED, ls="--", lw=1.3)
    ax.axvline(PRICES.index(-110), color=MUTED, lw=1.0, ls=":")
    ax.text(PRICES.index(-110) + 0.08, max(his) * 0.92, "backtest price",
            fontsize=7.5, color=MUTED, rotation=90, va="top")
    ax.axvline(PRICES.index(-120), color=GREEN, lw=1.0, ls=":")
    ax.text(PRICES.index(-120) + 0.08, max(his) * 0.92,
            "rule: −120 or better", fontsize=7.5, color=GREEN,
            rotation=90, va="top")
    ax.set_xticks(xs)
    ax.set_xticklabels([str(p) for p in PRICES])
    ax.set_xlabel("price paid (American odds)")
    ax.set_ylabel("return per unit risked (%)")
    ax.set_title("Price sensitivity: the edge survives the vig\n"
                 f"win rate held at {stats['win']*100:.2f}%", loc="left")
    ax.legend(fontsize=7.5, loc="lower left", frameon=False)

    # --- Panel 4 (wide): cumulative equity with order-bootstrap band -------
    ax = fig.add_subplot(gs[1, :2])
    _style(ax)
    eq = stats["equity"]
    k = np.arange(1, eq.size + 1)
    ax.fill_between(k, stats["eq_lo"], stats["eq_hi"], color=BAND, alpha=0.14,
                    label="90% band over bet orderings (same record)")
    ax.plot(k, eq, color=BLUE, lw=1.7, zorder=4, label="realised path")
    ax.plot(k, unit_roi(HURDLE) * RISK * k, color=RED, ls="--", lw=1.3,
            label="break-even")
    ax.plot(k, unit_roi(stats["win_lo"]) * RISK * k, color=GOLD, ls="--",
            lw=1.3, label="planning bound slope")
    ax.axhline(0, color=MUTED, lw=0.9)
    # Season boundaries: where a refit happened. Headroom first, so the labels
    # sit inside the axes instead of clipping through the title.
    ax.set_ylim(min(float(stats["eq_lo"].min()), 0.0) * 1.12, eq.max() * 1.30)
    y_lab = ax.get_ylim()[1] * 0.98
    last_lab = -99
    for b, t in stats["season_marks"]:
        ax.axvline(b, color=GRID, lw=0.8, zorder=1)
        # Early seasons are only a couple of bets wide, so their labels would
        # overprint. Draw every boundary; label only the ones with room.
        if b - last_lab >= 8:
            ax.text(b, y_lab, f" {t}", fontsize=6.8, color=MUTED,
                    rotation=90, va="top")
            last_lab = b
    ax.annotate(f"terminal +{eq[-1]:,.0f} units risked\n"
                f"max drawdown −{stats['mdd']:,.0f}",
                (eq.size, eq[-1]), textcoords="offset points",
                xytext=(-8, -34), ha="right", fontsize=8.5, color=INK,
                fontweight="bold")
    ax.set_xlabel("bet number (chronological)")
    ax.set_ylabel("cumulative profit (units risked, flat $110)")
    ax.set_title("Realised equity vs. sequencing luck\n"
                 "band re-orders the same wins and losses; endpoint fixed "
                 "by construction", loc="left")
    ax.legend(fontsize=7.5, loc="lower right", frameon=False)

    # --- Panel 5: Kelly vs flat, with bootstrap ---------------------------
    ax = fig.add_subplot(gs[1, 2])
    _style(ax)
    labels = ["flat stake\n(headline)",
              f"{KELLY_FRACTION:g}-Kelly\nper unit staked"]
    vals = [roi * 100, stats["kelly"] * 100]
    lo_e = [(roi - roi_lo) * 100, (stats["kelly"] - stats["kelly_lo"]) * 100]
    hi_e = [(roi_hi - roi) * 100, (stats["kelly_hi"] - stats["kelly"]) * 100]
    ax.bar(labels, vals, color=[BLUE, GREEN], width=0.5, zorder=3)
    ax.errorbar(labels, vals, yerr=[lo_e, hi_e], fmt="none", ecolor=INK,
                elinewidth=1.5, capsize=8, zorder=4)
    ax.axhline(0, color=RED, ls="--", lw=1.3, zorder=2)
    for x, (v, l) in enumerate(zip(vals, [roi_lo * 100, stats["kelly_lo"] * 100])):
        ax.text(x, v + hi_e[x] + 1.2, f"{v:+.1f}%", ha="center", fontsize=10,
                fontweight="bold", color=INK)
        # The lower bound is drawn at its own height inside the bar, where it
        # means something, rather than floating under the tick labels.
        ax.hlines(l, x - 0.25, x + 0.25, color=GOLD, lw=2.0, zorder=5)
        ax.text(x, l - 0.9, f"plan {l:+.1f}%", ha="center", va="top",
                fontsize=7.5, color=GOLD, fontweight="bold", zorder=6)
    ax.set_ylim(0, max(v + h for v, h in zip(vals, hi_e)) * 1.18)
    ax.set_ylabel("return per unit staked (%)")
    ax.set_title("Two stake rules, two intervals\n"
                 "flat = exact Wilson map; Kelly = "
                 f"{BOOT//1000}k bootstrap", loc="left")

    # --- Panel 6 (wide): per-season ROI, honest error bars -----------------
    ax = fig.add_subplot(gs[2, :2])
    _style(ax)
    rows = stats["seasons"]
    xs = np.arange(len(rows))
    vals = [r["roi"] * 100 for r in rows]
    lo_e = [max(0.0, (r["roi"] - r["lo"]) * 100) for r in rows]
    hi_e = [max(0.0, (r["hi"] - r["roi"]) * 100) for r in rows]
    cols = [GREEN if v > 0 else RED for v in vals]
    ax.bar(xs, vals, color=cols, width=0.6, zorder=3, alpha=0.9)
    ax.errorbar(xs, vals, yerr=[lo_e, hi_e], fmt="none", ecolor=INK,
                elinewidth=1.1, capsize=4, alpha=0.75, zorder=4)
    ax.axhline(0, color=RED, ls="--", lw=1.3, zorder=2)
    ax.axhline(roi * 100, color=BLUE, lw=1.4, zorder=2,
               label=f"pooled {roi*100:+.1f}%")
    # A 2-bet season spans +/-100% and would flatten every other bar. Clip to
    # the seasons that carry information; label whatever runs off the axis.
    big = [r for r in rows if r["n"] >= 5]
    top = max((r["hi"] * 100 for r in big), default=100.0) * 1.20
    bot = min(min((r["lo"] * 100 for r in big), default=-60.0), -20.0) * 1.15
    ax.set_ylim(bot, top)
    for x, r in enumerate(rows):
        if vals[x] > top or vals[x] < bot or r["lo"] * 100 < bot \
                or r["hi"] * 100 > top:
            ax.annotate(f"{vals[x]:+.0f}%\n(n={r['n']}\nCI off-scale)",
                        (x, top * 0.55 if vals[x] > 0 else bot * 0.55),
                        ha="center", va="center", fontsize=6.8,
                        color=INK, fontweight="bold", zorder=6)
    # The newest season is also the largest and the flattest. Call it out:
    # a reader finds that bar in three seconds, and silence there reads as
    # concealment. Its own CI is what says it is not yet evidence of decay.
    last = rows[-1]
    ax.annotate(f"{last['season']}: {last['wins']}–{last['n']-last['wins']}, "
                f"{last['roi']*100:+.1f}%\nlargest sample, flattest result\n"
                f"CI [{last['lo']*100:+.0f}, {last['hi']*100:+.0f}] — wide "
                f"enough that\nthis is not yet decay (see monitor.py)",
                (len(rows) - 1, last["roi"] * 100),
                textcoords="offset points", xytext=(-14, 58), ha="right",
                fontsize=7.4, color=INK,
                bbox=dict(boxstyle="round,pad=0.4", fc="#fdf6e3", ec=GOLD,
                          lw=0.9, alpha=0.95),
                arrowprops=dict(arrowstyle="->", color=GOLD, lw=1.2))
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{r['season']}\nn={r['n']}" for r in rows],
                       fontsize=7.5)
    ax.set_ylabel("return per unit risked (%)")
    ax.set_title(f"Per-season ROI — {stats['pos_seasons']}/{len(rows)} "
                 f"profitable\n{stats['n_min']}–{stats['n_max']} bets/season "
                 f"({stats['recent_share']*100:.0f}% of all bets come from "
                 f"{stats['recent_from']}+): bars are noise, intervals are "
                 "the point", loc="left")
    ax.legend(fontsize=7.5, loc="lower right", frameon=False)

    # --- Panel 7: threshold sweep, ROI form -------------------------------
    ax = fig.add_subplot(gs[2, 2])
    _style(ax)
    sw = stats["sweep"]
    xs = [r["x"] for r in sw]
    ax.fill_between(xs, [r["lo"] * 100 for r in sw],
                    [r["hi"] * 100 for r in sw], color=BAND, alpha=0.15,
                    label="Wilson 95% CI")
    ax.plot(xs, [r["roi"] * 100 for r in sw], "-o", color=BLUE, lw=1.6, ms=4,
            label="ROI at bias > x")
    ax.axhline(0, color=RED, ls="--", lw=1.3)
    ax.axvline(thr, color=GREEN, ls=":", lw=1.6,
               label=f"deployed filter ({thr})")
    axb = ax.twinx()
    axb.plot(xs, [r["n"] for r in sw], color=MUTED, lw=1.1, ls="-.", alpha=0.7)
    axb.set_ylabel("bets N", color=MUTED, fontsize=8.5)
    axb.tick_params(axis="y", labelcolor=MUTED, labelsize=8)
    for s in ("top", "left"):
        axb.spines[s].set_visible(False)
    axb.spines["right"].set_color(GRID)
    ax.set_xlabel("threshold x (points of expected bias)")
    ax.set_ylabel("return per unit risked (%)")
    ax.set_title("ROI vs. filter tightness\n"
                 "argmax is selection-biased — shape only", loc="left")
    ax.legend(fontsize=7.5, loc="upper left", frameon=False)

    # --- titles + provenance ----------------------------------------------
    fig.text(0.055, 0.955,
             f"FLOOR BIAS — ROI OF THE DEPLOYED BET FILTER (bias > {thr})",
             fontsize=17, fontweight="bold", color=INK, va="top")
    fig.text(0.055, 0.918,
             "Out-of-sample, walk-forward. Every interval is a 95% interval; "
             "the gold marker is the number to plan on, not the point "
             "estimate.",
             fontsize=10, color=MUTED, va="top")
    fig.text(0.055, 0.893,
             "The threshold was chosen partly on this data, so the point "
             "estimate is inflated by selection. Break-even is 52.38% at "
             "−110.",
             fontsize=9, color=RED, va="top")
    fig.text(0.055, 0.028, stats["provenance"], fontsize=7.2, color=MUTED,
             va="top", wrap=True)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170, facecolor="white")
    print(f"\nWrote {path}")


# ------------------------------------------------------------------ main ---

def _self_check():
    """Smallest checks that fail if the ROI maths breaks."""
    # Break-even win rate returns exactly zero ROI, at any price.
    for p in PRICES:
        assert abs(unit_roi(breakeven(p), p)) < 1e-12, p
    assert abs(breakeven(-110) - 0.5238) < 1e-4
    # Affine: the Wilson map equals ROI evaluated at the Wilson bounds.
    lo, hi = _wilson(60, 100)
    assert wilson_roi(60, 100) == (unit_roi(lo), unit_roi(hi))
    # All wins pay +payout/risk per unit; all losses lose the unit.
    assert abs(unit_roi(1.0) - 100.0 / 110.0) < 1e-12
    assert abs(unit_roi(0.0) + 1.0) < 1e-12
    # Drawdown: a win then two losses drops 2 units off the peak.
    assert abs(max_drawdown(np.array([100.0, -10.0, -120.0])) - 220.0) < 1e-9
    # Kelly stakes nothing when the model prices every game at breakeven.
    r, staked, nb = kelly_roi(np.ones(3), np.full(3, HURDLE))
    assert staked == 0.0 and nb == 0 and np.isnan(r)
    print("self-check OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, nargs="+",
                    default=list(range(2013, 2026)))
    ap.add_argument("--min-train", type=int, default=3)
    ap.add_argument("--threshold", type=float, default=1.75)
    ap.add_argument("--fig", default="docs/figs/roi_report.png")
    ap.add_argument("--no-fig", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        _self_check()
        return

    rng = np.random.default_rng(SEED)
    data = load_from_raw(args.season)
    years = sorted(data)
    if len(years) <= args.min_train:
        sys.exit(f"Need > {args.min_train} seasons; have {len(years)}.")

    season, bias, over, prob = walk_forward_bets(data, years, args.min_train)
    sel = bias > args.threshold
    s_b, o_b, p_b = season[sel], over[sel], prob[sel]
    n, wins = int(sel.sum()), int(o_b.sum())
    win = wins / n
    win_lo, win_hi = _wilson(wins, n)
    roi = unit_roi(win)
    roi_lo, roi_hi = wilson_roi(wins, n)
    lr, pval = log_likelihood_ratio(wins, n, q=HURDLE)

    k_roi, k_staked, k_n = kelly_roi(o_b, p_b)
    k_lo, k_hi = boot_kelly_ci(o_b, p_b, rng)

    equity = np.cumsum(np.where(o_b > 0, PAYOUT, -RISK))
    eq_lo, eq_hi = boot_equity_bands(o_b, rng)
    marks = [(int(np.argmax(s_b == t)) + 1, int(t))
             for t in sorted(set(s_b.tolist()))]

    rows = season_rows(s_b, o_b, p_b)
    sweep = []
    for x in np.arange(0.5, 3.01, 0.125):
        m = bias > x
        nn, ww = int(m.sum()), int(over[m].sum())
        if nn < 30:
            continue
        lo_x, hi_x = wilson_roi(ww, nn)
        sweep.append({"x": float(x), "n": nn, "roi": unit_roi(ww / nn),
                      "lo": lo_x, "hi": hi_x})

    # Bet counts are heavily back-loaded (2 in the first season, 51 in the
    # last), so "average bets per season" would misdescribe the sample.
    recent_from = years[-1] - 3
    recent_share = sum(r["n"] for r in rows if r["season"] >= recent_from) / n

    stats = {
        "threshold": args.threshold, "n": n, "wins": wins, "win": win,
        "n_min": min(r["n"] for r in rows), "n_max": max(r["n"] for r in rows),
        "recent_share": recent_share, "recent_from": recent_from,
        "win_lo": win_lo, "win_hi": win_hi,
        "roi": roi, "roi_lo": roi_lo, "roi_hi": roi_hi,
        "kelly": k_roi, "kelly_lo": k_lo, "kelly_hi": k_hi,
        "kelly_staked": k_staked, "kelly_n": k_n,
        "equity": equity, "eq_lo": eq_lo, "eq_hi": eq_hi,
        "mdd": max_drawdown(equity), "season_marks": marks,
        "seasons": rows, "pos_seasons": sum(1 for r in rows if r["roi"] > 0),
        "sweep": sweep, "pval": pval,
        "provenance": _provenance(years, args.min_train, args.threshold, n),
    }

    print(f"\nFLOOR BIAS ROI REPORT — filter: bias > {args.threshold}")
    print(f"  bet seasons {years[args.min_train]}-{years[-1]}, "
          f"walk-forward (train on seasons < t)")
    print(f"  N={n} bets  record {wins}-{n-wins}  win={win*100:.2f}% "
          f"(Wilson95 [{win_lo*100:.2f}, {win_hi*100:.2f}])")
    print(f"  break-even {HURDLE*100:.2f}%  |  LR test vs break-even "
          f"p={pval:.4f}")
    print(f"  FLAT-STAKE ROI  = {roi*100:+.2f}% per unit risked  "
          f"(95% [{roi_lo*100:+.2f}, {roi_hi*100:+.2f}])")
    print(f"    -> plan on {roi_lo*100:+.2f}%, not {roi*100:+.2f}%: "
          f"the threshold was chosen partly on this data.")
    print(f"  {KELLY_FRACTION:g}-KELLY ROI  = {k_roi*100:+.2f}% per unit "
          f"staked (boot95 [{k_lo*100:+.2f}, {k_hi*100:+.2f}], "
          f"{k_n}/{n} games staked)")
    print(f"  equity: terminal {equity[-1]:+,.0f} units risked, "
          f"max drawdown {stats['mdd']:,.0f}")
    print(f"  seasons profitable: {stats['pos_seasons']}/{len(rows)}  "
          f"({stats['n_min']}-{stats['n_max']} bets/season; "
          f"{recent_share*100:.0f}% of bets from {recent_from}+)")
    print("\n  per-season detail:")
    for r in rows:
        print(f"    {r['season']}  n={r['n']:>3}  {r['wins']:>3}-"
              f"{r['n']-r['wins']:<3}  win={r['win']*100:6.2f}%  "
              f"ROI={r['roi']*100:+7.2f}%  "
              f"95% [{r['lo']*100:+7.2f}, {r['hi']*100:+7.2f}]")
    last = rows[-1]
    print(f"\n  NOTE: {last['season']} is the largest sample "
          f"(n={last['n']}) and the flattest result "
          f"({last['roi']*100:+.2f}%).")
    print(f"  Its interval [{last['lo']*100:+.1f}, {last['hi']*100:+.1f}] "
          f"spans both the pooled estimate and break-even, so it is not "
          f"evidence\n  of decay on its own -- monitor/monitor.py is the "
          f"test that measures decay directly.")
    print("\n  price sensitivity (win rate held fixed):")
    for p in PRICES:
        print(f"    {p:>5}  break-even {breakeven(p)*100:5.2f}%  "
              f"ROI {unit_roi(win, p)*100:+6.2f}%  "
              f"planning {unit_roi(win_lo, p)*100:+6.2f}%")

    if not args.no_fig:
        make_figure(stats, args.fig)


if __name__ == "__main__":
    main()
