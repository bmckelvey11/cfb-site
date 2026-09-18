"""Distribution of the scoring margin per FBS game, and its key numbers.

Companion to analyze_total_points_distribution.py, behind
docs/scoring-margin-distribution-2026-09-18.md. Same population and the same
per-season classification from stg.game -- core.dim_team.is_fbs is current-state
and would misclassify teams that moved FBS<->FCS inside the window.

No neighbour-lift machinery here, unlike the totals study: 3 and 7 stand roughly
3x above their neighbours, so exact frequency and the cumulative curve carry the
argument on their own. A same-parity baseline would also beg the question, since
the scoring arithmetic that shapes margins IS what such a baseline assumes away.

Writes docs/img/scoring-margin-distribution.png plus a frequency CSV, and prints
every number quoted in the note. Read-only against the warehouse.

Usage: python scripts/analyze_scoring_margin_distribution.py [--start 2014] [--end 2025]
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
parser.add_argument("--top", type=int, default=14, help="how many exact margins to rank")
parser.add_argument("--xmax", type=int, default=50, help="right edge of the plotted range")
args = parser.parse_args()

OUT = REPO / "docs" / "img"
OUT.mkdir(parents=True, exist_ok=True)

# The points columns come back unsigned, so a bare subtraction underflows on any
# road win. Cast before differencing.
QUERY = """
select season,
       "homePoints"::INTEGER as home,
       "awayPoints"::INTEGER as away,
       "homePoints"::INTEGER - "awayPoints"::INTEGER as signed_margin
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

signed = df["signed_margin"].to_numpy(dtype=int)
margin = np.abs(signed)
n = margin.size
if n == 0:
    raise SystemExit(f"no FBS-vs-FBS games with scores in {args.start}-{args.end}")

counts = np.bincount(margin)
values = np.arange(counts.size)
pct = counts / n * 100.0
cum = np.cumsum(counts) / n * 100.0

# ---- numbers quoted in the note -------------------------------------------
print(f"population: FBS vs FBS, {args.start}-{args.end}, n={n:,} games")
print(
    f"margin  mean {margin.mean():.2f}   median {np.median(margin):.1f}"
    f"   sd {margin.std(ddof=1):.2f}   max {margin.max()}"
)
print(f"ties: {(margin == 0).sum()}  (overtime has settled every game since 1996)")

print(f"\ntop {args.top} exact margins:")
for i in np.argsort(counts)[::-1][: args.top]:
    print(f"  {values[i]:>3}  {counts[i]:>5} games  {pct[i]:5.2f}%   cumulative <= {cum[i]:5.2f}%")

print("\nthe classic key numbers, exact and cumulative:")
for k in (1, 2, 3, 4, 6, 7, 8, 10, 13, 14, 17, 21):
    print(f"  margin == {k:>2}: {pct[k]:5.2f}%      margin <= {k:>2}: {cum[k]:5.2f}%")

print(f"\none score (<= 8):  {cum[8]:5.2f}%")
print(f"two scores (<=16): {cum[16]:5.2f}%")

# Total and margin differ by 2*away, so they ALWAYS share parity -- this is the
# same statistic as the odd-total share in the totals study, not a second result.
print(f"\nodd margins {(margin % 2 == 1).mean()*100:.2f}%  (identical to the odd-total share by construction)")

home_win = (signed > 0).mean()
print(f"\nhome win rate {home_win*100:.2f}%   mean signed home margin {signed.mean():+.2f}")


def ols_slope(seasons: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Slope of y on season, its SE and t. Each game appears once, so plain OLS."""
    x = seasons.astype(float)
    x = x - x.mean()
    b = float((x * y).sum() / (x * x).sum())
    resid = y - (y.mean() + b * x)
    s2 = float((resid**2).sum() / (len(x) - 2))
    se = float((s2 / (x * x).sum()) ** 0.5)
    return b, se, b / se


seasons = df["season"].to_numpy(dtype=int)
print("\nis home-field advantage trending? (signed margin on season)")
for label, keep in (("all seasons", np.ones(n, bool)), ("excl. 2020", seasons != 2020)):
    b, se, t = ols_slope(seasons[keep], signed[keep].astype(float))
    print(
        f"  {label:<12} slope {b:+.4f} pts/season   SE {se:.4f}   t={t:+.2f}"
        f"   over 11 seasons {b*11:+.2f}   n={keep.sum():,}"
    )

print("\nby season:")
print("  season     n  home win%  mean signed   ==3%   ==7%   <=3%   <=7%  <=14%")
for s in sorted(np.unique(seasons)):
    k = seasons == s
    mk, sk = margin[k], signed[k]
    print(
        f"  {s}  {k.sum():>4}  {(sk > 0).mean()*100:8.2f}%  {sk.mean():+10.2f}"
        f"  {(mk == 3).mean()*100:5.2f}% {(mk == 7).mean()*100:5.2f}%"
        f" {(mk <= 3).mean()*100:5.2f}% {(mk <= 7).mean()*100:5.2f}% {(mk <= 14).mean()*100:5.2f}%"
    )

csv_path = OUT.parent / "data" / "scoring-margin-frequency.csv"
csv_path.parent.mkdir(parents=True, exist_ok=True)
with csv_path.open("w", encoding="utf-8") as fh:
    fh.write("margin,games,pct,cumulative_pct\n")
    for v, c, p, cu in zip(values, counts, pct, cum):
        fh.write(f"{v},{c},{p:.4f},{cu:.4f}\n")
print(f"\nwrote {csv_path.relative_to(REPO)}")

# ---- chart -----------------------------------------------------------------
KEY = (3, 7, 10, 14)
BASE, HILITE = "#9fb3c8", "#c0392b"
fig, (ax, ax2) = plt.subplots(
    2, 1, figsize=(13, 8), dpi=140, sharex=True, gridspec_kw={"height_ratios": [2.4, 1]}
)

hi = args.xmax + 1
colors = [HILITE if v in KEY else BASE for v in values[:hi]]
ax.bar(values[:hi], counts[:hi], width=1.0, color=colors, edgecolor="white", linewidth=0.3)
for k in KEY:
    ax.annotate(
        f"{k}\n{pct[k]:.2f}%",
        xy=(k, counts[k]),
        xytext=(0, 6),
        textcoords="offset points",
        ha="center",
        fontsize=9,
        color=HILITE,
        fontweight="bold",
    )
ax.set_ylim(0, counts[:hi].max() * 1.20)
ax.set_ylabel("Games")
ax.set_title(
    f"FBS scoring margin, {args.start}-{args.end}  (n={n:,})\n"
    "red = the classic key numbers 3, 7, 10, 14",
    fontsize=12,
)
ax.grid(axis="y", alpha=0.25, lw=0.6)
ax.set_axisbelow(True)

ax2.step(values[:hi], cum[:hi], where="mid", color="#1f3a5f", lw=1.8)
for k in KEY:
    ax2.plot([k], [cum[k]], "o", color=HILITE, ms=5, zorder=4)
    ax2.annotate(
        f"{cum[k]:.1f}%",
        xy=(k, cum[k]),
        xytext=(4, -11),
        textcoords="offset points",
        fontsize=8.5,
        color=HILITE,
        fontweight="bold",
    )
ax2.set_ylim(0, 100)
ax2.set_yticks([0, 25, 50, 75, 100])
ax2.set_ylabel("P(margin ≤ x)")
ax2.set_xlabel("Absolute scoring margin")
ax2.set_xticks(np.arange(0, args.xmax + 1, 5))
ax2.set_xlim(-1, args.xmax)
ax2.grid(axis="y", alpha=0.25, lw=0.6)
ax2.set_axisbelow(True)

for a in (ax, ax2):
    for side in ("top", "right"):
        a.spines[side].set_visible(False)

fig.tight_layout()
png = OUT / "scoring-margin-distribution.png"
fig.savefig(png)
print(f"wrote {png.relative_to(REPO)}")
