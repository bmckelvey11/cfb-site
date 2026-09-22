"""Reshape the 2022-23 Greenline export picks into the weekly capture format.

`grade_greenline.py` grades a PFF capture (`pff_greenline_<season>_w<week>.csv` plus
`pff_schedule_<season>.csv`). The export slates predate that pipeline and carry a different
shape, so their picks have only ever been gradeable by the bespoke
`grade_export_picks.py`. This writes them in the capture format so the standard grader can
read them, which makes the two paths cross-checkable against each other.

SCOPE: `grade_greenline.py` is a TOTALS grader, so only the 91 total picks come through
here. The 62 moneyline and 67 spread picks have no home in that format and stay with
`grade_export_picks.py`.

Three deliberate choices, because each one could otherwise mislead:

  WRITTEN TO A SEPARATE DIRECTORY (`<ingest>/pff_scoreboard/export_replay/`), never beside
  the real captures. These files are synthesized from a vendor export, not pulled from
  PFF, and a file named `pff_greenline_2022_w5.csv` sitting next to the genuine 2026
  captures would eventually be read as one.

  GRADED OUTPUT IS SEPARATE TOO. `greenline_graded.csv` is the 2026 pooled record, graded
  at a real book number with a known price. These picks have no price at all, so they are
  not poolable with it -- see greenline-export-picks-graded-2026-09-21.md.

  NO FINAL SCORES ARE WRITTEN INTO THE SCHEDULE. `is_over` is left empty so `pff_final()`
  declines and `grade_greenline.py` falls through to its documented warehouse lookup. CFBD
  stays the single source of truth for results rather than this script copying them in.

`pff_game_id` in these files is the CFBD `game_id`. The exports have no PFF id, and the
column is a key, not a claim about provenance.

Usage:
    python research/totals/scripts/format_exports_for_grading.py
    python research/totals/scripts/format_exports_for_grading.py --self-check
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from cfb_paths import INGEST  # noqa: E402

IN_DIR = INGEST / "pff_scoreboard"
ARCHIVE = IN_DIR / "greenline_history_archive.csv"
TEAM_MAP = IN_DIR / "greenline_history_archive_team_map.csv"
OUT_DIR = IN_DIR / "export_replay"

CAPTURE_COLUMNS = [
    "pff_game_id", "season", "pff_week", "kickoff_raw", "away_abbreviation",
    "home_abbreviation", "market_spread", "greenline_spread", "spread_best_side",
    "spread_best_value", "spread_value_label", "spread_value_level",
    "spread_away_cover_probability", "spread_home_cover_probability",
    "market_over_under", "greenline_total_projection", "total_best_side",
    "total_best_value", "total_value_label", "total_value_level",
    "over_cover_probability", "under_cover_probability", "market_money_line_away",
    "market_money_line_home", "greenline_money_line_away", "greenline_money_line_home",
    "money_line_best_side", "money_line_best_value", "money_line_value_label",
    "money_line_value_level", "money_line_away_cover_probability",
    "money_line_home_cover_probability",
]

SCHEDULE_COLUMNS = [
    "pff_game_id", "external_game_id", "season", "pff_week", "kickoff_raw", "status",
    "is_over", "channel", "away_franchise_id", "away_abbreviation", "away_record",
    "away_ats_record", "away_score", "home_franchise_id", "home_abbreviation",
    "home_record", "home_ats_record", "home_score", "opening_point_spread",
    "point_spread", "opening_over_under", "over_under", "opening_away_money_line",
    "opening_home_money_line", "away_team_money_line", "home_team_money_line",
    "betting_value_count", "matchup_path",
]


def slug(name: str) -> str:
    """'Arkansas State' -> 'arkansas-state', matching the shape slug_names() unpacks."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", str(name).lower())).strip("-")


def matchup_path(season, week, away: str, home: str, gid) -> str:
    return f"/ncaa/scores/{int(season)}/{int(week)}/{slug(away)}_at_{slug(home)}_{int(gid)}"


def abbrevs() -> dict[str, str]:
    """school -> pff abbreviation, inverted from the map the parser solved."""
    if not TEAM_MAP.exists():
        return {}
    return {r["school"]: r["pff_abbrev"]
            for r in csv.DictReader(TEAM_MAP.open(encoding="utf-8"))}


def build(df: pd.DataFrame, abbr: dict[str, str]) -> tuple[dict, dict]:
    """Return {(season, week): [capture rows]} and {season: {gid: schedule row}}."""
    caps: dict[tuple, list] = {}
    scheds: dict[int, dict] = {}
    for r in df.itertuples():
        season, week, gid = int(r.season), int(r.week), int(r.game_id)
        away, home = r.away_team, r.home_team
        aa, ha = abbr.get(away, slug(away)[:6].upper()), abbr.get(home, slug(home)[:6].upper())
        cap = {c: "" for c in CAPTURE_COLUMNS}
        cap.update({
            "pff_game_id": gid, "season": season, "pff_week": week,
            "kickoff_raw": r.kickoff_utc, "away_abbreviation": aa,
            "home_abbreviation": ha,
            "market_over_under": r.market_line,
            # No projection in the exports -- they publish the edge, not the number it
            # came from -- so `projection` and `d` come out blank downstream.
            "greenline_total_projection": "",
            "total_best_side": r.side, "total_best_value": r.difference,
        })
        caps.setdefault((season, week), []).append(cap)

        sch = {c: "" for c in SCHEDULE_COLUMNS}
        sch.update({
            "pff_game_id": gid, "external_game_id": gid, "season": season,
            "pff_week": week, "kickoff_raw": r.kickoff_utc,
            # is_over stays empty on purpose: the warehouse supplies the finals.
            "is_over": "", "away_abbreviation": aa, "home_abbreviation": ha,
            "over_under": r.market_line,
            "matchup_path": matchup_path(season, week, away, home, gid),
        })
        scheds.setdefault(season, {})[gid] = sch
    return caps, scheds


def write(caps: dict, scheds: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for (season, week), rows in sorted(caps.items()):
        p = OUT_DIR / f"pff_greenline_{season}_w{week}.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=CAPTURE_COLUMNS)
            wr.writeheader()
            wr.writerows(rows)
        print(f"  wrote {p.name}  ({len(rows)} picks)")
    for season, by_gid in sorted(scheds.items()):
        p = OUT_DIR / f"pff_schedule_{season}.csv"
        with p.open("w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=SCHEDULE_COLUMNS)
            wr.writeheader()
            wr.writerows(by_gid.values())
        print(f"  wrote {p.name}  ({len(by_gid)} games, no scores -- warehouse supplies them)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return 0

    df = pd.read_csv(ARCHIVE)
    picks = df[(df["snapshot"] == "export") & (df["is_greenline_pick"] == True)  # noqa: E712
               & (df["market"] == "total") & df["game_id"].notna()
               & df["week"].notna()].copy()
    dropped = int(((df["snapshot"] == "export") & (df["is_greenline_pick"] == True)  # noqa: E712
                   & (df["market"] == "total")).sum()) - len(picks)

    print(f"archive: {ARCHIVE}")
    print(f"total picks: {len(picks)}   unmatched, cannot be graded: {dropped}\n")
    caps, scheds = build(picks, abbrevs())
    write(caps, scheds)

    print("\nnow grade them, writing outside the 2026 pooled record:")
    for season in sorted(scheds):
        print(f"  python research/totals/scripts/grade_greenline.py --season {season} "
              f"--all --in-dir {OUT_DIR} --out {OUT_DIR / f'graded_{season}.csv'}")
    return 0


def self_check() -> None:
    # The slug has to survive the round trip through slug_names(), because that is what
    # the warehouse fallback tokenizes to find the final score.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from match_greenline_books import slug_names, strong, toks

    mp = matchup_path(2022, 5, "Arkansas State", "UL Monroe", 401426340)
    away, home = slug_names(mp)
    assert away == "arkansas state" and home == "ul monroe", (away, home)
    assert strong(toks(away) & toks("Arkansas State"))
    assert strong(toks(home) & toks("UL Monroe"))

    # Punctuation and apostrophes must not survive into the slug and split a token.
    a2, h2 = slug_names(matchup_path(2023, 8, "Hawai'i", "Texas A&M", 1))
    assert a2 == "hawai i" and h2 == "texas a m", (a2, h2)
    assert strong(toks(a2) & toks("Hawai'i")), toks(a2)

    # A capture row must carry everything grade_one() reads, and nothing invented.
    df = pd.DataFrame([{
        "season": 2022.0, "week": 5.0, "game_id": 401426340.0,
        "away_team": "UL Monroe", "home_team": "Arkansas State",
        "kickoff_utc": "2022-10-01T23:00:00+00:00", "market_line": 60.0,
        "side": "under", "difference": 0.031,
    }])
    caps, scheds = build(df, {"UL Monroe": "ULM", "Arkansas State": "ARST"})
    cap = caps[(2022, 5)][0]
    assert cap["total_best_side"] == "under" and cap["market_over_under"] == 60.0
    assert cap["pff_game_id"] == 401426340 and cap["away_abbreviation"] == "ULM"
    assert set(cap) == set(CAPTURE_COLUMNS)
    # Empty is_over is the whole point: it routes grading to the warehouse.
    sch = scheds[2022][401426340]
    assert sch["is_over"] == "" and sch["away_score"] == "" and sch["home_score"] == ""
    assert set(sch) == set(SCHEDULE_COLUMNS)

    print("self-check ok")


if __name__ == "__main__":
    raise SystemExit(main())
