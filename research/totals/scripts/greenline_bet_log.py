"""Record which Greenline flags actually got bet, week by week.

    python research/totals/scripts/greenline_bet_log.py --seed            # add new weeks
    python research/totals/scripts/greenline_bet_log.py --show 2          # review a week
    python research/totals/scripts/greenline_bet_log.py --mark 2 31104 31122 --line 54.5
    python research/totals/scripts/greenline_bet_log.py --none 2          # bet nothing
    python research/totals/scripts/greenline_bet_log.py --coverage
    python research/totals/scripts/greenline_bet_log.py --self-check

`research/totals/docs/under-selection-profile-2026-09-17.md` could not answer the
question it set out to: which flags get bet. The 2023-25 bet history has no matching
Greenline capture, and no archive of the 2023-25 flags exists. From 2026 week 2
forward both sides exist in the same week, so the answer is a logging problem rather
than a research problem -- but only if the logging starts.

The ledger is `$CFB_DATA_ROOT/ingest/pff_scoreboard/greenline_bet_log.csv`, one row
per totals flag per week, seeded from the raw captures. Seeding is idempotent: new
flags are appended, existing rows are never touched, so a re-seed after a fresh
capture cannot clobber a mark.

`bet` is deliberately three-valued -- `y`, `n`, or blank -- and blank means NOT YET
MARKED, not "no". Coverage refuses to compute on a week that still has blanks,
because defaulting them to "no" silently manufactures a 0% coverage rate, which is
exactly the number this ledger exists to measure. A week where nothing was bet gets
marked `n` across the board with `--none`, which is a real observation.
"""

from __future__ import annotations

import argparse
import csv
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from cfb_paths import INGEST  # noqa: E402

GL_DIR = INGEST / "pff_scoreboard"
LEDGER = GL_DIR / "greenline_bet_log.csv"

COLUMNS = ["season", "week", "pff_game_id", "kickoff", "away", "home", "side",
           "line", "projection", "value", "graded", "bet", "line_taken",
           "price_taken", "stake_units", "notes"]
KEY = ("season", "week", "pff_game_id")
MARKS = ("y", "n", "")


def flags(season: int | None = None) -> list[dict]:
    """Every totals flag in every capture, both sides -- the population graded 27-22."""
    out = []
    for path in sorted(GL_DIR.glob("pff_greenline_*_w*.csv")):
        for r in csv.DictReader(path.open(encoding="utf-8")):
            side = r.get("total_best_side")
            if not side:
                continue
            if season is not None and int(r.get("season") or 0) != season:
                continue
            out.append({
                "season": r.get("season") or "", "week": r.get("pff_week") or "",
                "pff_game_id": r.get("pff_game_id") or "",
                "kickoff": (r.get("kickoff_raw") or "")[:16],
                "away": r.get("away_abbreviation") or "",
                "home": r.get("home_abbreviation") or "",
                "side": side, "line": r.get("market_over_under") or "",
                "projection": r.get("greenline_total_projection") or "",
                "value": r.get("total_best_value") or "",
                "graded": "", "bet": "", "line_taken": "", "price_taken": "",
                "stake_units": "", "notes": "",
            })
    return out


def graded_results() -> dict[str, str]:
    """win/loss/push per flag, from `grade_greenline.py`'s output, when it exists."""
    path = GL_DIR / "greenline_graded.csv"
    if not path.exists():
        return {}
    return {r["pff_game_id"]: r["result"]
            for r in csv.DictReader(path.open(encoding="utf-8"))
            if r.get("side") and r.get("result")}


def load(path: Path = LEDGER) -> list[dict]:
    if not path.exists():
        return []
    return list(csv.DictReader(path.open(encoding="utf-8")))


def save(rows: list[dict], path: Path = LEDGER) -> None:
    """Atomic replace -- a half-written ledger loses marks that cannot be recovered."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with open(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows({c: r.get(c, "") for c in COLUMNS} for r in rows)
    Path(tmp).replace(path)


def seed(path: Path = LEDGER) -> tuple[int, int]:
    """Append flags not already in the ledger. Returns (added, kept)."""
    existing = load(path)
    seen = {tuple(r[k] for k in KEY) for r in existing}
    added = [f for f in flags() if tuple(f[k] for k in KEY) not in seen]

    results = graded_results()
    rows = existing + added
    for r in rows:  # grading arrives after the flag does; fill it in, never overwrite a mark
        if not r.get("graded"):
            r["graded"] = results.get(r["pff_game_id"], "")
    rows.sort(key=lambda r: (r["season"], int(r["week"] or 0), r["pff_game_id"]))
    save(rows, path)
    return len(added), len(existing)


def mark(week: int, ids: list[str], value: str = "y", path: Path = LEDGER,
         **fields: str) -> int:
    rows = load(path)
    want = set(ids)
    hit = 0
    for r in rows:
        if int(r["week"] or 0) != week:
            continue
        if want and r["pff_game_id"] not in want:
            continue
        r["bet"] = value
        for k, v in fields.items():
            if v:
                r[k] = v
        hit += 1
    save(rows, path)
    return hit


def coverage(rows: list[dict]) -> list[dict]:
    """Per week: flags, marked, bet. Refuses to rate a week that is not fully marked."""
    weeks: dict[tuple, list[dict]] = {}
    for r in rows:
        weeks.setdefault((r["season"], int(r["week"] or 0)), []).append(r)
    out = []
    for (season, week), rs in sorted(weeks.items()):
        marked = [r for r in rs if r["bet"] in ("y", "n")]
        bet = [r for r in rs if r["bet"] == "y"]
        complete = len(marked) == len(rs)
        out.append({"season": season, "week": week, "flags": len(rs),
                    "marked": len(marked), "bet": len(bet),
                    "rate": len(bet) / len(rs) if complete else None,
                    "unders": sum(1 for r in rs if r["side"] == "under"),
                    "bet_unders": sum(1 for r in bet if r["side"] == "under")})
    return out


def render_coverage(rows: list[dict]) -> str:
    out = ["| season | week | flags | unders | marked | bet | bet unders | coverage |",
           "|---:|---:|---:|---:|---:|---:|---:|---|"]
    for c in coverage(rows):
        rate = f"{c['rate']:.1%}" if c["rate"] is not None else \
            f"**unmarked ({c['flags'] - c['marked']} left)**"
        out.append(f"| {c['season']} | {c['week']} | {c['flags']} | {c['unders']} | "
                   f"{c['marked']} | {c['bet']} | {c['bet_unders']} | {rate} |")
    return "\n".join(out)


def render_week(rows: list[dict], week: int) -> str:
    rs = [r for r in rows if int(r["week"] or 0) == week]
    if not rs:
        return f"no flags logged for week {week}"
    out = [f"Week {week}: {len(rs)} totals flags "
           f"({sum(1 for r in rs if r['side'] == 'under')} under)",
           "",
           "| id | matchup | side | line | proj | value | graded | bet |",
           "|---|---|---|---:|---:|---:|---|---|"]
    for r in sorted(rs, key=lambda r: (r["side"], r["away"])):
        val = f"{float(r['value']):+.1%}" if r["value"] else ""
        out.append(f"| {r['pff_game_id']} | {r['away']} @ {r['home']} | {r['side']} | "
                   f"{r['line']} | {r['projection'][:5]} | {val} | "
                   f"{r['graded'] or '-'} | {r['bet'] or '**?**'} |")
    return "\n".join(out)


def self_check() -> None:
    d = Path(tempfile.mkdtemp())
    p = d / "log.csv"

    added, kept = seed(p)
    assert added > 50 and kept == 0, (added, kept)
    rows = load(p)
    assert all(r["bet"] == "" for r in rows), "a fresh seed must leave every mark blank"

    # blank must never be read as "not bet" -- that is the whole point of the ledger
    c = coverage(rows)
    assert all(x["rate"] is None for x in c), "unmarked weeks must refuse a coverage rate"

    # a mark survives a re-seed, and a re-seed adds nothing new
    wk = int(rows[0]["week"])
    gid = rows[0]["pff_game_id"]
    assert mark(wk, [gid], "y", p, line_taken="55.5", price_taken="-108") == 1
    again, kept2 = seed(p)
    assert again == 0, again
    after = {r["pff_game_id"]: r for r in load(p) if int(r["week"]) == wk}
    assert after[gid]["bet"] == "y" and after[gid]["line_taken"] == "55.5"

    # marking a whole week 'n' is a real observation and must yield a 0% rate
    mark(wk, [], "n", p)
    mark(wk, [gid], "y", p)
    wk_rows = [r for r in load(p) if int(r["week"]) == wk]
    cw = next(x for x in coverage(wk_rows) if x["week"] == wk)
    assert cw["marked"] == cw["flags"] and cw["rate"] == 1 / cw["flags"], cw

    # the ledger must round-trip every column it writes
    assert set(load(p)[0]) == set(COLUMNS)
    print(f"self-check OK ({added} flags seeded)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", action="store_true", help="append flags from new captures")
    ap.add_argument("--show", type=int, metavar="WEEK", help="print a week for marking")
    ap.add_argument("--mark", nargs="+", metavar=("WEEK", "ID"),
                    help="mark these flag ids in this week as bet")
    ap.add_argument("--none", type=int, metavar="WEEK",
                    help="mark every flag in this week as NOT bet")
    ap.add_argument("--line", help="line taken, with --mark")
    ap.add_argument("--price", help="price taken, with --mark")
    ap.add_argument("--units", help="stake in units, with --mark")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return
    if args.seed:
        added, kept = seed()
        print(f"seeded {LEDGER}: +{added} flags, {kept} existing rows untouched")
    if args.mark:
        week, ids = int(args.mark[0]), args.mark[1:]
        n = mark(week, ids, "y", LEDGER, line_taken=args.line or "",
                 price_taken=args.price or "", stake_units=args.units or "")
        print(f"marked {n} flag(s) bet in week {week}")
    if args.none is not None:
        n = mark(args.none, [], "n")
        print(f"marked all {n} flag(s) in week {args.none} as not bet")
    if args.show is not None:
        print(render_week(load(), args.show))
    if args.coverage:
        print(render_coverage(load()))
    if not any([args.seed, args.mark, args.none, args.show, args.coverage]):
        print(render_coverage(load()))


if __name__ == "__main__":
    main()
