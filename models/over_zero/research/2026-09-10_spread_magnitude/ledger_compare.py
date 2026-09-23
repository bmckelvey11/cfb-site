"""Did the cap's evidence survive the move to the warehouse ledger?

The 50-point cap (RESULTS-2D.md) was chosen on the Aug 28 ledger: raw CFBD JSON,
2016-2025, 234 bets, about a quarter of all games priced off projection sites. The
current `docs/backtest_bets.csv` is warehouse-sourced (book lines only), 2020-2026.
This script puts the >cut bets of the two ledgers side by side, per season, and
follows each old >cut bet into the new ledger, so a reader can see whether the old
record changed because its lines were unbettable or because the seasons changed.

The old ledger is read from git (`96799f3f`, the last commit before the Sep 22
refreshes), not from a copy on disk, so this reproduces from a clean checkout.

    python models/over_zero/research/2026-09-10_spread_magnitude/ledger_compare.py
"""

from __future__ import annotations

import argparse
import io
import subprocess
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[4]
LEDGER = "models/over_zero/docs/backtest_bets.csv"
OLD_REV = "96799f3f"
KEY = ["season", "home_team", "away_team"]


def old_ledger(rev: str) -> pd.DataFrame:
    raw = subprocess.run(["git", "show", f"{rev}:{LEDGER}"], cwd=REPO,
                         capture_output=True, check=True).stdout
    return pd.read_csv(io.BytesIO(raw))


def rec(d: pd.DataFrame) -> str:
    w = int(d.over.sum())
    return f"{w}-{len(d) - w} {d.flat_units_pnl.sum():+.2f}u"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", type=float, default=50.0)
    ap.add_argument("--rev", default=OLD_REV, help="git revision holding the old ledger")
    args = ap.parse_args()

    old = old_ledger(args.rev)
    new = pd.read_csv(REPO / LEDGER)
    ob, nb = old[old.passes_filter == 1], new[new.passes_filter == 1]

    print(f"bets above {args.cut:g} / at or below, by season  (old = {args.rev}, new = working tree)")
    for s in sorted(set(ob.season) | set(nb.season)):
        cells = []
        for b in (ob, nb):
            g = b[b.season == s]
            cells += [rec(g[g.spread > args.cut]), rec(g[g.spread <= args.cut])] if len(g) else ["--", "--"]
        print(f"  {s}   old {cells[0]:>13} | {cells[1]:>14}    new {cells[2]:>13} | {cells[3]:>14}")

    both = sorted(set(ob.season) & set(nb.season))
    for name, b in (("old", ob), ("new", nb)):
        o = b[b.season.isin(both)]
        print(f"overlap {both[0]}-{both[-1]} {name}: >{args.cut:g} {rec(o[o.spread > args.cut])}   "
              f"<={args.cut:g} {rec(o[o.spread <= args.cut])}")

    # Where did each old >cut bet go? If the old record came from unbettable
    # projection-site totals, these rows would drop out or change line.
    o50 = ob[ob.spread > args.cut]
    m = o50.merge(new[KEY + ["spread", "total", "passes_filter"]], on=KEY, how="left",
                  suffixes=("", "_new"))
    m["fate"] = "not graded in new"
    m.loc[m.passes_filter_new == 1, "fate"] = "still a bet"
    m.loc[m.passes_filter_new == 0, "fate"] = "graded, no longer a bet"
    m.loc[~m.season.isin(nb.season.unique()), "fate"] = "season not bet in new"
    m["line_moved"] = m.spread_new.notna() & ((m.spread != m.spread_new) | (m.total != m.total_new))
    print(f"\nfate of the {len(o50)} old >{args.cut:g} bets:")
    for fate, g in m.groupby("fate"):
        print(f"  {fate:<24} n={len(g):>2}  {rec(g):>13}  line moved on {int(g.line_moved.sum())}")

    added = nb[nb.spread > args.cut].merge(ob[KEY], on=KEY, how="left", indicator=True)
    added = added[added._merge == "left_only"]
    print(f"\nnew >{args.cut:g} bets absent from the old ledger's bets: {len(added)}  {rec(added)}")
    print(added[KEY + ["spread", "total", "bias", "over"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
