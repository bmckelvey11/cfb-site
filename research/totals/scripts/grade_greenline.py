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

Two holes in the PFF feed, both seen in 2026 week 2, are patched from elsewhere.
PFF marks games whose kickoff time was still TBD at capture (`kickoff_raw`
midnight) as `Canceled` and never posts a score for them, though they play; those
finals come from the warehouse (`core.fact_game`), joined on the calendar day and
a strong shared token in both team names -- the same rule `match_greenline_books`
uses. And a flag can carry an empty `market_over_under`; the line then comes from
the under list captured alongside it (`greenline_unders_<season>_w<week>.csv`).
Each graded row says where its score and line came from.

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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfb_paths import DB_PATH, INGEST  # noqa: E402
from match_greenline_books import slug_names, strong, toks  # noqa: E402

IN_DIR = INGEST / "pff_scoreboard"
OUT = IN_DIR / "greenline_graded.csv"
PAYOUT = 100 / 110  # -110

GRADED_COLUMNS = ["pff_game_id", "season", "pff_week", "away_abbreviation", "home_abbreviation",
                  "line", "projection", "d", "side", "value", "actual_total", "result",
                  "score_source", "line_source"]

BANDS = [("<50", lambda L: L < 50), ("50-54.5", lambda L: 50 <= L < 55),
         ("55-59.5", lambda L: 55 <= L < 60), ("60-64.5", lambda L: 60 <= L < 65),
         ("65+", lambda L: L >= 65)]

VALUE_BUCKETS = [("<2%", lambda v: v < 0.02), ("2-3%", lambda v: 0.02 <= v < 0.03),
                 ("3-4%", lambda v: 0.03 <= v < 0.04), ("4%+", lambda v: v >= 0.04)]


def num(v):
    return float(v) if v not in ("", None) else None


def pff_final(game: dict) -> tuple[float, float] | None:
    if str(game.get("is_over", "")).lower() not in ("true", "1"):
        return None
    away, home = num(game.get("away_score")), num(game.get("home_score"))
    return None if away is None or home is None else (away, home)


def warehouse_final(game: dict, finals: list[dict]) -> tuple[float, float] | None:
    """Same calendar day, strong token overlap in both names, one clear best hit."""
    away, home = slug_names(game.get("matchup_path", ""))
    a, h = toks(away), toks(home)
    day = (game.get("kickoff_raw") or "")[:10]
    if not (a and h and day):
        return None
    hits = sorted(((len(a & toks(f["away"])) + len(h & toks(f["home"])), i)
                   for i, f in enumerate(finals)
                   if f["day"] == day and strong(a & toks(f["away"])) and strong(h & toks(f["home"]))),
                  reverse=True)
    if not hits or (len(hits) > 1 and hits[0][0] == hits[1][0]):
        return None
    f = finals[hits[0][1]]
    return (f["away_points"], f["home_points"])


def grade_one(flag: dict, game: dict, finals: list[dict] = (), lines: dict | None = None) -> dict | None:
    """None when the game has not finished or no line can be found."""
    side = flag.get("total_best_side")
    line, line_source = num(flag.get("market_over_under")), "greenline"
    if line is None and lines and flag["pff_game_id"] in lines:
        line, line_source = lines[flag["pff_game_id"]], "unders_capture"
    if line is None or not side:
        return None
    final, score_source = pff_final(game), "pff"
    if final is None:
        final, score_source = warehouse_final(game, finals), "warehouse"
    if final is None:
        return None
    actual = sum(final)
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
            "actual_total": actual, "result": result,
            "score_source": score_source, "line_source": line_source}


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


def warehouse_finals(season: int) -> list[dict]:
    """Completed games with scores; `day` is the Eastern calendar date, as PFF publishes."""
    if not DB_PATH.exists():
        return []
    import duckdb  # local: the rest of the script has no warehouse dependency
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute(
        "select strftime(start_date, '%Y-%m-%d'), away_team, home_team, away_points, home_points "
        "from core.fact_game where season = ? and completed and home_points is not null", [season]).fetchall()
    con.close()
    return [{"day": d, "away": a, "home": h, "away_points": float(ap), "home_points": float(hp)}
            for d, a, h, ap, hp in rows]


def capture_lines(season: int, wk: str, in_dir: Path = IN_DIR) -> dict:
    p = in_dir / f"greenline_unders_{season}_w{wk}.csv"
    if not p.exists():
        return {}
    return {r["game_id"]: num(r["line"]) for r in csv.DictReader(p.open(encoding="utf-8"))}


def load(season: int, weeks: list[str], in_dir: Path = IN_DIR) -> list[dict]:
    sched_path = in_dir / f"pff_schedule_{season}.csv"
    if not sched_path.exists():
        raise SystemExit(f"{sched_path} not found -- run scripts/pull_pff_scoreboard.py")
    sched = {x["pff_game_id"]: x for x in csv.DictReader(sched_path.open(encoding="utf-8"))}
    finals = warehouse_finals(season)
    out = []
    for wk in weeks:
        p = in_dir / f"pff_greenline_{season}_w{wk}.csv"
        if not p.exists():
            continue
        lines = capture_lines(season, wk, in_dir)
        for flag in csv.DictReader(p.open(encoding="utf-8")):
            g = sched.get(flag["pff_game_id"])
            if not g:
                continue
            row = grade_one(flag, g, finals, lines)
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

    # PFF calls a TBD-kickoff game Canceled and never scores it; the warehouse does.
    canceled = {"is_over": "False", "status": "Canceled", "kickoff_raw": "2026-09-12T00:00:00",
                "matchup_path": "/ncaa/scores/2026/2/georgia-state-panthers_at_kennesaw-state-owls_31185"}
    finals = [{"day": "2026-09-12", "away": "Georgia State", "home": "Kennesaw State",
               "away_points": 31.0, "home_points": 17.0},
              {"day": "2026-09-12", "away": "Kansas State", "home": "Georgia", "away_points": 3.0,
               "home_points": 50.0}]
    r = grade_one(flag, canceled, finals)
    assert (r["actual_total"], r["result"], r["score_source"]) == (48.0, "win", "warehouse"), r
    # "state" alone is not a match: Kansas State @ Georgia must not grade Georgia State's flag.
    assert grade_one(flag, canceled, finals[1:]) is None
    assert grade_one(flag, canceled, []) is None
    # A flag with no line falls back to the captured under list; without one it stays ungraded.
    bare = dict(flag, market_over_under="")
    assert grade_one(bare, fin) is None
    r = grade_one(bare, fin, (), {"1": 58.5})
    assert (r["line"], r["line_source"], r["result"]) == (58.5, "unders_capture", "win"), r

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
    # Replaying a non-PFF capture (see format_exports_for_grading.py) must not read from
    # or write over the real 2026 capture set, so both ends are overridable.
    ap.add_argument("--in-dir", type=Path, default=IN_DIR,
                    help=f"directory holding the captures (default: {IN_DIR})")
    ap.add_argument("--out", type=Path, default=OUT,
                    help=f"graded output (default: {OUT})")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    if args.all:
        weeks = sorted(p.stem.rsplit("_w", 1)[1]
                       for p in args.in_dir.glob(f"pff_greenline_{args.season}_w*.csv"))
    elif args.week:
        weeks = args.week
    else:
        raise SystemExit("pass --week N (repeatable) or --all")

    rows = load(args.season, weeks, args.in_dir)
    print(f"=== Greenline totals, {args.season} week(s) {', '.join(weeks)} ===\n")
    report(rows)

    patched = [r for r in rows if r["score_source"] != "pff" or r["line_source"] != "greenline"]
    if patched:
        print(f"\n{len(patched)} flags graded from fallbacks (PFF had no final or no line):")
        for r in patched:
            print(f"  {r['away_abbreviation']}@{r['home_abbreviation']:<5} score={r['score_source']} "
                  f"line={r['line_source']} -> {r['result']}")

    if rows:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=GRADED_COLUMNS)
            wr.writeheader()
            wr.writerows(rows)
        print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
