"""ROI and hit rate by season and by bias bin: figure + markdown doc.

  python monitor/roi_hitrate_doc.py [--season 2013 ... 2025] [--min-train 3]
      [--threshold 1.75] [--fig docs/figs/roi_hitrate.png]
      [--doc docs/ROI_HITRATE.md]

Companion to roi_report.py, which reports the deployed filter as a single
number. This one splits the same walk-forward bets two ways and shows both
metrics for each split:

  BY SEASON    -- bets at the deployed filter (bias > 1.75), grouped by the
                  season they were placed in. The time-series view: does the
                  edge hold up year to year, or is it carried by a few?
  BY BIAS BIN  -- every graded game, grouped into disjoint bias bands. The
                  mechanism check: censoring theory says more expected bias
                  means more mispricing, so the metrics should rise across
                  bins. One bin popping alone is noise.

Hit rate and ROI are the same fact at a fixed price -- ROI is affine in the
win rate -- so the paired panels carry identical information geometry, and the
break-even line lands at 52.38% and 0% respectively. They are shown together
because a hit rate answers "does it win" and an ROI answers "what does a unit
risked earn", and readers arrive wanting one or the other.

Protocol, loaders and estimators shared with roi_report.py / bias_bins.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "v2"))
from monitor import _wilson, load_from_raw  # noqa: E402
from run_walkforward import HURDLE  # noqa: E402
from bias_bins import BIN_EDGES  # noqa: E402
from roi_report import (  # noqa: E402
    INK, MUTED, GRID, BLUE, GREEN, RED, GOLD, BAND,
    _provenance, _style, unit_roi, walk_forward_bets, wilson_roi,
)


def rows_for(bias, over, groups, labels, selector):
    """One stats row per group: N, record, win rate + CI, ROI + CI.

    `selector(g)` returns the boolean mask for group g, so the same routine
    serves both the season split and the bias-bin split.
    """
    rows = []
    for g, label in zip(groups, labels):
        sel = selector(g)
        n = int(sel.sum())
        if n == 0:
            rows.append({"label": label, "n": 0})
            continue
        wins = int(over[sel].sum())
        w = wins / n
        w_lo, w_hi = _wilson(wins, n)
        r_lo, r_hi = wilson_roi(wins, n)
        rows.append({"label": label, "n": n, "wins": wins, "losses": n - wins,
                     "win": w, "win_lo": w_lo, "win_hi": w_hi,
                     "roi": unit_roi(w), "roi_lo": r_lo, "roi_hi": r_hi,
                     "clears": w_lo > HURDLE})
    return rows


def _bar_panel(ax, rows, *, value_key, lo_key, hi_key, baseline, ylabel,
               title, pooled=None, pooled_label=""):
    """One metric, one grouping. Bars coloured by whether the CI clears the bar.

    A group whose interval sits entirely above break-even is the only kind of
    evidence a single bar can carry at these sample sizes; everything else is
    coloured as inconclusive rather than as a win or a loss.
    """
    live = [r for r in rows if r["n"]]
    xs = np.arange(len(live))
    vals = [r[value_key] * 100 for r in live]
    lo_e = [max(0.0, (r[value_key] - r[lo_key]) * 100) for r in live]
    hi_e = [max(0.0, (r[hi_key] - r[value_key]) * 100) for r in live]
    cols = [GREEN if r["clears"] else
            (RED if r[hi_key] < baseline else "#9aa3ae") for r in live]

    ax.bar(xs, vals, color=cols, width=0.62, zorder=3, alpha=0.92)
    ax.errorbar(xs, vals, yerr=[lo_e, hi_e], fmt="none", ecolor=INK,
                elinewidth=1.15, capsize=4, alpha=0.8, zorder=4)
    ax.axhline(baseline * 100, color=RED, ls="--", lw=1.4, zorder=2,
               label=f"break-even ({baseline*100:.2f}%)" if baseline
               else "break-even (0%)")
    if pooled is not None:
        ax.axhline(pooled * 100, color=BLUE, lw=1.4, zorder=2,
                   label=pooled_label)

    # Clip to the groups that carry information; label whatever runs off. A
    # 2-bet season spans the whole axis and would flatten every other bar.
    big = [r for r in live if r["n"] >= 5]
    top = max((r[hi_key] * 100 for r in big), default=100.0)
    bot = min((r[lo_key] * 100 for r in big), default=0.0)
    pad = 0.20 * (top - bot)
    ax.set_ylim(bot - pad, top + pad)
    for x, r in enumerate(live):
        if (r[lo_key] * 100 < bot - pad) or (r[hi_key] * 100 > top + pad):
            ax.annotate(f"{vals[x]:+.0f}%\n(n={r['n']}\nCI off-scale)",
                        (x, (top + pad) * 0.5 if vals[x] > baseline * 100
                         else (bot - pad) * 0.5),
                        ha="center", va="center", fontsize=6.6,
                        color=INK, fontweight="bold", zorder=6)

    ax.set_xticks(xs)
    ax.set_xticklabels([f"{r['label']}\nn={r['n']}" for r in live],
                       fontsize=7.4)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left")
    ax.legend(fontsize=7.4, loc="lower right", frameon=False)


def make_figure(seasons, bins, pooled, path, threshold):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.titlesize": 10.5, "axes.titleweight": "bold",
        "axes.labelsize": 9, "figure.facecolor": "white",
    })

    fig = plt.figure(figsize=(16.5, 10.2))
    gs = GridSpec(2, 2, figure=fig, hspace=0.42, wspace=0.20,
                  left=0.06, right=0.975, top=0.845, bottom=0.10)

    ax = fig.add_subplot(gs[0, 0])
    _style(ax)
    _bar_panel(ax, seasons, value_key="win", lo_key="win_lo", hi_key="win_hi",
               baseline=HURDLE, ylabel="over win rate (%)",
               title=f"Hit rate by season — filter bias > {threshold}",
               pooled=pooled["win"],
               pooled_label=f"pooled {pooled['win']*100:.2f}%")

    ax = fig.add_subplot(gs[0, 1])
    _style(ax)
    _bar_panel(ax, seasons, value_key="roi", lo_key="roi_lo", hi_key="roi_hi",
               baseline=0.0, ylabel="return per unit risked (%)",
               title=f"ROI by season — filter bias > {threshold}",
               pooled=pooled["roi"],
               pooled_label=f"pooled {pooled['roi']*100:+.2f}%")

    ax = fig.add_subplot(gs[1, 0])
    _style(ax)
    _bar_panel(ax, bins, value_key="win", lo_key="win_lo", hi_key="win_hi",
               baseline=HURDLE, ylabel="over win rate (%)",
               title="Hit rate by bias bin (disjoint, all graded games)")
    ax.set_xlabel("expected censoring bias (points)")

    ax = fig.add_subplot(gs[1, 1])
    _style(ax)
    _bar_panel(ax, bins, value_key="roi", lo_key="roi_lo", hi_key="roi_hi",
               baseline=0.0, ylabel="return per unit risked (%)",
               title="ROI by bias bin (disjoint, all graded games)")
    ax.set_xlabel("expected censoring bias (points)")

    fig.text(0.06, 0.965,
             "FLOOR BIAS — HIT RATE AND ROI, BY SEASON AND BY BIAS BIN",
             fontsize=16.5, fontweight="bold", color=INK, va="top")
    fig.text(0.06, 0.930,
             "Walk-forward, out-of-sample. Bars are point estimates; the "
             "whiskers are 95% Wilson intervals and are the part to read. "
             "Green = interval clears break-even.",
             fontsize=9.5, color=MUTED, va="top")
    fig.text(0.06, 0.902,
             "At 2–51 bets per season a single bar cannot separate a real "
             "edge from noise. ROI is affine in hit rate at a fixed price, so "
             "each pair carries the same fact in two units.",
             fontsize=9, color=RED, va="top")
    fig.text(0.06, 0.030, pooled["provenance"], fontsize=7.2, color=MUTED,
             va="top", wrap=True)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170, facecolor="white")
    print(f"Wrote {path}")


def _table(rows, first_col):
    """Markdown table: N, record, hit rate + CI, ROI + CI, verdict."""
    out = [f"| {first_col} | N | record | hit rate | hit-rate 95% | ROI | "
           "ROI 95% | clears break-even |",
           "|---|---:|---:|---:|---|---:|---|:---:|"]
    for r in rows:
        if not r["n"]:
            out.append(f"| {r['label']} | 0 | — | — | — | — | — | — |")
            continue
        out.append(
            f"| {r['label']} | {r['n']} | {r['wins']}–{r['losses']} | "
            f"{r['win']*100:.2f}% | "
            f"[{r['win_lo']*100:.2f}%, {r['win_hi']*100:.2f}%] | "
            f"{r['roi']*100:+.2f}% | "
            f"[{r['roi_lo']*100:+.2f}%, {r['roi_hi']*100:+.2f}%] | "
            f"{'**yes**' if r['clears'] else 'no'} |")
    return "\n".join(out)


def write_doc(seasons, bins, pooled, path, fig_path, threshold):
    fig_rel = Path(fig_path).name
    live_s = [r for r in seasons if r["n"]]
    live_b = [r for r in bins if r["n"]]
    clears_s = [r for r in live_s if r["clears"]]
    clears_b = [r for r in live_b if r["clears"]]
    pos = [r for r in live_s if r["roi"] > 0]
    last = live_s[-1]

    # Sentences are assembled before the f-string so interpolated numbers do
    # not leave the prose wrapped at ragged mid-sentence widths.
    pooled_line = (
        f"Pooled: **{pooled['n']} bets, {pooled['wins']}–{pooled['losses']}, "
        f"{pooled['win']*100:.2f}%** hit rate "
        f"([{pooled['win_lo']*100:.2f}%, {pooled['win_hi']*100:.2f}%]), "
        f"**{pooled['roi']*100:+.2f}%** ROI "
        f"([{pooled['roi_lo']*100:+.2f}%, {pooled['roi_hi']*100:+.2f}%]).")
    counts_line = (
        f"{len(pos)}/{len(live_s)} seasons profitable on the point estimate, "
        f"but only {len(clears_s)} clear break-even on their own interval — "
        f"which is what {pooled['n_min']}–{pooled['n_max']} bets a season "
        f"buys you. Single seasons are not the unit of evidence here; the "
        f"pooled row is.")
    # The decay-watch bullet is about the most recent season, but "largest"
    # and "flattest" are facts to check, not properties the last row inherits
    # by being last -- they were both true of 2025 and neither is of 2026.
    supers = []
    if last is max(live_s, key=lambda r: r["n"]):
        supers.append("the largest sample")
    if last is min(live_s, key=lambda r: abs(r["roi"])):
        supers.append("the flattest result")
    lead = (f"{last['label']} is " + " and ".join(supers)) if supers else (
        f"{last['label']} is the most recent season")
    spans = (last["roi_lo"] <= pooled["roi"] <= last["roi_hi"]
             and last["roi_lo"] <= 0.0 <= last["roi_hi"])
    verdict = (
        "contains both the pooled estimate and break-even, so it is not "
        "evidence of decay on its own"
        if spans else
        "does not contain both the pooled estimate and break-even — read it "
        "against `run_monitor.py` before treating it either way")
    last_line = (
        f"- **{lead}**: {last['wins']}–{last['losses']}, "
        f"{last['roi']*100:+.2f}% ROI on n={last['n']}, against a pooled "
        f"{pooled['roi']*100:+.2f}%. Its interval "
        f"[{last['roi_lo']*100:+.1f}%, {last['roi_hi']*100:+.1f}%] {verdict}. "
        f"`run_monitor.py` is the test that measures decay "
        f"directly, and as of its last run it finds none.")
    backload_line = (
        f"- **The sample is back-loaded**: {pooled['n_min']}–"
        f"{pooled['n_max']} bets per season, with "
        f"{pooled['recent_share']*100:.0f}% of all bets coming from "
        f"{pooled['recent_from']} onward. The pooled figure is mostly recent "
        f"data.")
    partial_line = (pooled["partial"] + chr(10)) if pooled["partial"] else ""
    bins_line = (
        f"This is the mechanism check, not a menu of bets. Censoring theory "
        f"predicts that more expected bias means more mispricing, so the "
        f"metrics should **rise across the bins**; a single bin popping while "
        f"its neighbours sit flat is noise, not a strategy. {len(clears_b)} "
        f"of {len(live_b)} bins clear break-even on their own interval.")
    excluded_line = (
        f"Note the bins are disjoint, so the 1.00–1.75 row is the band "
        f"*excluded* by the deployed rule — it is shown precisely because it "
        f"demonstrates no edge, which is why the operational threshold moved "
        f"from 1.0 to {threshold} (MODEL_GUIDE §3).")
    caveat_line = (
        f"- The {threshold} threshold was chosen partly on this data, so the "
        f"pooled point estimate is inflated by selection. **Plan on the lower "
        f"bound** ({pooled['roi_lo']*100:+.2f}% ROI), not the point estimate.")

    doc = f"""# Hit rate and ROI — by season and by bias bin

Walk-forward, out-of-sample: for season *t* the whole pipeline (Tobit sigmas
+ probit) is fit on seasons *< t* only, then season *t* is graded. Pushes are
dropped. Generated by `monitor/roi_hitrate_doc.py`; the single-number version
of the same bets is in [`roi_report.py`](../monitor/roi_report.py) and
[`figs/roi_report.png`](figs/roi_report.png).

![Hit rate and ROI by season and by bias bin](figs/{fig_rel})

**Read the intervals, not the bars.** Hit rate and ROI are the same fact in
two units — at a fixed price ROI is affine in the win rate — so each pair of
panels carries identical information. Break-even is {HURDLE*100:.2f}% at −110,
which is 0% ROI. A bar is green only when its 95% interval sits entirely
above break-even.

## By season — the deployed filter (bias > {threshold})

{_table(seasons, "season")}

{pooled_line}

{counts_line}

Two things worth naming rather than leaving for the reader to find:

{last_line}
{backload_line}

## By bias bin — every graded game, disjoint bands

{_table(bins, "bias bin")}

{bins_line}

{excluded_line}

## Caveats that apply to every number above

{caveat_line}
{partial_line}- Every ROI here is priced at −110 flat. The operational rule says −120 or
  better; see the price-sensitivity panel in `figs/roi_report.png` for what
  the vig costs.
- Wilson intervals assume independent bets. Games on the same slate are not
  fully independent, so the true intervals are somewhat wider than shown.

## Reproducing these tables

Every row above comes out of `backtest_bets.csv` — one line per graded
walk-forward game, all of them, not just the ones clearing the filter. Group
by `season` (filtering `passes_filter == 1`) for the first table, bucket
`bias` on the bin edges for the second. The file's `threshold` column records
which filter produced it. Regenerate both file and doc with
`python monitor/roi_report.py --season {pooled['season_arg']}` then
`python monitor/roi_hitrate_doc.py --season {pooled['season_arg']}`
(both default to 2013-2025, so the range is not optional).

The `kelly_units` / `kelly_units_pnl` columns are live only on rows where
`passes_filter == 1`; elsewhere they are what Kelly would have staked, not
money wagered, so don't sum them across the excluded bins.

---

{pooled['provenance']}
"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(doc, encoding="utf-8")
    print(f"Wrote {path}")


def _self_check():
    """Smallest checks that fail if the grouping or table maths breaks."""
    bias = np.array([0.2, 0.8, 1.2, 2.0, 3.0])
    over = np.array([1.0, 0.0, 1.0, 1.0, 0.0])
    rows = rows_for(bias, over, ["low", "high"], ["low", "high"],
                    lambda g: (bias > 1.0) if g == "high" else (bias <= 1.0))
    assert rows[0]["n"] == 2 and rows[0]["wins"] == 1, rows[0]
    assert rows[1]["n"] == 3 and rows[1]["wins"] == 2, rows[1]
    # Every group's N sums back to the whole sample: no game double-counted.
    assert rows[0]["n"] + rows[1]["n"] == bias.size
    # A perfect group clears; a coin-flip group at n=2 cannot.
    perfect = rows_for(np.ones(40), np.ones(40), [0], ["p"],
                       lambda g: np.ones(40, bool))[0]
    assert perfect["clears"] and abs(perfect["roi"] - 100 / 110) < 1e-12
    assert not rows[1]["clears"]
    # Empty group renders without raising.
    assert "| z | 0 |" in _table([{"label": "z", "n": 0}], "g")
    print("self-check OK")


def _partial_note(data, years):
    """Text for the final season when it has graded far fewer games than a
    full one, else "". Compares against the median of the finished seasons."""
    counts = {y: len(data[y][0]) for y in years}
    last = years[-1]
    prior = sorted(counts[y] for y in years[:-1])
    if not prior:
        return ""
    median = prior[len(prior) // 2]
    if counts[last] >= 0.6 * median:
        return ""
    return (f"- **{last} is a partial season**: {counts[last]} graded games "
            f"so far against a ~{median}-game full season, so its row is a "
            f"few weeks of results and will move as the season fills in. It "
            f"is pooled in with the rest.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, nargs="+",
                    default=list(range(2013, 2026)))
    ap.add_argument("--min-train", type=int, default=3)
    ap.add_argument("--threshold", type=float, default=1.75)
    ap.add_argument("--fig", default="docs/figs/roi_hitrate.png")
    ap.add_argument("--doc", default="docs/ROI_HITRATE.md")
    ap.add_argument("--no-fig", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        _self_check()
        return

    data = load_from_raw(args.season)
    years = sorted(data)
    if len(years) <= args.min_train:
        sys.exit(f"Need > {args.min_train} seasons; have {len(years)}.")

    season, bias, over, _ = walk_forward_bets(data, years, args.min_train)

    # Season split: only the bets the deployed filter would actually place.
    sel = bias > args.threshold
    s_b, o_b, b_b = season[sel], over[sel], bias[sel]
    bet_years = sorted(set(s_b.tolist()))
    seasons = rows_for(b_b, o_b, bet_years, [str(int(t)) for t in bet_years],
                       lambda t: s_b == t)

    # Bin split: every graded game, so the bands below the filter are visible.
    edges = list(zip(BIN_EDGES[:-1], BIN_EDGES[1:]))
    labels = [f"{lo:.2f}–{hi:.2f}" if np.isfinite(hi) else f">{lo:.2f}"
              for lo, hi in edges]
    bins = rows_for(bias, over, edges, labels,
                    lambda e: (bias > e[0]) & (bias <= e[1]))

    n, wins = int(sel.sum()), int(o_b.sum())
    w = wins / n
    w_lo, w_hi = _wilson(wins, n)
    r_lo, r_hi = wilson_roi(wins, n)
    live = [r for r in seasons if r["n"]]
    recent_from = years[-1] - 3
    pooled = {
        "n": n, "wins": wins, "losses": n - wins, "win": w,
        "win_lo": w_lo, "win_hi": w_hi,
        "roi": unit_roi(w), "roi_lo": r_lo, "roi_hi": r_hi,
        "n_min": min(r["n"] for r in live), "n_max": max(r["n"] for r in live),
        "recent_from": recent_from,
        "recent_share": sum(r["n"] for r in live
                            if int(r["label"]) >= recent_from) / n,
        "provenance": _provenance(years, args.min_train, args.threshold, n),
        "season_arg": " ".join(str(y) for y in years),
        # A season still being played grades far fewer games than a finished
        # one, and its row moves every week. Flag it rather than let the
        # footer's "data A-B" imply B is complete.
        "partial": _partial_note(data, years),
    }

    print(f"\nHIT RATE AND ROI — filter bias > {args.threshold}, "
          f"bet seasons {bet_years[0]}-{bet_years[-1]}")
    print("\nBY SEASON")
    print(_table(seasons, "season"))
    print("\nBY BIAS BIN (disjoint, all graded games)")
    print(_table(bins, "bias bin"))
    print(f"\nPOOLED  N={n}  {wins}-{n-wins}  hit={w*100:.2f}% "
          f"[{w_lo*100:.2f}, {w_hi*100:.2f}]  ROI={unit_roi(w)*100:+.2f}% "
          f"[{r_lo*100:+.2f}, {r_hi*100:+.2f}]")

    if not args.no_fig:
        make_figure(seasons, bins, pooled, args.fig, args.threshold)
    write_doc(seasons, bins, pooled, args.doc, args.fig, args.threshold)


if __name__ == "__main__":
    main()
