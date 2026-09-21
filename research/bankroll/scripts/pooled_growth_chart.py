"""Bankroll growth by week under the pooled Greenline prior only.

    python research/bankroll/scripts/pooled_growth_chart.py
    python research/bankroll/scripts/pooled_growth_chart.py --paths 100000 --out research/bankroll/docs
    python research/bankroll/scripts/pooled_growth_chart.py --self-check

The unit rule is to bracket both priors. This chart deliberately does not: it was
asked for as "the pooled edge, charted", so it conditions on the 146-113 record
(posterior mean 56.4%) and shows three configs side by side. The n58 reading is
in mc-combined-totals-2026-09-17.md and bankroll-config-sweep-2026-09-21.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mc_combined_totals import (  # noqa: E402
    PCTS, Config, simulate,
    BLUE, GREEN, GOLD, INK, MUTED, _style,
)

# (label, gl_unit, colour); volume is the simulator default, 6-12 unders a week
CONFIGS = (
    ("0.5% unit, 6-12 unders/wk", 0.005, BLUE),
    ("1.0% unit, 6-12 unders/wk", 0.01, GREEN),
    ("1.2% unit (quarter Kelly), 6-12 unders/wk", 0.012, GOLD),
)
STEM = "pooled-bankroll-growth-2026-09-21"


def run(paths: int, seed: int, bankroll: float, resize: bool = True, seasons: int = 1,
        only_unit: float | None = None) -> list[dict]:
    configs = CONFIGS if only_unit is None else tuple(
        c for c in CONFIGS if abs(c[1] - only_unit) < 1e-9)
    if not configs:
        raise SystemExit(f"--only-unit {only_unit} matches none of "
                         f"{[c[1] for c in CONFIGS]}")
    out = []
    for label, unit, colour in configs:
        res = simulate(Config(bankroll=bankroll, paths=paths, gl_unit=unit,
                              seed=seed, resize_weekly=resize, seasons=seasons))
        out.append(dict(label=label, colour=colour, fan=res["fan"], final=res["final"],
                        p_bust=res["p_bust"], unit=unit, resize=resize))
    return out


def figure(runs: list[dict], bankroll: float, path: Path, resized: list[dict] | None = None) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n_weeks = runs[0]["fan"].shape[0] - 1
    weeks = np.arange(n_weeks + 1)  # 0 = now (after week 3 of 2026); 12 = end of 2026
    rows = [runs] + ([resized] if resized else [])
    fig, axes = plt.subplots(len(rows), len(runs), figsize=(max(7.5, 5.0 * len(runs)), 5.2 * len(rows)),
                             sharey=True, squeeze=False)
    lo, hi = PCTS.index(5), PCTS.index(95)
    q1, q3, med = PCTS.index(25), PCTS.index(75), PCTS.index(50)
    for row_axes, row_runs in zip(axes, rows):
        row_axes[0].set_ylabel("bankroll, $")
        for ax, r in zip(row_axes, row_runs):
            _panel(ax, r, weeks, bankroll, lo, hi, q1, q3, med)
            ax.set_title(r["label"] + ("\nunits re-sized weekly" if r["resize"]
                                       else "\nflat units off the start"), fontsize=10.5)
    axes[0, 0].legend(fontsize=8, frameon=False, loc="upper left")
    narrow = len(runs) == 1  # one panel: the wide-figure title overflows
    fig.suptitle(f"Bankroll by week, planning prior (kappa 0.5: 89.5–70.0, mean 56.1%), "
                 f"${bankroll:,.0f} start", fontsize=11 if narrow else 13,
                 fontweight="bold", color=INK, wrap=narrow)
    sub = "Win rate drawn per path from the half-pooled posterior. n58 and pooled readings are in the sweep."
    if resized:
        sub += " Top row: units re-sized off the bankroll each week. Bottom row: flat stakes off the starting bankroll."
    fig.text(0.5, 0.905 if not resized else 0.95, sub, fontsize=8 if narrow else 9,
             color=MUTED, ha="center", wrap=narrow)
    fig.tight_layout(rect=(0, 0, 1, 0.9 if not resized else 0.94))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170, facecolor="white")
    print(f"wrote {path}")


def _panel(ax, r, weeks, bankroll, lo, hi, q1, q3, med):
    f = r["fan"]
    ax.fill_between(weeks, f[:, lo], f[:, hi], color=r["colour"], alpha=0.12, lw=0, label="5th–95th")
    ax.fill_between(weeks, f[:, q1], f[:, q3], color=r["colour"], alpha=0.28, lw=0, label="25th–75th")
    ax.plot(weeks, f[:, med], color=r["colour"], lw=2.2, label="median")
    ax.axhline(bankroll, color=MUTED, lw=0.8, ls="--")
    _style(ax)
    ax.set_title(r["label"], fontsize=10.5)
    ax.set_xlabel("weeks from now  (12 = end of 2026 regular season)")
    ax.set_xticks(weeks[::3])
    if len(weeks) > 14:
        ax.axvline(12, color=MUTED, lw=0.8, ls=":")
    end = f[-1]
    ax.text(weeks[-1], end[med], f"  ${end[med]:,.0f}", color=r["colour"], fontsize=9,
            va="center", fontweight="bold")
    ax.text(weeks[-1], end[lo], f"  ${end[lo]:,.0f}", color=MUTED, fontsize=8, va="center")
    ax.text(weeks[-1], end[hi], f"  ${end[hi]:,.0f}", color=MUTED, fontsize=8, va="center")
    ax.set_xlim(weeks[0], weeks[-1] + 2.2)


def table(runs: list[dict], bankroll: float) -> str:
    rows = ["| config | staking | median | 5th | 25th | 75th | 95th | P(down) | busts |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in runs:
        q = np.percentile(r["final"], [50, 5, 25, 75, 95])
        rows.append(f"| {r['label']} | {'weekly re-size' if r['resize'] else 'flat'} | "
                    f"${q[0]:,.0f} ({q[0]/bankroll-1:+.1%}) | ${q[1]:,.0f} | "
                    f"${q[2]:,.0f} | ${q[3]:,.0f} | ${q[4]:,.0f} | "
                    f"{(r['final'] < bankroll).mean():.1%} | {r['p_bust']:.1%} |")
    return "\n".join(rows)


def self_check() -> None:
    runs = run(paths=3_000, seed=1, bankroll=20_000)
    assert len(runs) == len(CONFIGS)
    for r in runs:
        assert r["fan"].shape[1] == len(PCTS)
        assert np.allclose(r["fan"][0], 20_000)
        # the fan must widen over the season
        assert r["fan"][-1, -1] - r["fan"][-1, 0] > r["fan"][1, -1] - r["fan"][1, 0]
    flat = run(paths=3_000, seed=1, bankroll=20_000, resize=False)
    assert all(g["p_bust"] == 0.0 for g in flat)
    one = run(paths=1_000, seed=1, bankroll=20_000, only_unit=0.01)
    assert len(one) == 1 and one[0]["unit"] == 0.01
    print("self-check OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bankroll", type=float, default=20_000.0)
    ap.add_argument("--paths", type=int, default=50_000)
    ap.add_argument("--seed", type=int, default=20260921)
    ap.add_argument("--out", help="docs directory; writes figs/<stem>.png")
    ap.add_argument("--flat-stakes", action="store_true",
                    help="add a second row with flat units off the starting bankroll")
    ap.add_argument("--seasons", type=int, default=1)
    ap.add_argument("--only-unit", type=float,
                    help="chart one config only, by its gl_unit (e.g. 0.01)")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return
    runs = run(args.paths, args.seed, args.bankroll, seasons=args.seasons, only_unit=args.only_unit)
    flat = run(args.paths, args.seed, args.bankroll, resize=False, seasons=args.seasons,
               only_unit=args.only_unit) if args.flat_stakes else None
    print(table(runs + (flat or []), args.bankroll))
    if args.out:
        figure(runs, args.bankroll, Path(args.out) / "figs" / f"{STEM}.png", flat)


if __name__ == "__main__":
    main()
