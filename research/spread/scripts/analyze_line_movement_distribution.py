"""Descriptive distribution of the open-to-close spread move, and where lines settle.

This is the DESCRIPTIVE companion to the line-movement research in this tree, not
part of it: `prereg-line-movement.md` and `line-movement-results.md` ask whether
the PT panel FORECASTS the move. This script only measures the move itself --
how far lines travel, how often they sit still, and which numbers they end on.

Source is the warehouse, not the PT archive. `core.fact_game_line` carries a real
book open and close per provider, but only from 2021, and only Bovada spans the
whole window: DraftKings enters in 2023 and ESPN Bet in 2024, so a median-across-
books series would change composition mid-window. One book, stated, beats a
moving basket. That makes this a different population from the totals and margin
studies in root docs/ (2014-2025, all books, n=9,085).

Writes research/spread/docs/img/line-movement-distribution.png plus a move
frequency CSV, and prints every number quoted in the note. Read-only.

Usage: python research/spread/scripts/analyze_line_movement_distribution.py
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

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from cfb_paths import DB_PATH  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--start", type=int, default=2021, help="first season (open/close begins 2021)")
parser.add_argument("--end", type=int, default=2025, help="last complete season")
parser.add_argument("--book", default="bovada", help="provider_key to use as the series")
args = parser.parse_args()

OUT = REPO / "research" / "spread" / "docs" / "img"
OUT.mkdir(parents=True, exist_ok=True)

QUERY = """
with fbs as (
  select gameId as game_id, season
  from stg.game
  where "homeClassification" = 'fbs' and "awayClassification" = 'fbs'
)
select f.season,
       l.spread_open  as open_,
       l.spread_close as close_
from core.fact_game_line l
join fbs f using (game_id)
where l.provider_key = ?
  and l.spread_open is not null
  and l.spread_close is not null
  and f.season between ? and ?
order by f.season
"""

con = duckdb.connect(str(DB_PATH), read_only=True)
df = con.execute(QUERY, [args.book, args.start, args.end]).fetchdf()
con.close()

seasons = df["season"].to_numpy(dtype=int)
open_ = df["open_"].to_numpy(dtype=float)
close_ = df["close_"].to_numpy(dtype=float)
n = open_.size
if n == 0:
    raise SystemExit(f"no {args.book} open/close pairs in {args.start}-{args.end}")

# Spreads are home-relative, so a positive move means the home side got worse.
move = close_ - open_
a_open, a_close = np.abs(open_), np.abs(close_)

print(f"population: FBS vs FBS, {args.book}, {args.start}-{args.end}, n={n:,} games")
print(f"opener: mean {open_.mean():+.2f}   median {np.median(open_):+.1f}")
print(
    f"move (close - open, home-relative): mean {move.mean():+.3f}"
    f"   sd {move.std(ddof=1):.2f}   median {np.median(move):+.1f}"
)
print(
    f"|move|: mean {np.abs(move).mean():.2f}   median {np.median(np.abs(move)):.1f}"
    f"   p90 {np.percentile(np.abs(move), 90):.1f}   max {np.abs(move).max():.1f}"
)

print(f"\nlines that never move: {(move == 0).mean()*100:.2f}%")
for t in (0.5, 1, 1.5, 2, 3, 5, 7):
    print(f"  |move| <= {t:>3}: {(np.abs(move) <= t).mean()*100:5.2f}%")

same_side = np.sign(open_) == np.sign(close_)
print(f"\nfavourite got MORE favoured: {((a_close > a_open) & same_side).mean()*100:5.2f}%")
print(f"favourite got LESS favoured: {((a_close < a_open) & same_side).mean()*100:5.2f}%")
print(f"line flipped sides:          {(~same_side & (open_ != 0) & (close_ != 0)).mean()*100:5.2f}%")

print("\nmost common exact moves:")
vals, cnt = np.unique(move, return_counts=True)
for i in np.argsort(cnt)[::-1][:8]:
    print(f"  {vals[i]:+5.1f}  {cnt[i]:>5} games  {cnt[i]/n*100:5.2f}%")

print("\nwhere lines SIT, open vs close (absolute spread):")
print("     k    open%   close%    delta")
for k in (1, 1.5, 2, 2.5, 3, 3.5, 4, 6, 6.5, 7, 7.5, 10, 13.5, 14):
    po, pc = (a_open == k).mean() * 100, (a_close == k).mean() * 100
    print(f"  {k:>4}   {po:6.2f}   {pc:6.2f}   {pc-po:+6.2f}")
print(
    f"\n  on a whole number: open {(a_open % 1 == 0).mean()*100:.2f}%"
    f"   close {(a_close % 1 == 0).mean()*100:.2f}%"
)
print(
    f"  on 3 or 7 exactly: open {((a_open == 3) | (a_open == 7)).mean()*100:.2f}%"
    f"   close {((a_close == 3) | (a_close == 7)).mean()*100:.2f}%"
)

# Inflow and retention are different mechanisms and the two key numbers differ on
# them -- 7 is genuinely sticky, 3 only attracts. Keep them apart.
for k in (3, 7):
    onto = (a_close == k) & (a_open != k)
    off = (a_open == k) & (a_close != k)
    lo, hi = np.minimum(a_open, a_close), np.maximum(a_open, a_close)
    through = (lo < k) & (hi > k)
    stay = ((a_open == k) & (a_close == k)).sum() / max((a_open == k).sum(), 1) * 100
    print(f"\nkey number {k}:")
    print(f"  opened on {k}: {(a_open == k).mean()*100:5.2f}%    closed on {k}: {(a_close == k).mean()*100:5.2f}%")
    print(
        f"  moved ONTO {k}: {onto.mean()*100:5.2f}%   moved OFF {k}: {off.mean()*100:5.2f}%"
        f"   net {(onto.mean()-off.mean())*100:+5.2f}%"
    )
    print(f"  jumped THROUGH {k} without settling: {through.mean()*100:5.2f}%")
    print(f"  retention -- opened on {k} and closed on {k}: {stay:5.2f}%  (n={(a_open == k).sum()})")
    for nb in (k - 0.5, k + 0.5):
        s2 = ((a_open == nb) & (a_close == nb)).sum() / max((a_open == nb).sum(), 1) * 100
        print(f"     same for {nb}: {s2:5.2f}%  (n={(a_open == nb).sum()})")


def mean_t(y: np.ndarray) -> tuple[float, float, float]:
    se = float(y.std(ddof=1) / len(y) ** 0.5)
    return float(y.mean()), se, float(y.mean() / se)


print("\nis there a systematic drift in the move?")
for label, keep in (("all seasons", np.ones(n, bool)), ("excl. 2024", seasons != 2024)):
    m, se, t = mean_t(move[keep])
    print(f"  {label:<12} mean {m:+.4f}   se {se:.4f}   t={t:+.2f}   n={keep.sum():,}")

print("\nby season:")
print("  season     n    mean move   sd     no-move%   close on 3 or 7")
for s in sorted(np.unique(seasons)):
    k = seasons == s
    mk = move[k]
    k37 = ((a_close[k] == 3) | (a_close[k] == 7)).mean() * 100
    print(
        f"  {s}  {k.sum():>4}   {mk.mean():+8.3f}  {mk.std(ddof=1):5.2f}"
        f"   {(mk == 0).mean()*100:7.2f}%   {k37:9.2f}%"
    )

csv_path = REPO / "research" / "spread" / "docs" / "data" / "line-movement-frequency.csv"
csv_path.parent.mkdir(parents=True, exist_ok=True)
with csv_path.open("w", encoding="utf-8") as fh:
    fh.write("move,games,pct\n")
    for v, cc in zip(vals, cnt):
        fh.write(f"{v},{cc},{cc/n*100:.4f}\n")
print(f"\nwrote {csv_path.relative_to(REPO)}")

# ---- chart -----------------------------------------------------------------
BASE, HILITE = "#9fb3c8", "#c0392b"
fig, (ax, ax2) = plt.subplots(
    2, 1, figsize=(13, 8), dpi=140, gridspec_kw={"height_ratios": [1.5, 1]}
)

lim = 6.0
edges = np.arange(-lim - 0.25, lim + 0.5, 0.5)
ax.hist(np.clip(move, -lim, lim), bins=edges, color=BASE, edgecolor="white", linewidth=0.4)
ax.axvline(0, color="#1f3a5f", lw=1.3, ls="--")
ax.set_xlabel("Close − open, home-relative (half-point bins, clipped at ±6)")
ax.set_ylabel("Games")
ax.set_title(
    f"FBS spread movement, open to close — {args.book}, {args.start}-{args.end}  (n={n:,})\n"
    f"{(move == 0).mean()*100:.1f}% of lines never move; sd {move.std(ddof=1):.2f}",
    fontsize=12,
)
ax.grid(axis="y", alpha=0.25, lw=0.6)
ax.set_axisbelow(True)

ks = np.arange(0.5, 14.5, 0.5)
po = np.array([(a_open == k).mean() * 100 for k in ks])
pc = np.array([(a_close == k).mean() * 100 for k in ks])
w = 0.2
ax2.bar(ks - w / 2, po, width=w, color=BASE, label="Open")
ax2.bar(ks + w / 2, pc, width=w, color=HILITE, label="Close")
for k in (3, 7):
    ax2.annotate(
        f"+{(a_close == k).mean()*100 - (a_open == k).mean()*100:.2f} pp",
        xy=(k, max((a_open == k).mean(), (a_close == k).mean()) * 100),
        xytext=(0, 7),
        textcoords="offset points",
        ha="center",
        fontsize=9,
        color=HILITE,
        fontweight="bold",
    )
ax2.set_xlabel("Absolute spread")
ax2.set_ylabel("% of games")
ax2.set_xticks(np.arange(0, 15, 1))
ax2.set_xlim(0, 14.5)
ax2.set_ylim(0, max(po.max(), pc.max()) * 1.2)
ax2.legend(frameon=False, fontsize=9)
ax2.grid(axis="y", alpha=0.25, lw=0.6)
ax2.set_axisbelow(True)

for a in (ax, ax2):
    for side in ("top", "right"):
        a.spines[side].set_visible(False)

fig.tight_layout()
png = OUT / "line-movement-distribution.png"
fig.savefig(png)
print(f"wrote {png.relative_to(REPO)}")
