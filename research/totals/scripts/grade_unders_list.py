"""Grade a captured Greenline under list at PFF's number and at the book's.

    python research/totals/scripts/grade_unders_list.py --week 3
    python research/totals/scripts/grade_unders_list.py --week 2 --week 3
    python research/totals/scripts/grade_unders_list.py --self-check

`grade_greenline.py` grades every flag in the week's capture at PFF's shown
number. That is the signal question. This is the slate question: the positive-edge
under list is the published pick set, and `match_greenline_books.py` already
repriced it at a book, so the two numbers can differ by a half point -- worth
roughly two points of win probability at these totals. Grading both side by side
is the only way to see whether the record is PFF's or the shop's.

The population is `greenline_unders_<season>_w<week>.csv`, the published list.
`greenline_unders_<season>_w<week>_draftkings.csv` is joined onto it for
`book_line` and is NOT the population: `match_greenline_books.py` only keeps games
it could match at the book, so in 2026 week 2 it holds 23 of the 36 picks. Reading
it as the pick list silently grades a subset, so a pick with no book match is
graded at PFF's number on both sides and counted in `book matched`.

Finals come through `grade_greenline`'s own score resolution -- refreshed PFF
schedule first, the warehouse for the games PFF marks `Canceled`. Every pick that
cannot be graded is printed with its reason; a grader that hides skipped picks
misleads the next pooled run. Reports record, units at -110, and the Wilson
interval, which at one week's sample will contain break-even.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grade_greenline import (IN_DIR, PAYOUT, num, pff_final, warehouse_final,  # noqa: E402
                             warehouse_finals)
from greenline_season_review import wilson  # noqa: E402


def read(name: str) -> list[dict]:
    p = IN_DIR / name
    return list(csv.DictReader(p.open(encoding="utf-8-sig"))) if p.exists() else []


def capture(season: int, week: str) -> list[dict]:
    """The published list, with `book_line` joined on where the reprice found a book."""
    picks = read(f"greenline_unders_{season}_w{week}.csv")
    if not picks:
        raise SystemExit(f"no under capture for {season} week {week} in {IN_DIR}")
    book = {r["game_id"]: r.get("book_line")
            for r in read(f"greenline_unders_{season}_w{week}_draftkings.csv")}
    return [dict(p, book_line=book.get(p["game_id"], "")) for p in picks]


def grade_at(line: float, actual: float) -> str:
    """Under side: the total must land below the line."""
    return "push" if actual == line else "win" if actual < line else "loss"


def tally(results: list[str]) -> dict:
    w, l, p = (results.count(k) for k in ("win", "loss", "push"))
    risked = w + l
    lo, hi = wilson(w, risked) if risked else (float("nan"), float("nan"))
    return {"w": w, "l": l, "p": p, "n": len(results),
            "pct": w / risked * 100 if risked else float("nan"),
            "units": w * PAYOUT - l,
            "roi": (w * PAYOUT - l) / risked * 100 if risked else float("nan"),
            "lo": lo * 100, "hi": hi * 100}


def row(label: str, t: dict) -> str:
    pushes = f" ({t['p']}p)" if t["p"] else ""
    return (f"  {label:<14} {t['w']:3d}-{t['l']:<3d}{pushes:<5} {t['pct']:5.1f}%  "
            f"{t['units']:+6.2f}u  {t['roi']:+6.1f}%   95% CI {t['lo']:4.1f}-{t['hi']:4.1f}%")


def load(season: int, weeks: list[str], skipped: list | None = None) -> list[dict]:
    sched_path = IN_DIR / f"pff_schedule_{season}.csv"
    if not sched_path.exists():
        raise SystemExit(f"{sched_path} not found -- run scripts/pull_pff_scoreboard.py")
    sched = {x["pff_game_id"]: x for x in csv.DictReader(sched_path.open(encoding="utf-8"))}
    finals = warehouse_finals(season)
    skipped = skipped if skipped is not None else []
    out = []
    for week in weeks:
        for flag in capture(season, week):
            name = f"{flag['away']} @ {flag['home']}"
            game = sched.get(flag["game_id"])
            if not game:
                skipped.append((name, "not in the refreshed PFF schedule"))
                continue
            final = pff_final(game) or warehouse_final(game, finals)
            if final is None:
                skipped.append((name, "no final -- PFF has no score and the warehouse has no match"))
                continue
            actual, line = sum(final), num(flag["line"])
            book = num(flag.get("book_line")) if flag.get("book_line") else None
            out.append({"week": week, "away": flag["away"], "home": flag["home"],
                        "line": line, "book_line": book, "actual": actual,
                        "value": num(flag.get("value")), "band": flag.get("band", ""),
                        "pff_result": grade_at(line, actual),
                        "book_result": grade_at(book if book is not None else line, actual)})
    return out


def report(rows: list[dict], skipped: list = ()) -> None:
    for name, why in skipped:
        print(f"  ungraded: {name} -- {why}")
    if skipped:
        print()
    if not rows:
        print("nothing gradeable yet -- refresh the schedule after kickoff so scores land")
        return
    matched = sum(1 for r in rows if r["book_line"] is not None)
    shopped = sum(1 for r in rows if r["book_line"] is not None and r["book_line"] != r["line"])
    print(f"{len(rows)} graded under picks; {matched} matched at the book, "
          f"{shopped} at a different number\n")
    print("  price          record       win%    units      ROI")
    print(row("PFF number", tally([r["pff_result"] for r in rows])))
    print(row("book number", tally([r["book_result"] for r in rows])))
    print("\n  game                     PFF   book  final  PFF/book")
    for r in sorted(rows, key=lambda r: (r["week"], r["away"])):
        book = f"{r['book_line']:g}" if r["book_line"] is not None else "--"
        print(f"  {r['away'] + ' @ ' + r['home']:<24} {r['line']:5g} {book:>5}  "
              f"{r['actual']:5g}  {r['pff_result']}/{r['book_result']}")


def self_check() -> None:
    assert grade_at(50.5, 44) == "win"
    assert grade_at(50.5, 54) == "loss"
    assert grade_at(50.0, 50) == "push"
    # Half a point of shop can flip a pick: 51 lands under 51.5 but over 50.5.
    assert grade_at(51.5, 51) == "win" and grade_at(50.5, 51) == "loss"
    # An unmatched book line falls back to PFF's number; it must not drop the pick.
    bare = {"week": "3", "away": "A", "home": "B", "line": 50.5, "book_line": None,
            "actual": 44.0}
    assert grade_at(bare["book_line"] or bare["line"], bare["actual"]) == "win"
    t = tally(["win", "win", "loss", "push"])
    assert (t["w"], t["l"], t["p"], t["n"]) == (2, 1, 1, 4)
    assert abs(t["units"] - (2 * PAYOUT - 1)) < 1e-9        # pushes return the stake
    assert abs(t["pct"] - 66.667) < 0.01                    # and do not dilute win%
    assert t["lo"] < 66.667 < t["hi"]
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", action="append", help="repeatable")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return
    if not args.week:
        raise SystemExit("pass --week N (repeatable)")
    print(f"=== Greenline under list, {args.season} week(s) {', '.join(args.week)} ===\n")
    skipped = []
    report(load(args.season, args.week, skipped), skipped)


if __name__ == "__main__":
    main()
