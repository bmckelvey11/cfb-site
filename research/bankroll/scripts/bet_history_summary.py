"""Hit rate + ROI table and cumulative-units graph from the book export.

    python research/bankroll/scripts/bet_history_summary.py [--year 2026] [--out DIR]

Reads data/ingest/bet_history/history.csv (main table only; the parlay/teaser
section after the first blank line is skipped). ROI = units net / units wagered;
pushes count as bets with 0 net but are excluded from hit rate.
"""

import argparse
import csv
import datetime as dt
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SRC = Path(__file__).resolve().parents[3] / "data" / "ingest" / "bet_history" / "history.csv"


def load(year, src=SRC):
    rows = list(csv.reader(open(src, encoding="utf-8")))
    hdr, out = rows[1], []
    for r in rows[2:]:
        if not r or not r[0].strip():
            break
        d = dict(zip(hdr, r))
        if d["Start Time"].startswith(str(year)):
            out.append(d)
    return sorted(out, key=lambda d: d["Start Time"])


def key(b, by):
    t = b["Start Time"]
    if by == "month":
        return t[:7]
    if by == "type":
        return b["Type"].split("_")[0] + (" 1H" if b["Period"] == "firsthalf" else "")
    d = dt.datetime.fromisoformat(t[:19]) - dt.timedelta(hours=6)  # late-night kicks stay with their Saturday
    return (d - dt.timedelta(days=(d.weekday() - 3) % 7)).strftime("wk of %m-%d")  # Thu-Wed weeks


def stats(bets):
    w = sum(b["Result"] == "win" for b in bets)
    l = sum(b["Result"] == "loss" for b in bets)
    wag = sum(float(b["Units Wagered"]) for b in bets)
    net = sum(float(b["Units Net"]) for b in bets)
    return len(bets), w, l, w / (w + l) if w + l else 0, wag, net, net / wag if wag else 0


def self_check():
    bets = [{"Result": "win", "Units Wagered": "1", "Units Net": "0.9"},
            {"Result": "loss", "Units Wagered": "1", "Units Net": "-1"}]
    n, w, l, hr, wag, net, roi = stats(bets)
    assert (n, w, l, hr, wag) == (2, 1, 1, 0.5, 2.0) and abs(roi + 0.05) < 1e-9
    print("self-check ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--by", choices=["month", "week", "type"], default="week")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "out"))
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    bets = load(a.year, a.src)
    groups = defaultdict(list)
    for b in bets:
        groups[key(b, a.by)].append(b)

    print(f"| {a.by.title()} | Bets | W-L | Hit % | Units wagered | Units net | ROI |\n|---|---|---|---|---|---|---|")
    for k, g in [*sorted(groups.items()), ("Total", bets)]:
        n, w, l, hr, wag, net, roi = stats(g)
        print(f"| {k} | {n} | {w}-{l} | {hr:.1%} | {wag:.1f} | {net:+.2f} | {roi:+.1%} |")

    cum, s = [], 0
    for b in bets:
        s += float(b["Units Net"])
        cum.append(s)
    n, w, l, hr, wag, net, roi = stats(bets)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(range(1, len(cum) + 1), cum, marker="o", ms=3)
    ax.axhline(0, color="grey", lw=0.8)
    ax.set(xlabel="Bet #", ylabel="Cumulative units",
           title=f"{a.year} bets: {w}-{l} ({hr:.1%}), ROI {roi:+.1%}, {net:+.2f}u")
    Path(a.out).mkdir(parents=True, exist_ok=True)
    p = Path(a.out) / f"bet_history_{a.year}.png"
    fig.tight_layout()
    fig.savefig(p, dpi=120)
    print(f"\n{p}")


if __name__ == "__main__":
    main()
