"""Bankroll growth by week under the pooled Greenline prior only.

    python research/bankroll/scripts/pooled_growth_chart.py
    python research/bankroll/scripts/pooled_growth_chart.py --paths 100000 --out research/bankroll/docs
    python research/bankroll/scripts/pooled_growth_chart.py --self-check

The unit rule is to bracket both priors. This chart deliberately does not: it was
asked for as "the pooled edge, charted", so it conditions on the 141-109 record
(posterior mean 56.4%) and shows three configs side by side. The n49 reading is
in mc-combined-totals-2026-09-17.md and bankroll-config-sweep-2026-09-17.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mc_combined_totals import (  # noqa: E402
    GL_COVERAGE_HISTORICAL, PCTS, WEEKS_REMAINING, Config, simulate,
    BLUE, GREEN, GOLD, INK, MUTED, _style,
)

# (label, gl_unit, coverage, colour)
CONFIGS = (
    ("0.5% x 13% of flags  (recommended)", 0.005, GL_COVERAGE_HISTORICAL, BLUE),
    ("1.0% x 13% of flags", 0.01, GL_COVERAGE_HISTORICAL, GREEN),
    ("0.25% x every flag  (conditional on coverage)", 0.0025, 1.0, GOLD),
)
STEM = "pooled-bankroll-growth-2026-09-17"


def run(paths: int, seed: int, bankroll: float) -> list[dict]:
    out = []
    for label, unit, cov, colour in CONFIGS:
        res = simulate(Config(bankroll=bankroll, paths=paths, gl_unit=unit,
                              gl_prior="pooled", gl_coverage=cov, seed=seed))
        out.append(dict(label=label, colour=colour, fan=res["fan"], final=res["final"],
                        p_bust=res["p_bust"], unit=unit, coverage=cov))
    return out


def figure(runs: list[dict], bankroll: float, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    weeks = np.arange(3, 3 + WEEKS_REMAINING + 1)  # week 3 = start, before week 4 bets
    fig, axes = plt.subplots(1, len(runs), figsize=(15, 5.2), sharey=True)
    lo, hi = PCTS.index(5), PCTS.index(95)
    q1, q3, med = PCTS.index(25), PCTS.index(75), PCTS.index(50)
    for ax, r in zip(axes, runs):
        f = r["fan"]
        ax.fill_between(weeks, f[:, lo], f[:, hi], color=r["colour"], alpha=0.12, lw=0, label="5th–95th")
        ax.fill_between(weeks, f[:, q1], f[:, q3], color=r["colour"], alpha=0.28, lw=0, label="25th–75th")
        ax.plot(weeks, f[:, med], color=r["colour"], lw=2.2, label="median")
        ax.axhline(bankroll, color=MUTED, lw=0.8, ls="--")
        _style(ax)
        ax.set_title(r["label"], fontsize=10.5)
        ax.set_xlabel("week of the 2026 season")
        ax.set_xticks(weeks[::2])
        end = f[-1]
        ax.text(weeks[-1], end[med], f"  ${end[med]:,.0f}", color=r["colour"], fontsize=9,
                va="center", fontweight="bold")
        ax.text(weeks[-1], end[lo], f"  ${end[lo]:,.0f}", color=MUTED, fontsize=8, va="center")
        ax.text(weeks[-1], end[hi], f"  ${end[hi]:,.0f}", color=MUTED, fontsize=8, va="center")
        ax.set_xlim(weeks[0], weeks[-1] + 2.2)
    axes[0].set_ylabel("bankroll, $")
    axes[0].legend(fontsize=8, frameon=False, loc="upper left")
    fig.suptitle(f"Bankroll by week, pooled Greenline prior (141–109, mean 56.4%), "
                 f"${bankroll:,.0f} start", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.5, 0.905, "Win rate drawn per path from the pooled posterior only. The n49 "
             "reading is in the MC doc and the sweep. Flat stakes off the starting bankroll.",
             fontsize=9, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170, facecolor="white")
    print(f"wrote {path}")


def table(runs: list[dict], bankroll: float) -> str:
    rows = ["| config | median | 5th | 25th | 75th | 95th | P(down) | busts |",
            "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in runs:
        q = np.percentile(r["final"], [50, 5, 25, 75, 95])
        rows.append(f"| {r['label']} | ${q[0]:,.0f} ({q[0]/bankroll-1:+.1%}) | ${q[1]:,.0f} | "
                    f"${q[2]:,.0f} | ${q[3]:,.0f} | ${q[4]:,.0f} | "
                    f"{(r['final'] < bankroll).mean():.1%} | {r['p_bust']:.1%} |")
    return "\n".join(rows)


def self_check() -> None:
    runs = run(paths=3_000, seed=1, bankroll=20_000)
    assert len(runs) == len(CONFIGS)
    for r in runs:
        assert r["fan"].shape == (WEEKS_REMAINING + 1, len(PCTS))
        assert np.allclose(r["fan"][0], 20_000)
        # the fan must widen over the season
        assert r["fan"][-1, -1] - r["fan"][-1, 0] > r["fan"][1, -1] - r["fan"][1, 0]
    print("self-check OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bankroll", type=float, default=20_000.0)
    ap.add_argument("--paths", type=int, default=50_000)
    ap.add_argument("--seed", type=int, default=20260917)
    ap.add_argument("--out", help="docs directory; writes figs/<stem>.png")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return
    runs = run(args.paths, args.seed, args.bankroll)
    print(table(runs, args.bankroll))
    if args.out:
        figure(runs, args.bankroll, Path(args.out) / "figs" / f"{STEM}.png")


if __name__ == "__main__":
    main()
