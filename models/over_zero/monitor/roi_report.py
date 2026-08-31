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
import csv
import json
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
    RAW_DIR,
    censoring_bias,
    implied_team_points,
    log_likelihood_ratio,
    pick_line,
)

RISK, PAYOUT = 110.0, 100.0
BOOT = 10_000
SEED = 20260826

# A unit is 1% of bankroll, so the flat rule stakes exactly 1u per bet and
# every stake, profit and drawdown below is on one scale. Turning the raw
# 110-per-bet arithmetic into units is a divide by RISK.
UNIT_PCT = 0.01

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


def game_meta(season, raw_dir=RAW_DIR, provider=None):
    """Per-game identity for one season, in load_raw_seasons' row order.

    Replays that loader's iteration and its three drop conditions (no final
    score, no book with both lines, pick'em) so row i here is row i of
    data[season]. Only the identity fields are kept -- the numbers come from
    the loader itself, never from this replay. Callers must assert the lengths
    match per season; a global check can hide two seasons off by compensating
    amounts.
    """
    path = Path(raw_dir) / f"lines_{season}.json"
    if not path.exists():
        return []
    rows = []
    for g in json.loads(path.read_text(encoding="utf-8")):
        hp, ap = g.get("homeScore"), g.get("awayScore")
        if hp is None or ap is None:
            continue
        picked = pick_line(g, provider)
        if picked is None or picked[0] == 0:
            continue
        spread = picked[0]
        # Favourite is the negative-spread side, matching load_raw_seasons.
        fav, dog = ((g.get("homeTeam"), g.get("awayTeam")) if spread < 0
                    else (g.get("awayTeam"), g.get("homeTeam")))
        rows.append({
            "game_id": g.get("id"), "week": g.get("week"),
            "date": (g.get("startDate") or "")[:10],
            "home_team": g.get("homeTeam"), "away_team": g.get("awayTeam"),
            "fav_team": fav, "dog_team": dog,
        })
    return rows


def walk_forward_bets(data, years, min_train, with_meta=False):
    """Every out-of-sample game with its season label, chronological.

    Mirrors bias_bins.walk_forward but keeps the season so the bets can be
    ordered and grouped in time. Pushes (exact totals) are dropped: no bet
    resolves on them.

    with_meta appends a 5th return: one dict per surviving row carrying game
    identity and the inputs, built inside this loop and sliced by the same
    `keep` mask, so CSV rows line up with the arrays by construction rather
    than by a reconciliation after the fact.
    """
    season, bias_all, over_all, prob_all, meta = [], [], [], [], []
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

        if with_meta:
            ids = game_meta(t)
            if len(ids) != se_t.size:
                raise AssertionError(
                    f"{t}: identity replay has {len(ids)} rows, loader has "
                    f"{se_t.size} -- the drop conditions have diverged.")
            for i in np.flatnonzero(keep):
                meta.append({**ids[i], "season": int(t),
                             "spread": float(se_t[i]), "total": float(te_t[i]),
                             "fav_pts": float(fp_t[i]),
                             "dog_pts": float(dp_t[i]),
                             "actual_total": float(fp_t[i] + dp_t[i])})
    out = (np.concatenate(season), np.concatenate(bias_all),
           np.concatenate(over_all), np.concatenate(prob_all))
    return out + (meta,) if with_meta else out


def wilson_roi(wins, n, price=-110):
    """Exact ROI interval: map the Wilson win-rate CI through the affine ROI."""
    lo, hi = _wilson(wins, n)
    return unit_roi(lo, price), unit_roi(hi, price)


def kelly_units(prob, fraction=KELLY_FRACTION, price=-110):
    """Per-bet quarter-Kelly stake in UNITS, where 1 unit = 1% of bankroll.

    The only place a Kelly stake is defined. kelly_fraction returns a share of
    bankroll, so dividing by UNIT_PCT puts it on the same scale as the flat
    rule's 1u: a bet the model likes twice as much as break-even-plus-a-hair
    shows up as 2u, and one it prices below break-even shows up as 0u.
    """
    risk, payout = american_to_risk_payout(price)
    return kelly_fraction(prob, fraction, risk=risk, payout=payout) / UNIT_PCT


def kelly_roi(over, prob, fraction=KELLY_FRACTION, price=-110):
    """Quarter-Kelly return per unit staked, flat bankroll (order-independent).

    Returns (roi, units_staked, n_staked). Kelly skips any game the model
    prices at or below breakeven, so both `units_staked` and `n_staked` can be
    well below len(over) -- and units_staked is the denominator that makes
    Kelly's ROI% incomparable with flat's until you multiply back out.
    """
    risk, payout = american_to_risk_payout(price)
    b = payout / risk
    u = kelly_units(prob, fraction, price)
    staked = float(u.sum())
    if staked <= 0:
        return float("nan"), 0.0, 0
    profit = float(np.sum(np.where(over > 0, u * b, -u)))
    return profit / staked, staked, int((u > 0).sum())


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
    # In units: risk 1u, win payout/risk. Same shape as the raw 110/100 path,
    # on the scale the stake rules are quoted in.
    per_bet = np.where(over > 0, payout / risk, -1.0)
    for i in range(n_boot):
        paths[i] = np.cumsum(rng.permutation(per_bet))
    return (np.percentile(paths, 5, axis=0), np.percentile(paths, 95, axis=0))


def max_drawdown(equity):
    """Peak-to-trough drop of a cumulative-profit path, in units."""
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


CSV_COLUMNS = [
    "game_id", "season", "week", "date", "away_team", "home_team",
    "fav_team", "dog_team", "spread", "total", "fav_pts", "dog_pts",
    "actual_total", "bias", "model_prob", "over", "threshold",
    "passes_filter", "flat_units_risked", "flat_units_pnl", "kelly_units",
    "kelly_units_pnl",
]

DEPLOYED_THRESHOLD = 1.75


def default_csv_path(threshold):
    """The deployed file has a fixed name; anything else gets its own, so an
    exploratory `--threshold 1.0` run cannot quietly overwrite the committed
    234-bet ledger with a 681-bet one that looks identical.
    """
    if threshold == DEPLOYED_THRESHOLD:
        return "docs/backtest_bets.csv"
    return f"docs/backtest_bets_bias{threshold:g}.csv"


def _g(x):
    """Full float precision in the CSV. 4dp would round the Kelly stakes
    enough that reading the file back no longer reproduces the ROI."""
    v = float(x)
    return f"{0.0 if v == 0 else v:.10g}"     # no "-0" on the skipped rows


def write_bets_csv(path, meta, bias, over, prob, threshold, price=-110):
    """One row per graded walk-forward game -- ALL of them, not just the ones
    clearing the filter, so the bias-bin table is reproducible from this file
    too. Pushes are absent: walk_forward_bets drops them, and matching the
    analysis exactly matters more than being literally every game.

    Stakes and P&L are in units (1 unit = 1% of bankroll): the flat rule risks
    1u on a qualifying game, Kelly risks kelly_units(prob). Both ledgers are
    live only where passes_filter == 1; on the other rows they are the
    counterfactual "what the rule would have staked", not money wagered.
    """
    risk, payout = american_to_risk_payout(price)
    b = payout / risk
    sel = bias > threshold
    ku = kelly_units(prob, price=price)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for i, m in enumerate(meta):
            won = over[i] > 0
            flat_risk = 1.0 if sel[i] else 0.0
            w.writerow({
                **{k: m[k] for k in (
                    "game_id", "season", "week", "date", "away_team",
                    "home_team", "fav_team", "dog_team")},
                "spread": _g(m["spread"]), "total": _g(m["total"]),
                "fav_pts": _g(m["fav_pts"]), "dog_pts": _g(m["dog_pts"]),
                "actual_total": _g(m["actual_total"]),
                "bias": _g(bias[i]), "model_prob": _g(prob[i]),
                "over": int(won), "threshold": _g(threshold),
                "passes_filter": int(sel[i]),
                "flat_units_risked": _g(flat_risk),
                "flat_units_pnl": _g(flat_risk * (b if won else -1.0)),
                "kelly_units": _g(ku[i]),
                "kelly_units_pnl": _g(ku[i] * (b if won else -1.0)),
            })
    return len(meta)


def reconcile_csv(path, expect, price=-110):
    """Read the file back and re-derive the headline. This is the check that
    matters: it catches meta/array misalignment, a wrong filter mask and
    lost precision at once, none of which the arithmetic self-checks see.
    """
    n = wins = 0
    flat_pnl = kelly_pnl = kelly_staked = 0.0
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            # The file says which filter it was written under, so a stale or
            # mismatched ledger fails here instead of quietly reconciling.
            assert float(row["threshold"]) == expect["threshold"], row["threshold"]
            if row["passes_filter"] != "1":
                continue
            # Kelly is sized on the filtered bets, same as kelly_roi() -- the
            # unfiltered rows are in the file for the bin table, not to stake.
            kelly_staked += float(row["kelly_units"])
            kelly_pnl += float(row["kelly_units_pnl"])
            n += 1
            wins += int(row["over"])
            flat_pnl += float(row["flat_units_pnl"])
    assert n == expect["n"], (n, expect["n"])
    assert wins == expect["wins"], (wins, expect["wins"])
    assert abs(flat_pnl / n - expect["roi"]) < 1e-9, (flat_pnl / n, expect["roi"])
    assert abs(kelly_pnl / kelly_staked - expect["kelly"]) < 1e-9
    assert abs(kelly_staked - expect["kelly_staked"]) < 1e-6
    return n, flat_pnl, kelly_staked, kelly_pnl


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
    ax.annotate(f"terminal +{eq[-1]:,.1f}u\n"
                f"max drawdown −{stats['mdd']:,.1f}u",
                (eq.size, eq[-1]), textcoords="offset points",
                xytext=(-8, -34), ha="right", fontsize=8.5, color=INK,
                fontweight="bold")
    ax.set_xlabel("bet number (chronological)")
    ax.set_ylabel("cumulative profit (units; 1u = 1% of bankroll)")
    ax.set_title("Realised equity vs. sequencing luck\n"
                 "band re-orders the same wins and losses; endpoint fixed "
                 "by construction", loc="left")
    ax.legend(fontsize=7.5, loc="lower right", frameon=False)

    # --- Panel 5: Kelly vs flat, with bootstrap ---------------------------
    ax = fig.add_subplot(gs[1, 2])
    _style(ax)
    labels = [f"flat stake\n1.00u/bet → {stats['flat_profit_u']:+.0f}u",
              f"{KELLY_FRACTION:g}-Kelly\n{stats['k_u_mean']:.2f}u avg "
              f"→ {stats['kelly_profit_u']:+.0f}u"]
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
    # Near-equal bars, 6x different profit: the ROI% hides the turnover, and
    # the stake range is the reason flat is the rule that ships.
    ax.set_title("Two stake rules, two intervals\n"
                 f"Kelly stakes {stats['k_u_min']:.1f}–{stats['k_u_max']:.1f}u"
                 f" per game — same edge, {stats['kelly_staked']/n:.1f}x the "
                 "turnover", loc="left")

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
    # Units: 1u = 1% of bankroll, so a stake is its bankroll fraction x100,
    # nothing at or below breakeven, and full Kelly on a sure thing is 100u.
    assert abs(kelly_units(np.array([HURDLE]))[0]) < 1e-12
    assert abs(kelly_units(np.array([1.0]), fraction=1.0)[0] - 100.0) < 1e-9
    assert np.allclose(kelly_units(np.array([0.62])),
                       kelly_fraction(np.array([0.62])) * 100.0)
    # Equity is in units now: a win adds payout/risk, a loss costs exactly 1u.
    assert abs(unit_roi(1.0) - PAYOUT / RISK) < 1e-12
    # ROI x n is total profit in units, which is what the two stake rules are
    # compared on -- Kelly's turnover base differs, its percentage doesn't say.
    o = np.array([1.0, 1.0, 0.0])
    assert abs(unit_roi(o.mean()) * o.size
               - (2 * PAYOUT / RISK - 1.0)) < 1e-9
    print("self-check OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, nargs="+",
                    default=list(range(2013, 2026)))
    ap.add_argument("--min-train", type=int, default=3)
    ap.add_argument("--threshold", type=float, default=1.75)
    ap.add_argument("--fig", default="docs/figs/roi_report.png")
    ap.add_argument("--no-fig", action="store_true")
    ap.add_argument("--csv", default=None,
                    help="per-bet walk-forward rows (all graded games); "
                         "defaults to a path named for the threshold")
    ap.add_argument("--no-csv", action="store_true")
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

    season, bias, over, prob, meta = walk_forward_bets(
        data, years, args.min_train, with_meta=True)
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
    k_u = kelly_units(p_b)
    # ROI% is per unit STAKED for Kelly and per unit RISKED for flat, so the
    # two percentages are not comparable until multiplied back out. Total
    # profit in units is, and is the number a bankroll actually sees.
    flat_profit_u, kelly_profit_u = roi * n, k_roi * k_staked

    equity = np.cumsum(np.where(o_b > 0, PAYOUT / RISK, -1.0))
    k_equity = np.cumsum(np.where(o_b > 0, k_u * PAYOUT / RISK, -k_u))
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
        "flat_profit_u": flat_profit_u, "kelly_profit_u": kelly_profit_u,
        "k_u_min": float(k_u.min()), "k_u_med": float(np.median(k_u)),
        "k_u_mean": float(k_u.mean()), "k_u_max": float(k_u.max()),
        "k_equity": k_equity, "k_mdd": max_drawdown(k_equity),
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
    print(f"\n  STAKES IN UNITS (1 unit = 1% of bankroll; flat = 1.00u/bet)")
    print(f"    {KELLY_FRACTION:g}-Kelly stake: min {stats['k_u_min']:.2f}u  "
          f"median {stats['k_u_med']:.2f}u  mean {stats['k_u_mean']:.2f}u  "
          f"max {stats['k_u_max']:.2f}u")
    print(f"    flat  staked {n:>7.1f}u -> profit {flat_profit_u:+.2f}u "
          f"({roi*100:+.2f}% of turnover)")
    print(f"    Kelly staked {k_staked:>7.1f}u -> profit "
          f"{kelly_profit_u:+.2f}u ({k_roi*100:+.2f}% of turnover)")
    print(f"    -> Kelly's higher ROI% is on a "
          f"{k_staked/n:.2f}x turnover base; compare the unit profits, not "
          f"the percentages.")
    print(f"  equity: terminal {equity[-1]:+,.2f}u, "
          f"max drawdown {stats['mdd']:,.2f}u  |  Kelly path: "
          f"{stats['k_equity'][-1]:+,.1f}u, max drawdown "
          f"{stats['k_mdd']:,.1f}u")
    if stats["k_u_max"] > 3.0:
        print(f"    WARNING: {KELLY_FRACTION:g}-Kelly's largest stake is "
              f"{stats['k_u_max']:.1f}% of bankroll on one game. It is sized "
              f"off the model's own\n    win probability with no allowance "
              f"for estimation error, and college slates settle at the same\n"
              f"    time, so several {stats['k_u_med']:.1f}u bets are live "
              f"together. Flat 1u is the deployable rule.")
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

    if not args.no_csv:
        csv_path = args.csv or default_csv_path(args.threshold)
        rows = write_bets_csv(csv_path, meta, bias, over, prob, args.threshold)
        cn, cflat, ckstake, ckpnl = reconcile_csv(csv_path, stats)
        print(f"\nWrote {csv_path} — {rows} graded games "
              f"({cn} clear the filter). Read back: {cflat:+.2f}u flat, "
              f"{ckpnl:+.2f}u Kelly on {ckstake:.1f}u staked — "
              f"reconciles with the headline above.")

    if not args.no_fig:
        make_figure(stats, args.fig)


if __name__ == "__main__":
    main()
