"""Record which Greenline flags actually got bet, week by week.

    python research/totals/scripts/greenline_bet_log.py --seed            # add new weeks
    python research/totals/scripts/greenline_bet_log.py --import-book      # from history.csv
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

`--import-book` marks the ledger from a fresh book export
(`data/ingest/bet_history/history.csv`). Both sides resolve to CFBD team ids before
matching -- PFF through `pff_schedule` plus `pff_franchise.cfbd_team_id`, the book
through `core.dim_team.abbreviation` -- because the two vocabularies disagree on 32 of
137 teams (PFF writes MIZZ and CONN where the book writes MIZ and UCONN), so matching
the raw strings would silently drop those games as "not bet". Flags on a day the
export covers but which carry no matching bet are marked `n`; that is what makes the
import worth having, since it converts a whole week from blank to marked in one pass
instead of recording only the `y` rows and leaving coverage uncomputable. Days the
export does not reach stay blank, so an export that stops mid-season cannot mark the
rest of the season unbet.

`bet` is deliberately three-valued -- `y`, `n`, or blank -- and blank means NOT YET
MARKED, not "no". Coverage refuses to compute on a week that still has blanks,
because defaulting them to "no" silently manufactures a 0% coverage rate, which is
exactly the number this ledger exists to measure. A week where nothing was bet gets
marked `n` across the board with `--none`, which is a real observation.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
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


# The book abbreviations CFBD spells differently, shared with
# `under_selection_profile.py`. PFF's own spellings never enter this map -- they go
# through pff_franchise.cfbd_team_id instead.
BOOK_ALIAS = {"ARI": "ARIZ", "NCST": "NCSU", "WF": "WAKE", "BAMA": "ALA",
              "AFA": "AF", "UCONN": "CONN", "BOISE": "BOIS", "CHA": "CLT",
              "CC": "CCU", "UMD": "MD", "RUT": "RUTG", "NW": "NU",
              "JVST": "JXST"}


def _book_abbrev_to_cfbd() -> dict[str, str]:
    """book abbreviation -> CFBD team_id, via core.dim_team."""
    import duckdb

    from cfb_paths import DB_PATH

    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute("select abbreviation, team_id from core.dim_team "
                       "where abbreviation is not null").fetchall()
    con.close()
    return {a: str(t) for a, t in rows}


def _flag_cfbd_ids() -> dict[str, frozenset]:
    """pff_game_id -> the game's two CFBD team ids.

    PFF captures carry only their own abbreviations, so the route is
    schedule -> franchise_id -> pff_franchise.cfbd_team_id.
    """
    franchise = {}
    fpath = Path(str(INGEST).replace("ingest", "processed")) / "pff" / "pff_franchise.csv"
    if not fpath.exists():
        return {}
    for r in csv.DictReader(fpath.open(encoding="utf-8")):
        if r.get("cfbd_team_id"):
            franchise[r["franchise_id"]] = r["cfbd_team_id"]

    out = {}
    for path in sorted(GL_DIR.glob("pff_schedule_*.csv")):
        for r in csv.DictReader(path.open(encoding="utf-8")):
            a, h = franchise.get(r.get("away_franchise_id", "")), \
                franchise.get(r.get("home_franchise_id", ""))
            if a and h:
                out[r["pff_game_id"]] = frozenset((a, h))
    return out


def book_totals(path: Path | None = None) -> list[dict]:
    """Full-game total bets from the book export, resolved to CFBD team ids.

    Reuses `cfb_system_maker.betlog`'s parser, which already handles the export's
    stray data-uri line and its in-scope filtering.
    """
    from cfb_system_maker.betlog import parse_betlog_csv

    src = path or (INGEST / "bet_history" / "history.csv")
    if not src.exists():
        return []
    ab = _book_abbrev_to_cfbd()
    out = []
    for r in parse_betlog_csv(src).in_scope:
        if r.bet_type not in ("over", "under"):
            continue
        away, home = (x.strip().upper() for x in r.game.split("@"))
        ids = {ab.get(BOOK_ALIAS.get(t, t)) for t in (away, home)}
        out.append({"date": r.start_time[:10], "away": away, "home": home,
                    "teams": frozenset(ids) if None not in ids else None,
                    "side": r.bet_type, "line": r.line_taken, "odds": r.odds,
                    "units": r.units_wagered, "game": r.game})
    return out


def import_book(path: Path | None = None, ledger: Path = LEDGER) -> dict:
    """Mark the ledger from a book export. Returns a summary dict.

    A flag is marked `y` when the export holds a full-game total on the same two CFBD
    teams within a day of the flag's kickoff. Flags whose kickoff day the export covers
    but which have no such bet are marked `n`; flags outside the export's date span keep
    whatever they had, because "the export does not reach this week" is not evidence
    that nothing was bet.
    """
    bets = book_totals(path)
    rows = load(ledger)
    if not bets or not rows:
        return {"bets": len(bets), "marked_y": 0, "marked_n": 0, "unmatched": [],
                "unresolved": 0}

    flag_ids = _flag_cfbd_ids()
    covered = set()
    for b in bets:  # a bet a day either side still counts as covering that day
        d0 = dt.date.fromisoformat(b["date"])
        covered |= {(d0 + dt.timedelta(days=o)).isoformat() for o in (-1, 0, 1)}

    index: dict[tuple, dict] = {}
    for b in bets:
        if b["teams"] is None:
            continue
        d0 = dt.date.fromisoformat(b["date"])
        for off in (-1, 0, 1):
            index.setdefault(((d0 + dt.timedelta(days=off)).isoformat(), b["teams"]), b)

    hit_y, hit_n, used = 0, 0, set()
    for r in rows:
        day = (r.get("kickoff") or "")[:10]
        if not day or day not in covered:
            continue
        teams = flag_ids.get(r["pff_game_id"])
        b = index.get((day, teams)) if teams else None
        if b is None:
            if r["bet"] == "":
                r["bet"] = "n"
                hit_n += 1
            continue
        r["bet"] = "y"
        r["line_taken"] = str(b["line"])
        r["price_taken"] = str(b["odds"])
        r["stake_units"] = str(b["units"])
        if b["side"] != r["side"]:
            r["notes"] = f"book took the {b['side']}, PFF flagged the {r['side']}"
        used.add(id(b))
        hit_y += 1

    save(rows, ledger)
    # "Unmatched" should mean PFF had a board that day and did not flag the game --
    # not that the bet predates any capture, which is most of a 2023-25 export.
    flag_days = {(r.get("kickoff") or "")[:10] for r in rows}
    return {"bets": len(bets), "marked_y": hit_y, "marked_n": hit_n,
            "unresolved": sum(1 for b in bets if b["teams"] is None),
            "no_capture": sum(1 for b in bets if b["date"] not in flag_days),
            "unmatched": [b["game"] + " " + b["date"] for b in bets
                          if id(b) not in used and b["teams"] is not None
                          and b["date"] in flag_days]}


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

    # --- the importer ---------------------------------------------------------
    p2 = d / "log2.csv"
    seed(p2)
    rows2 = load(p2)
    flag_ids = _flag_cfbd_ids()
    assert len(flag_ids) > 50, "PFF flags must resolve to CFBD ids"

    # Write the fixture in the BOOK's vocabulary, reached from the CFBD ids rather
    # than from PFF's spelling -- a fixture that reused PFF's abbreviations would
    # pass even if the id join were broken, which is the bug this guards.
    ab = _book_abbrev_to_cfbd()
    by_id = {v: k for k, v in ab.items()}
    target = next(r for r in rows2
                  if r["pff_game_id"] in flag_ids
                  and all(i in by_id for i in flag_ids[r["pff_game_id"]]))
    a_id, h_id = sorted(flag_ids[target["pff_game_id"]])
    day = target["kickoff"][:10]
    book = d / "book.csv"
    book.write_text(
        "data:text/csv;charset=utf-8,\n"
        "League,Start Time,Game,Pick Desc,Type,Period,Odds,Odds/Spread/Total,Result,"
        "Units Wagered,Units Net,Money Wagered,Money Net,Tag\n"
        f"ncaaf,{day}T18:30:00.000Z,{by_id[a_id]} @ {by_id[h_id]},x,"
        f"{target['side']},game,-108,{target['line'] or 50.5},win,1,0.93,1000,930,\n",
        encoding="utf-8")
    r = import_book(book, p2)
    assert r["marked_y"] == 1, r
    after2 = {x["pff_game_id"]: x for x in load(p2)}
    assert after2[target["pff_game_id"]]["bet"] == "y"
    assert after2[target["pff_game_id"]]["price_taken"] == "-108"

    # every other flag on a day the export covers is marked n, and a week the export
    # never reaches must stay blank -- silence in the export is not evidence of no bet
    same_day = [x for x in load(p2) if x["kickoff"][:10] == day]
    assert all(x["bet"] in ("y", "n") for x in same_day), "covered day left blank"
    far = [x for x in load(p2) if x["kickoff"][:10] not in
           {day, *( (dt.date.fromisoformat(day) + dt.timedelta(days=o)).isoformat()
                    for o in (-1, 1))}]
    assert far and all(x["bet"] == "" for x in far), "uncovered day was marked"

    # re-importing is idempotent
    before = load(p2)
    import_book(book, p2)
    assert load(p2) == before

    print(f"self-check OK ({added} flags seeded, importer marks and stays in its window)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", action="store_true", help="append flags from new captures")
    ap.add_argument("--import-book", nargs="?", const="", metavar="CSV",
                    help="mark the ledger from a book export (default: the standard path)")
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
    if args.import_book is not None:
        src = Path(args.import_book) if args.import_book else None
        r = import_book(src)
        print(f"book export: {r['bets']} full-game totals -> "
              f"{r['marked_y']} flags marked bet, {r['marked_n']} marked not bet")
        if r["no_capture"]:
            print(f"  {r['no_capture']} bets fall on days with no Greenline capture "
                  f"(nothing to mark)")
        if r["unresolved"]:
            print(f"  {r['unresolved']} bets had an unresolvable team abbreviation "
                  f"-- add it to BOOK_ALIAS")
        if r["unmatched"]:
            print(f"  {len(r['unmatched'])} bets on captured days that PFF did not "
                  f"flag: {', '.join(r['unmatched'][:8])}"
                  + (" ..." if len(r["unmatched"]) > 8 else ""))
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
    if not any([args.seed, args.mark, args.none, args.show, args.coverage,
                args.import_book is not None]):
        print(render_coverage(load()))


if __name__ == "__main__":
    main()
