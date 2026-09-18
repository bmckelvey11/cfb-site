"""Distribution of combined points scored per FBS game, and its key numbers.

Re-runnable study behind docs/total-points-distribution-2026-09-17.md. Reads
core-ish staging (stg.game) from the local DuckDB, which carries a *per-season*
classification -- core.dim_team.is_fbs is current-state only and would
misclassify teams that moved FBS<->FCS mid-window.

Writes docs/img/total-points-distribution.png plus a frequency CSV, and prints
every number quoted in the note. Read-only against the warehouse.

Usage: python scripts/analyze_total_points_distribution.py [--start 2014] [--end 2025]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from cfb_paths import DB_PATH  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--start", type=int, default=2014, help="first season (inclusive)")
parser.add_argument("--end", type=int, default=2025, help="last complete season (inclusive)")
parser.add_argument("--top", type=int, default=8, help="how many spikes to highlight")
parser.add_argument("--xmax", type=int, default=100, help="right edge of the plotted range")
args = parser.parse_args()

OUT = REPO / "docs" / "img"
OUT.mkdir(parents=True, exist_ok=True)

QUERY = """
select season,
       "homePoints" as home,
       "awayPoints" as away,
       "homePoints" + "awayPoints" as total
from stg.game
where season between ? and ?
  and "homeClassification" = 'fbs'
  and "awayClassification" = 'fbs'
  and "homePoints" is not null
  and "awayPoints" is not null
order by season
"""

con = duckdb.connect(str(DB_PATH), read_only=True)
df = con.execute(QUERY, [args.start, args.end]).fetchdf()
con.close()

totals = df["total"].to_numpy(dtype=int)
n = totals.size
if n == 0:
    raise SystemExit(f"no FBS-vs-FBS games with scores in {args.start}-{args.end}")

lo, hi = int(totals.min()), int(totals.max())
# One bin per integer point. Anything wider smears out the exact-value spikes
# that the whole question is about.
edges = np.arange(lo, hi + 2)
counts, _ = np.histogram(totals, bins=edges)
values = edges[:-1]
pct = counts / n * 100.0

order = np.argsort(counts)[::-1]
top_idx = np.sort(order[: args.top])
top_values = set(values[top_idx].tolist())

mean, median = totals.mean(), float(np.median(totals))

# ---- numbers quoted in the note -------------------------------------------
print(f"population: FBS vs FBS, {args.start}-{args.end}, n={n:,} games")
print(f"range {lo}-{hi}   mean {mean:.2f}   median {median:.1f}   sd {totals.std(ddof=1):.2f}")
print(f"\ntop {args.top} exact totals:")
for i in order[: args.top]:
    print(f"  {values[i]:>3}  {counts[i]:>5} games  {pct[i]:5.2f}%")

# Raw frequency mixes three things: the bell envelope, an odd/even parity
# effect, and genuine single-value spikes. Comparing each value to its
# SAME-PARITY neighbours (v-4, v-2, v+2, v+4) cancels the first two, so what is
# left is the spike itself. Only scored over the dense middle of the range.
# The window is symmetric about v, so its mean already removes any linear trend
# in the envelope exactly -- a least-squares line through those four points
# evaluated at v IS their mean. Only curvature leaks through; see the robustness
# check below.
neigh = np.full(counts.shape, np.nan, dtype=float)
for j in range(4, len(counts) - 4):
    base = counts[[j - 4, j - 2, j + 2, j + 4]].mean()
    if base > 0:
        neigh[j] = counts[j] / base
# >=100 games in the bin: below that the ratio is mostly Poisson noise and the
# ranking fills up with thin tail bins.
dense = (values >= 20) & (values <= 90) & (counts >= 100) & ~np.isnan(neigh)
lift_order = np.argsort(np.where(dense, neigh, -1))[::-1]
print(f"\ntop {args.top} by lift over same-parity neighbours (totals 20-90, n>=100):")
print("   v      n   lift   lift(quadratic baseline)")
for i in lift_order[: args.top]:
    # Robustness: fit a quadratic through six same-parity neighbours so local
    # curvature cannot be mistaken for a spike.
    off = np.array([-6, -4, -2, 2, 4, 6])
    quad = np.polyval(np.polyfit(off, counts[i + off].astype(float), 2), 0)
    print(f"  {values[i]:>3}  {counts[i]:>5}  {neigh[i]:.2f}x  {counts[i] / quad:.2f}x")

# Each team's score is near a parity coin flip, so INDEPENDENT parities would put
# even totals at ~50%. They are below that, which means the two teams' score
# parities are anti-correlated.
home_odd = (df["home"] % 2 == 1).mean()
away_odd = (df["away"] % 2 == 1).mean()
indep_even = home_odd * away_odd + (1 - home_odd) * (1 - away_odd)
even = totals % 2 == 0
print(f"\neven totals {even.mean()*100:.2f}%   odd {100-even.mean()*100:.2f}%")
print(
    f"  P(home score odd) {home_odd:.4f}   P(away score odd) {away_odd:.4f}"
    f"   =>  P(even) under independence {indep_even*100:.2f}%"
)
for k in (40, 45, 50, 55, 60):
    print(f"  P(total > {k}) = {(totals > k).mean()*100:5.2f}%")

print("\nmean by season (drift check):")
for s in sorted(df["season"].unique()):
    sub = df.loc[df["season"] == s, "total"]
    print(f"  {s}  n={len(sub):>4}  mean {sub.mean():5.2f}  median {sub.median():4.1f}")

csv_path = OUT.parent / "data" / "total-points-frequency.csv"
csv_path.parent.mkdir(parents=True, exist_ok=True)
cum = np.cumsum(counts) / n * 100.0
with csv_path.open("w", encoding="utf-8") as fh:
    fh.write("total_points,games,pct,cumulative_pct\n")
    for v, c, p, cu in zip(values, counts, pct, cum):
        fh.write(f"{v},{c},{p:.4f},{cu:.4f}\n")
print(f"\nwrote {csv_path.relative_to(REPO)}")

# ---- chart -----------------------------------------------------------------
BASE, HILITE = "#9fb3c8", "#c0392b"
fig, (ax, ax2) = plt.subplots(
    2, 1, figsize=(13, 8), dpi=140, sharex=True, gridspec_kw={"height_ratios": [2.4, 1]}
)

colors = [HILITE if v in top_values else BASE for v in values]
ax.bar(values, counts, width=1.0, color=colors, edgecolor="white", linewidth=0.25)

ax.axvline(mean, color="#1f3a5f", lw=1.4, ls="--", zorder=3)
ax.axvline(median, color="#1f3a5f", lw=1.4, ls=":", zorder=3)

ymax = counts.max()
ax.text(mean + 0.8, ymax * 1.16, f"mean {mean:.1f}", color="#1f3a5f", fontsize=9, ha="left")
ax.text(mean + 0.8, ymax * 1.08, f"median {median:.0f}", color="#1f3a5f", fontsize=9, ha="left")

# Only the leading spikes get an on-bar label; below that the values sit 1 point
# apart (44/45, 58/59) and the labels overlap. The box lists the full ranking.
for i in np.sort(order[:4]):
    ax.annotate(
        str(values[i]),
        xy=(values[i], counts[i]),
        xytext=(0, 5),
        textcoords="offset points",
        ha="center",
        fontsize=9,
        color=HILITE,
        fontweight="bold",
        zorder=6,
        bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none"),
    )

table = "\n".join(f"{values[i]:>3}   {pct[i]:.2f}%" for i in order[: args.top])
ax.text(
    0.012,
    0.97,
    f"most frequent totals\n{table}\n\nodd {100 - even.mean() * 100:.1f}%  /  even {even.mean() * 100:.1f}%",
    transform=ax.transAxes,
    va="top",
    ha="left",
    fontsize=8.5,
    family="monospace",
    color="#1f3a5f",
    bbox=dict(boxstyle="round,pad=0.5", fc="#f4f7fa", ec="#cbd6e2", lw=0.8),
)

ax.set_ylim(0, ymax * 1.22)
ax.set_ylabel("Games")
ax.set_title(
    f"FBS combined game totals, {args.start}-{args.end}  (n={n:,})\n"
    f"red = {args.top} most frequent exact totals",
    fontsize=12,
)
ax.grid(axis="y", alpha=0.25, lw=0.6)
ax.set_axisbelow(True)

# Cumulative panel, drawn from the tail as P(total > x) so it is the exceedance
# table plotted rather than its complement -- a reader moving between the two
# should not have to subtract from 100.
surv = 100.0 - cum
ax2.step(values, surv, where="mid", color="#1f3a5f", lw=1.8)
for k in (40, 45, 50, 55, 60):
    # `values` starts at `lo`, not 0 -- index by offset, not by the total itself.
    j = k - lo
    ax2.plot([k], [surv[j]], "o", color=HILITE, ms=5, zorder=4)
    ax2.annotate(
        f"{surv[j]:.1f}%",
        xy=(k, surv[j]),
        xytext=(4, -11),
        textcoords="offset points",
        fontsize=8.5,
        color=HILITE,
        fontweight="bold",
    )
ax2.set_ylim(0, 100)
ax2.set_yticks([0, 25, 50, 75, 100])
ax2.set_ylabel("P(total > x)")
ax2.set_xlabel("Combined points scored (1-point bins)")
ax2.set_xlim(lo - 1, args.xmax)
ax2.set_xticks(np.arange(0, args.xmax + 1, 5))
ax2.grid(axis="y", alpha=0.25, lw=0.6)
ax2.set_axisbelow(True)

for a in (ax, ax2):
    for side in ("top", "right"):
        a.spines[side].set_visible(False)

fig.tight_layout()
png = OUT / "total-points-distribution.png"
fig.savefig(png)
print(f"wrote {png.relative_to(REPO)}")
