"""Backtest the week-5 price rule on Greenline unders: does a better number than PFF's win?

    python research/totals/scripts/greenline_price_filter.py
    python research/totals/scripts/greenline_price_filter.py --out research/totals/docs/x.md
    python research/totals/scripts/greenline_price_filter.py --self-check

REGISTERED 2026-09-28, committed before any result was printed.

The rule, as used live for 2026 week 5: from PFF's positive-edge unders, take the best
DraftKings/FanDuel under (highest total, then best price) and bet it only if that total is
ABOVE PFF's displayed line AND at or above Pinnacle's fair total
(`greenline_vs_pinnacle.fair_line`). Stake size is a bankroll question and is not tested here.

Four variants, and only these -- the trial count is 4, and any other cut is a fifth trial:

  A  every positive-edge under, at the best DK/FD number
  B  best total > PFF's line
  C  B and best total >= Pinnacle fair                     <- the adopted rule
  D  best total >= Pinnacle fair, ignoring PFF's line

Decision-time prices are rebuilt from snapshots, never read from the weekly CSVs (two of
those were priced after their capture):

  DK/FD     the odds-api snapshot in `greenline_clv_all_eras.CAPTURE_SNAPSHOTS`
  Pinnacle  the last oddspapi snapshot at or before the PFF capture (CAPTURED); the first
            one after it is a sensitivity row, to show whether a stale Pinnacle drives C/D
  flags     positive-edge unders from each week's `pff_greenline` capture with
            `greenline_unders.unders()` defaults -- not the published list CSVs, because
            week 3's list had a spread filter on it

Graded at the book's total and price; finals from `greenline_graded.csv`; a push returns the
stake. CLV is the book total at capture minus the REST-backed median close
(`greenline_clv_all_eras`, span gate): positive means the market moved toward the under.

Expected answer, stated before running: ~25 selected bets over weeks 2-4 put the win-rate MDE
near 75%, so the record cannot confirm or kill the rule. The informative contrasts are CLV
and selected vs rejected flags. Weeks 2-4 are a discovery-period look -- the rule was written
on week 5, after the week 2-4 under list graded near break-even at PFF's number, which is its
premise. Prospective evidence is the bet ledger from week 5 on, graded at the line taken.

The Pinnacle leg (D) sits beside a closed family (greenline-findings row 10, Pinnacle shade:
does Pinnacle's position RANK PFF's picks?). This asks a different question -- is the retail
book's price off the sharp market -- and is logged as a reopening, not a continuation.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfb_paths import INGEST  # noqa: E402
from greenline_bet_stats import bootstrap  # noqa: E402
from greenline_clv import load_flags  # noqa: E402
from greenline_clv_all_eras import CAPTURE_SNAPSHOTS, Z95, book_closes, consensus, stats  # noqa: E402
from greenline_season_review import mde, wilson  # noqa: E402
from greenline_unders import unders  # noqa: E402
from greenline_vs_pinnacle import PIN_DIR, fair_line, pinnacle_totals  # noqa: E402
from match_greenline_books import (OA_DIR, break_even, is_placeholder, latest_snapshot,  # noqa: E402
                                   match, sigma, slug_names)

GL_DIR = INGEST / "pff_scoreboard"
BOOKS = ("DraftKings", "FanDuel")
ET = timezone(timedelta(hours=-4))
# PFF capture per week: the dump stamp (weeks 3-4), or the capture CSV's write time (week 2 kept no dump)
CAPTURED = {"2": "20260909T231100Z", "3": "20260916T182615Z", "4": "20260923T194955Z"}
VARIANTS = {"A": "all positive-edge unders", "B": "book total > PFF line",
            "C": "B and >= Pinnacle fair (adopted)", "D": ">= Pinnacle fair only"}


def decimal(odds: int) -> float:
    return 1 + (100 / -odds if odds < 0 else odds / 100)


def best_book(totals: dict) -> tuple[str, float, int] | None:
    """Highest under total across DK/FD, then the better price -- the live week-5 choice."""
    have = [(b, *totals[b]) for b in BOOKS if b in totals]
    return max(have, key=lambda t: (t[1], decimal(t[2]))) if have else None


def passes(pff_line: float, book_line: float, pin_fair: float | None) -> dict[str, bool]:
    """The four registered variants. No Pinnacle price means C and D cannot pass, as live."""
    above_pff = book_line > pff_line
    at_pin = pin_fair is not None and book_line >= pin_fair
    return {"A": True, "B": above_pff, "C": above_pff and at_pin, "D": at_pin}


def pin_snapshot(week: str, after: bool = False) -> Path:
    cap = CAPTURED[week]
    snaps = sorted(PIN_DIR.glob("oddspapi_ncaa_pinnacle_*.json"), key=lambda p: p.stem.rsplit("_", 1)[1])
    if after:
        return next(p for p in snaps if p.stem.rsplit("_", 1)[1] > cap)
    return [p for p in snaps if p.stem.rsplit("_", 1)[1] <= cap][-1]


def grade(actual: float, line: float) -> str:
    return "push" if actual == line else ("win" if actual < line else "loss")


def build(pin_after: bool = False) -> tuple[list[dict], dict]:
    sched = {s["pff_game_id"]: s for s in csv.DictReader((GL_DIR / "pff_schedule_2026.csv").open(encoding="utf-8"))}
    finals = {(r["pff_week"], r["pff_game_id"]): float(r["actual_total"])
              for r in csv.DictReader((GL_DIR / "greenline_graded.csv").open(encoding="utf-8")) if r["actual_total"]}
    teams = {f["pff_game_id"]: f["teams"] for f in load_flags()}
    _, by_teams = book_closes((2026,))
    rows, cover = [], {}
    odds_snaps = sorted(OA_DIR.glob("odds_americanfootball_ncaaf_*.json"), key=lambda p: p.stem.rsplit("_", 1)[1])
    for wk, snap in CAPTURE_SNAPSHOTS.items():
        oa = latest_snapshot(OA_DIR / snap)[0]
        # the odds snapshot precedes PFF's capture by up to 3h; the first one after it shows
        # whether the better number was still there when the flag could be acted on
        oa_after = latest_snapshot(next(p for p in odds_snaps if p.stem.rsplit("_", 1)[1] > CAPTURED[wk]))[0]
        pin_path = pin_snapshot(wk, pin_after)
        pin = pinnacle_totals(pin_path)[0]
        flags = list(csv.DictReader((GL_DIR / f"pff_greenline_2026_w{wk}.csv").open(encoding="utf-8")))
        c = cover.setdefault(wk, Counter(odds=snap, pinnacle_file=pin_path.name))
        for u in unders(flags):
            c["unders"] += 1
            g = sched.get(u["game_id"]) or {}
            away, home = slug_names(g.get("matchup_path", ""))
            kick = datetime.fromisoformat(u["kickoff"]).replace(tzinfo=ET).astimezone(timezone.utc)
            ph = is_placeholder(u["kickoff"])
            totals = (match(kick, away, home, oa, ph) or {}).get("totals", {})
            for b in BOOKS:
                c[b] += b in totals
            bb = best_book(totals)
            pe = match(kick, away, home, pin, ph)
            c["pinnacle"] += pe is not None
            if bb is None:
                continue
            actual = finals.get((wk, u["game_id"]))
            if actual is None:
                c["ungraded"] += 1
                continue
            book, bl, bo = bb
            pf = fair_line(pe["line"], pe["over"], pe["under"], sigma(pe["line"])) if pe else None
            later = best_book((match(kick, away, home, oa_after, ph) or {}).get("totals", {}))
            res = grade(actual, bl)
            close, _ = consensus(by_teams.get((2026, teams[u["game_id"]]))) if u["game_id"] in teams else (None, "")
            rows.append({"week": wk, "game_id": u["game_id"], "game": f"{u['away']} @ {u['home']}",
                         "date": u["kickoff"][:10], "pff_line": u["line"], "book": book, "book_line": bl,
                         "odds": bo, "pin_fair": pf, "actual": actual, "result": res,
                         "net": decimal(bo) - 1 if res == "win" else (-1.0 if res == "loss" else 0.0),
                         "clv": bl - close if close is not None else None,
                         "still_up": later is not None and later[1] > u["line"], **passes(u["line"], bl, pf)})
    return rows, cover


def summary(label: str, rs: list[dict]) -> str:
    w = sum(r["result"] == "win" for r in rs)
    l = sum(r["result"] == "loss" for r in rs)
    p = len(rs) - w - l
    if w + l < 2:
        return f"| {label} | {len(rs)} | {w}-{l}-{p} | -- | -- | -- | -- | -- | -- | -- |"
    lo, hi = wilson(w, w + l)
    be = sum(break_even(r["odds"]) for r in rs) / len(rs)
    units = sum(r["net"] for r in rs)
    _, _, rlo, rhi = bootstrap(rs)
    cl = [r for r in rs if r["clv"] is not None]
    s = stats([r["clv"] for r in cl], [r["date"] for r in cl]) if len(cl) > 1 else None
    clv = (f"{s['mean']:+.2f} ± {Z95 * s['se']:.2f} (med {s['median']:+.1f}, {s['beat']}-{s['lost']}, n={s['n']})"
           if s else "--")
    return (f"| {label} | {len(rs)} | {w}-{l}-{p} | {w / (w + l) * 100:.1f}% | {lo * 100:.0f}–{hi * 100:.0f}% | "
            f"{be * 100:.1f}% | {mde(w + l, be) * 100:.0f}% | {units:+.2f}u | "
            f"{units / len(rs) * 100:+.1f}% ({rlo * 100:+.0f} to {rhi * 100:+.0f}) | {clv} |")


HEAD = ("| split | bets | W-L-P | win% | Wilson 95% | break-even | MDE | units | ROI (95% bootstrap) | CLV pts |\n"
        "| --- | ---: | --- | ---: | --- | ---: | ---: | ---: | --- | --- |")


def report(rows: list[dict], cover: dict, after: list[dict]) -> str:
    L = ["## Coverage (decision-time snapshots)", "",
         "| week | odds-api | Pinnacle | unders | DK | FD | Pinnacle matched | ungraded |",
         "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for wk, c in cover.items():
        L.append(f"| {wk} | {c['odds']} | {c['pinnacle_file']} | {c['unders']} | {c['DraftKings']} | "
                 f"{c['FanDuel']} | {c['pinnacle']} | {c['ungraded']} |")
    L += ["", "## Variants, weeks 2-4 pooled", "", HEAD]
    for k, name in VARIANTS.items():
        L.append(summary(f"{k}: {name}", [r for r in rows if r[k]]))
    L.append(summary("rejected by C (A minus C)", [r for r in rows if not r["C"]]))
    L += ["", "## The adopted rule (C) by week", "", HEAD]
    for wk in CAPTURE_SNAPSHOTS:
        L.append(summary(f"C, week {wk}", [r for r in rows if r["C"] and r["week"] == wk]))
        L.append(summary(f"A, week {wk}", [r for r in rows if r["week"] == wk]))
    L += ["", "## Sensitivity: first Pinnacle snapshot after capture", "", HEAD]
    for k in ("C", "D"):
        L.append(summary(f"{k} (Pinnacle after)", [r for r in after if r[k]]))
    L += ["", "## Sensitivity: was the better number still there after PFF's capture?", "",
          "Added 2026-09-28 after the first run, as a decision-time check, not a variant: the odds",
          "snapshot precedes the capture by up to 3h, so a gap to PFF's line can be the market",
          "falling in between. Graded at the pre-capture number either way.", "", HEAD]
    L.append(summary("C, still above PFF's line in the next odds snapshot", [r for r in rows if r["C"] and r["still_up"]]))
    L.append(summary("C, gone or unmatched by the next snapshot", [r for r in rows if r["C"] and not r["still_up"]]))
    L += ["", "## Selected bets (C)", "",
          "| week | game | PFF | book | total | odds | Pinnacle fair | final | result | CLV | still up |",
          "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: | --- |"]
    for r in sorted((r for r in rows if r["C"]), key=lambda r: (r["week"], r["date"])):
        L.append(f"| {r['week']} | {r['game']} | {r['pff_line']:g} | {r['book']} | {r['book_line']:g} | "
                 f"{r['odds']:+d} | {r['pin_fair']:.2f} | {r['actual']:g} | {r['result']} | "
                 + (f"{r['clv']:+.1f}" if r["clv"] is not None else "--")
                 + f" | {'yes' if r['still_up'] else 'no'} |")
    return "\n".join(L) + "\n"


def self_check() -> None:
    assert abs(decimal(-110) - 1.9091) < 1e-3 and decimal(150) == 2.5
    # line first, then price: a half point beats better juice
    assert best_book({"DraftKings": (49.5, -120), "FanDuel": (49.0, -102)})[0] == "DraftKings"
    assert best_book({"DraftKings": (49.5, -115), "FanDuel": (49.5, -110)})[0] == "FanDuel"
    assert best_book({"BetMGM": (60.0, -110)}) is None
    assert passes(48.5, 49.5, 48.95) == {"A": True, "B": True, "C": True, "D": True}
    assert passes(58.5, 59.5, 59.93) == {"A": True, "B": True, "C": False, "D": False}  # LOU @ NCST, week 5
    assert passes(50.5, 50.5, 49.0) == {"A": True, "B": False, "C": False, "D": True}
    assert passes(50.5, 51.5, None)["C"] is False
    assert grade(49.0, 49.5) == "win" and grade(50.0, 49.5) == "loss" and grade(49.0, 49.0) == "push"
    for wk, cap in CAPTURED.items():
        before, after = pin_snapshot(wk), pin_snapshot(wk, after=True)
        assert before.stem.rsplit("_", 1)[1] <= cap < after.stem.rsplit("_", 1)[1], (wk, before, after)
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, help="also write the report here")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return
    rows, cover = build()
    after, _ = build(pin_after=True)
    md = report(rows, cover, after)
    print(md)
    if args.out:
        args.out.write_text(md, encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
