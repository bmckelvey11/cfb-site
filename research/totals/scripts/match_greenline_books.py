"""Match Greenline under flags to the number a book is actually offering.

    python research/totals/scripts/match_greenline_books.py --week 2
    python research/totals/scripts/match_greenline_books.py --week 2 --book FanDuel
    python research/totals/scripts/match_greenline_books.py --self-check

PFF shows its own line, which is not the one you bet. This joins each flagged
under to the latest the-odds-api snapshot (`data/ingest/oddsapi/`, pulled every
six hours by `CFB-Odds-Snapshot`) and reprices the edge at the book's number.

REPRICING IS THE POINT. An edge of 5.4% at 44.5 is not an edge of 5.4% at 43.5:
half a point of total is worth roughly two points of win probability at these
sigmas, so a book hanging a lower number can erase most of the flag. The
repriced column uses the pricing law recovered in `greenline_pricing.py` --
p_under = Phi((line - projection) / sigma), sigma = -4.60 + 0.2782 * line --
which reproduces PFF's own probabilities on the under side and is what lets a
PFF projection be evaluated against a line PFF never quoted.

That law was fitted on one week of under-side games and carries a residual of
about 0.9 points of sigma, so treat a repriced edge as a ranking, not a
measurement. Where the book's number equals PFF's, the repriced figure should
land within a few tenths of a percent of PFF's own -- the report prints that
agreement so a bad fit is visible rather than silent.

The two feeds share no game id and spell schools differently, so the join is
kickoff plus a shared token in BOTH team names, the same rule `join_oa` in
`models/over_zero/scripts/best_line_slate.py` uses. Ties are dropped rather
than guessed. PFF publishes kickoff in Eastern; the-odds-api publishes UTC.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import NormalDist

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from cfb_paths import INGEST  # noqa: E402

N = NormalDist()
GL_DIR = INGEST / "pff_scoreboard"
OA_DIR = INGEST / "oddsapi"
BREAK_EVEN_110 = 110 / 210
SIGMA_A, SIGMA_B = -4.60, 0.2782      # from greenline_pricing.py, under side
KICK_TOLERANCE = timedelta(minutes=1)

OA_BOOKS = {"draftkings": "DraftKings", "fanduel": "FanDuel", "betrivers": "BetRivers",
            "betmgm": "BetMGM", "bovada": "Bovada", "betus": "BetUS",
            "mybookieag": "MyBookie", "lowvig": "LowVig", "betonlineag": "BetOnline"}


def toks(name: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9 ]", " ", str(name).lower()).split())


def sigma(line: float) -> float:
    return SIGMA_A + SIGMA_B * line


def p_under(line: float, projection: float) -> float:
    """PFF's own under probability, evaluated at any line."""
    return N.cdf((line - projection) / sigma(line))


def edge_at(line: float, projection: float, odds: int) -> float:
    """Win probability less the break-even implied by the price actually offered."""
    return p_under(line, projection) - break_even(odds)


def break_even(odds: int) -> float:
    """American odds to the probability a bet must clear to be flat."""
    return (-odds) / (-odds + 100) if odds < 0 else 100 / (odds + 100)


def latest_snapshot() -> tuple[list[dict], str, Path]:
    snaps = sorted(OA_DIR.glob("odds_americanfootball_ncaaf_*.json"))
    if not snaps:
        raise SystemExit(f"no snapshot in {OA_DIR} -- run scripts/pull_odds.py")
    path = snaps[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for e in payload["events"]:
        ko = datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00"))
        totals = {}
        for b in e.get("bookmakers", []):
            name = OA_BOOKS.get(b.get("key"))
            if name is None:
                continue
            for m in b.get("markets", []):
                if m.get("key") != "totals":
                    continue
                for o in m.get("outcomes", []):
                    if o.get("name") == "Over" and o.get("point") is not None:
                        totals[name] = (float(o["point"]), int(o["price"]))
        rows.append({"kick": ko, "home": toks(e["home_team"]), "away": toks(e["away_team"]),
                     "home_name": e["home_team"], "away_name": e["away_team"], "totals": totals})
    return rows, payload.get("pulled_at", path.stem), path


def slug_names(matchup_path: str) -> tuple[str, str]:
    """'/ncaa/scores/2026/2/rutgers-scarlet-knights_at_boston-college-eagles_31104'."""
    tail = (matchup_path or "").rsplit("/", 1)[-1]
    tail = re.sub(r"_\d+$", "", tail)
    if "_at_" not in tail:
        return "", ""
    away, home = tail.split("_at_", 1)
    return away.replace("-", " "), home.replace("-", " ")


def match(flag_kick: datetime, away: str, home: str, oa: list[dict]) -> dict | None:
    a, h = toks(away), toks(home)
    if not (a and h):
        return None
    hits = sorted(((len(h & e["home"]) + len(a & e["away"]), i)
                   for i, e in enumerate(oa)
                   if abs(e["kick"] - flag_kick) <= KICK_TOLERANCE
                   and (h & e["home"]) and (a & e["away"])), reverse=True)
    if not hits or (len(hits) > 1 and hits[0][0] == hits[1][0]):
        return None
    return oa[hits[0][1]]


def self_check() -> None:
    assert abs(break_even(-110) - BREAK_EVEN_110) < 1e-9
    assert abs(break_even(-105) - 105 / 205) < 1e-9
    assert abs(break_even(100) - 0.5) < 1e-9
    assert abs(break_even(120) - 100 / 220) < 1e-9

    # A lower number is worse for an under, and the loss is material.
    hi, lo = edge_at(44.5, 42.9, -110), edge_at(43.5, 42.9, -110)
    assert hi > lo, (hi, lo)
    assert 0.015 < hi - lo < 0.06, hi - lo          # ~half a point is worth a few points of p

    # The law must reproduce PFF's own published probability at PFF's own line.
    assert abs(p_under(44.5, 42.9) - 0.5774) < 0.02, p_under(44.5, 42.9)
    assert abs(p_under(48.5, 46.8) - 0.5742) < 0.02, p_under(48.5, 46.8)

    # Worse juice eats edge even at an identical number.
    assert edge_at(48.5, 46.8, -120) < edge_at(48.5, 46.8, -110)

    assert slug_names("/ncaa/scores/2026/2/rutgers-scarlet-knights_at_boston-college-eagles_31104") \
        == ("rutgers scarlet knights", "boston college eagles")
    assert slug_names("garbage") == ("", "")

    ko = datetime(2026, 9, 12, 23, 30, tzinfo=timezone.utc)
    oa = [{"kick": ko, "home": toks("Boston College Eagles"), "away": toks("Rutgers Scarlet Knights"),
           "home_name": "x", "away_name": "y", "totals": {"DraftKings": (54.5, -110)}}]
    assert match(ko, "rutgers scarlet knights", "boston college eagles", oa) is not None
    # A game an hour away is a different game, not a fuzzy match.
    assert match(ko + timedelta(hours=1), "rutgers scarlet knights", "boston college eagles", oa) is None
    # Two equally good candidates are dropped, never guessed between.
    assert match(ko, "rutgers scarlet knights", "boston college eagles", oa + oa) is None
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", default="2")
    ap.add_argument("--book", default="DraftKings")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    gl_path = GL_DIR / f"greenline_unders_{args.season}_w{args.week}.csv"
    if not gl_path.exists():
        raise SystemExit(f"{gl_path} not found")
    flags = list(csv.DictReader(gl_path.open(encoding="utf-8")))

    sched_path = GL_DIR / f"pff_schedule_{args.season}.csv"
    sched = {x["pff_game_id"]: x for x in csv.DictReader(sched_path.open(encoding="utf-8"))}

    oa, pulled_at, snap = latest_snapshot()
    print(f"=== Greenline unders vs {args.book}, {args.season} week {args.week} ===")
    print(f"snapshot {snap.name}  (pulled {pulled_at})\n")

    out, unmatched, nobook = [], [], []
    for fl in flags:
        g = sched.get(fl["game_id"])
        away, home = slug_names(g.get("matchup_path", "")) if g else ("", "")
        kick = datetime.fromisoformat(fl["kickoff"]).replace(tzinfo=timezone(timedelta(hours=-4)))
        e = match(kick.astimezone(timezone.utc), away, home, oa)
        if e is None:
            unmatched.append(fl)
            continue
        if args.book not in e["totals"]:
            nobook.append(fl)
            continue
        bline, bodds = e["totals"][args.book]
        proj = float(fl["projection"])
        out.append({**fl, "book_line": bline, "book_odds": bodds,
                    "book_edge": edge_at(bline, proj, bodds),
                    "pff_edge": float(fl["value"]),
                    "diff": bline - float(fl["line"])})

    out.sort(key=lambda r: -r["book_edge"])
    print(f"{'game':<14} {'PFF':>6} {'DK':>6} {'move':>5} {'odds':>6} {'PFF ed':>7} {'DK ed':>7}  band")
    for r in out:
        print(f"{r['away']+' @ '+r['home']:<14} {float(r['line']):6.1f} {r['book_line']:6.1f} "
              f"{r['diff']:+5.1f} {r['book_odds']:+6d} {r['pff_edge']*100:+6.2f}% "
              f"{r['book_edge']*100:+6.2f}%  {r['band']}")

    live = [r for r in out if r["book_edge"] > 0]
    print(f"\n{len(out)} matched at {args.book}; {len(live)} still positive after repricing")
    if unmatched:
        print(f"{len(unmatched)} not found in the snapshot: "
              + ", ".join(f"{r['away']}@{r['home']}" for r in unmatched))
    if nobook:
        print(f"{len(nobook)} matched but {args.book} posts no total: "
              + ", ".join(f"{r['away']}@{r['home']}" for r in nobook))

    same = [r for r in out if abs(r["diff"]) < 0.01]
    if same:
        err = [abs(r["book_edge"] - r["pff_edge"]) for r in same]
        print(f"\nsanity: {len(same)} games where {args.book} matches PFF's number exactly; "
              f"repriced edge differs from PFF's by {sum(err)/len(err)*100:.2f}% on average")
        print("(that gap is the pricing law's error, not a real disagreement)")

    if out:
        dest = GL_DIR / f"greenline_unders_{args.season}_w{args.week}_{args.book.lower()}.csv"
        with dest.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)
        print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
