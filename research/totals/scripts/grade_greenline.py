"""Grade captured Greenline totals flags against final scores.

    python research/totals/scripts/grade_greenline.py --week 2
    python research/totals/scripts/grade_greenline.py --all
    python research/totals/scripts/grade_greenline.py --self-check

Every open question about Greenline's totals -- whether the under tilt actually
wins, whether `value` ranks picks usefully, whether the edge concentrates at low
totals -- is a results question, and none of them can be answered from a single
pre-kickoff snapshot. This grades what was captured, week by week, so a month of
capture settles them.

The line graded is the one in the Greenline capture, not the closing number:
that is the price actually available when the flag appeared. Refresh the
schedule after kickoff (`scripts/pull_pff_scoreboard.py`) so final scores are
present, then run this. Graded rows accumulate in `greenline_graded.csv` so
weeks can be pooled.

A word on reading the output: one week is roughly 40 gradeable flags. At that
size a 60% record has a 95% interval of about 45-74%, so a single week decides
nothing. The by-band and by-value splits are there to accumulate, not to act on
after one slate.
"""

from __future__ import annotations

import argparse
import csv
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from cfb_paths import INGEST  # noqa: E402

IN_DIR = INGEST / "pff_scoreboard"
OUT = IN_DIR / "greenline_graded.csv"
PAYOUT = 100 / 110  # -110

GRADED_COLUMNS = ["pff_game_id", "season", "pff_week", "away_abbreviation", "home_abbreviation",
                  "line", "projection", "d", "side", "value", "actual_total", "result"]

BANDS = [("<50", lambda L: L < 50), ("50-54.5", lambda L: 50 <= L < 55),
         ("55-59.5", lambda L: 55 <= L < 60), ("60-64.5", lambda L: 60 <= L < 65),
         ("65+", lambda L: L >= 65)]

VALUE_BUCKETS = [("<2%", lambda v: v < 0.02), ("2-3%", lambda v: 0.02 <= v < 0.03),
                 ("3-4%", lambda v: 0.03 <= v < 0.04), ("4%+", lambda v: v >= 0.04)]


def num(v):
    return float(v) if v not in ("", None) else None


def grade_one(flag: dict, game: dict) -> dict | None:
    """None when the game has not finished or the capture lacks a line."""
    away, home = num(game.get("away_score")), num(game.get("home_score"))
    line, side = num(flag.get("market_over_under")), flag.get("total_best_side")
    if away is None or home is None or line is None or not side:
        return None
    if str(game.get("is_over", "")).lower() not in ("true", "1"):
        return None
    actual = away + home
    if actual == line:
        result = "push"
    elif (actual > line) == (side == "over"):
        result = "win"
    else:
        result = "loss"
    return {"pff_game_id": flag["pff_game_id"], "season": flag.get("season"),
            "pff_week": flag.get("pff_week"),
            "away_abbreviation": flag.get("away_abbreviation"),
            "home_abbreviation": flag.get("home_abbreviation"),
            "line": line, "projection": num(flag.get("greenline_total_projection")),
            "d": (num(flag.get("greenline_total_projection")) or 0) - line,
            "side": side, "value": num(flag.get("total_best_value")),
            "actual_total": actual, "result": result}


def tally(rows: list[dict]) -> dict:
    w = sum(1 for r in rows if r["result"] == "win")
    l = sum(1 for r in rows if r["result"] == "loss")
    p = sum(1 for r in rows if r["result"] == "push")
    risked = w + l  # pushes return the stake
    units = w * PAYOUT - l
    return {"n": len(rows), "w": w, "l": l, "p": p,
            "pct": w / risked * 100 if risked else float("nan"),
            "units": units, "roi": units / risked * 100 if risked else float("nan")}


def line_row(label: str, t: dict) -> str:
    if not t["n"]:
        return f"  {label:<10}   --"
    pushes = f" ({t['p']}p)" if t["p"] else ""
    return (f"  {label:<10} {t['w']:3d}-{t['l']:<3d}{pushes:<5} {t['pct']:5.1f}%  "
            f"{t['units']:+6.2f}u  {t['roi']:+6.1f}%")


def report(rows: list[dict]) -> None:
    if not rows:
        print("nothing gradeable yet -- refresh the schedule after kickoff so scores land")
        return
    print(f"{len(rows)} graded flags\n")
    print("  segment    record       win%    units      ROI")
    print(line_row("ALL", tally(rows)))
    print()
    for side in ("under", "over"):
        print(line_row(side, tally([r for r in rows if r["side"] == side])))
    print("\nby market total (under flags only):")
    unders = [r for r in rows if r["side"] == "under"]
    for lab, fn in BANDS:
        print(line_row(lab, tally([r for r in unders if fn(r["line"])])))
    print("\nby PFF value (under flags only) -- does their own ranking work?")
    for lab, fn in VALUE_BUCKETS:
        print(line_row(lab, tally([r for r in unders if r["value"] is not None and fn(r["value"])])))

    graded = [r for r in rows if r["result"] != "push" and r["projection"] is not None]
    if graded:
        err = [r["actual_total"] - r["projection"] for r in graded]
        merr = [r["actual_total"] - r["line"] for r in graded]
        print(f"\nprojection accuracy vs the market line (n={len(graded)}):")
        print(f"  PFF projection   mean error {st.mean(err):+6.2f}  MAE {st.mean([abs(e) for e in err]):5.2f}")
        print(f"  market line      mean error {st.mean(merr):+6.2f}  MAE {st.mean([abs(e) for e in merr]):5.2f}")
        better = sum(1 for a, b in zip(err, merr) if abs(a) < abs(b))
        print(f"  PFF closer than the market in {better}/{len(graded)} games")
        print("  (mean error below zero means games landed under both numbers)")


def load(season: int, weeks: list[str]) -> list[dict]:
    sched_path = IN_DIR / f"pff_schedule_{season}.csv"
    if not sched_path.exists():
        raise SystemExit(f"{sched_path} not found -- run scripts/pull_pff_scoreboard.py")
    sched = {x["pff_game_id"]: x for x in csv.DictReader(sched_path.open(encoding="utf-8"))}
    out = []
    for wk in weeks:
        p = IN_DIR / f"pff_greenline_{season}_w{wk}.csv"
        if not p.exists():
            continue
        for flag in csv.DictReader(p.open(encoding="utf-8")):
            g = sched.get(flag["pff_game_id"])
            if not g:
                continue
            row = grade_one(flag, g)
            if row:
                out.append(row)
    return out


def self_check() -> None:
    flag = {"pff_game_id": "1", "season": "2026", "pff_week": "2",
            "away_abbreviation": "AAA", "home_abbreviation": "BBB",
            "market_over_under": "50.5", "greenline_total_projection": "48.0",
            "total_best_side": "under", "total_best_value": "0.045"}
    fin = {"is_over": "True", "away_score": "20", "home_score": "24"}      # 44 -> under wins
    assert grade_one(flag, fin)["result"] == "win"
    assert grade_one(flag, dict(fin, away_score="30"))["result"] == "loss"  # 54 -> over
    # An unfinished game must never grade, even when scores are present mid-play.
    assert grade_one(flag, dict(fin, is_over="False")) is None
    assert grade_one(flag, {"is_over": "True"}) is None
    # Exact landing on a whole-number line is a push, not a loss.
    push = grade_one(dict(flag, market_over_under="44"), fin)
    assert push["result"] == "push", push

    rows = [dict(result=r, side="under", line=48.0, value=0.05, projection=46.0,
                 actual_total=44.0) for r in ("win", "win", "loss")]
    t = tally(rows)
    assert (t["w"], t["l"], t["p"]) == (2, 1, 0)
    assert abs(t["units"] - (2 * PAYOUT - 1)) < 1e-9
    assert abs(t["pct"] - 66.666) < 0.01
    # Pushes return the stake: they must not dilute win% or ROI.
    t2 = tally(rows + [dict(rows[0], result="push")])
    assert t2["units"] == t["units"] and abs(t2["pct"] - t["pct"]) < 1e-9, t2
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", action="append", help="repeatable; omit with --all")
    ap.add_argument("--all", action="store_true", help="every captured week")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    if args.all:
        weeks = sorted(p.stem.rsplit("_w", 1)[1]
                       for p in IN_DIR.glob(f"pff_greenline_{args.season}_w*.csv"))
    elif args.week:
        weeks = args.week
    else:
        raise SystemExit("pass --week N (repeatable) or --all")

    rows = load(args.season, weeks)
    print(f"=== Greenline totals, {args.season} week(s) {', '.join(weeks)} ===\n")
    report(rows)

    if rows:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=GRADED_COLUMNS)
            wr.writeheader()
            wr.writerows(rows)
        print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
