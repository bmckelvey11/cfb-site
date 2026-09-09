"""Pull the PFF website's public scoreboard feeds to CSV.

    python scripts/pull_pff_scoreboard.py                 # current season
    python scripts/pull_pff_scoreboard.py --season 2026
    python scripts/pull_pff_scoreboard.py --report        # counts only, write nothing
    python scripts/pull_pff_scoreboard.py --self-check    # offline parser check

Writes to $CFB_DATA_ROOT/ingest/pff_scoreboard/ (not globbed by the warehouse):

  pff_schedule_<season>.csv     one row per game: opener + current spread/total/ML
  pff_bet_split_<season>.csv    one row per (game, market): line, prices, public
                                cash% / ticket% split, and PFF's `has_value` flag

These are www.pff.com endpoints, NOT the api.pff.com developer API -- that spec has
no picks or odds operations at all, and its API key does not authenticate this host
(tried Bearer and x-api-key; both return `is_premium_subscriber: false`).

WHAT IS NOT HERE: the picks. PFF's Greenline projections live on
/api/scoreboard/matchup as greenline_{spread,total,money_line}_prop and come back
null unless the request carries a logged-in premium session cookie. `best_bets`
likewise marks every priced market `locked: "premium"`. The public half -- lines,
the cash/ticket split, and the fact that PFF flags a market as holding value -- is
what this pulls; which side it likes is paywalled.

Current season only. season=2025 and earlier return zero games, so there is no
backfill here -- like the Action Network history, coverage starts when you log it.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cfb_paths import INGEST, current_season  # noqa: E402

BASE = "https://www.pff.com/api"
OUT_DIR = INGEST / "pff_scoreboard"
PACING_SECONDS = 0.5

SCHEDULE_COLUMNS = [
    "pff_game_id", "external_game_id", "season", "pff_week", "kickoff_raw",
    "status", "is_over", "channel",
    "away_franchise_id", "away_abbreviation", "away_record", "away_ats_record", "away_score",
    "home_franchise_id", "home_abbreviation", "home_record", "home_ats_record", "home_score",
    "opening_point_spread", "point_spread",
    "opening_over_under", "over_under",
    "opening_away_money_line", "opening_home_money_line",
    "away_team_money_line", "home_team_money_line",
    "betting_value_count", "matchup_path",
]

SPLIT_COLUMNS = [
    "pff_game_id", "season", "prop_type", "value_type", "has_value", "locked",
    "start", "line", "spread",
    "over_odds", "under_odds", "over_cash", "under_cash", "over_tickets", "under_tickets",
    "away_odds", "home_odds", "away_cash", "home_cash", "away_tickets", "home_tickets",
]


def get(path: str, query: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}/{path}?{query}",
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh)


def schedule_rows(payload: dict, season: int) -> list[dict]:
    rows = []
    for week in payload.get("weeks") or []:
        for g in week.get("games") or []:
            away = g.get("away_franchise") or {}
            home = g.get("home_franchise") or {}
            rows.append({
                "pff_game_id": g.get("pff_game_id"),
                "external_game_id": g.get("external_game_id"),
                "season": season,
                "pff_week": g.get("pff_week"),
                "kickoff_raw": g.get("kickoff_raw"),
                "status": g.get("status"),
                "is_over": g.get("is_over"),
                "channel": g.get("channel"),
                "away_franchise_id": away.get("franchise_id"),
                "away_abbreviation": away.get("abbreviation"),
                "away_record": g.get("away_record"),
                "away_ats_record": g.get("away_ats_record"),
                "away_score": g.get("away_score"),
                "home_franchise_id": home.get("franchise_id"),
                "home_abbreviation": home.get("abbreviation"),
                "home_record": g.get("home_record"),
                "home_ats_record": g.get("home_ats_record"),
                "home_score": g.get("home_score"),
                "opening_point_spread": g.get("opening_point_spread"),
                "point_spread": g.get("point_spread"),
                "opening_over_under": g.get("opening_over_under"),
                "over_under": g.get("over_under"),
                "opening_away_money_line": g.get("opening_away_money_line"),
                "opening_home_money_line": g.get("opening_home_money_line"),
                "away_team_money_line": g.get("away_team_money_line"),
                "home_team_money_line": g.get("home_team_money_line"),
                "betting_value_count": g.get("betting_value_count"),
                "matchup_path": g.get("matchup_path"),
            })
    return rows


def split_rows(payload: dict, season: int) -> list[dict]:
    """`game_odds` is populated only for the game_id the request asked for."""
    rows = []
    for o in payload.get("game_odds") or []:
        rows.append({
            "pff_game_id": o.get("game_id"),
            "season": season,
            "prop_type": o.get("prop_type"),
            "value_type": o.get("value_type"),
            "has_value": o.get("has_value"),
            "locked": o.get("locked"),
            "start": o.get("start"),
            "line": o.get("line"),
            "spread": o.get("spread"),
            "over_odds": o.get("over"),
            "under_odds": o.get("under"),
            "over_cash": o.get("over_cash"),
            "under_cash": o.get("under_cash"),
            "over_tickets": o.get("over_tickets"),
            "under_tickets": o.get("under_tickets"),
            "away_odds": o.get("away_odds"),
            "home_odds": o.get("home_odds"),
            "away_cash": o.get("away_cash"),
            "home_cash": o.get("home_cash"),
            "away_tickets": o.get("away_tickets"),
            "home_tickets": o.get("home_tickets"),
        })
    return rows


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def self_check() -> None:
    sched = {"weeks": [{"games": [{
        "pff_game_id": 31104, "pff_week": "2", "opening_point_spread": -3.0,
        "point_spread": -3.5, "betting_value_count": 3,
        "away_franchise": {"franchise_id": 278, "abbreviation": "RUTG"},
        "home_franchise": {"franchise_id": 121, "abbreviation": "BC"},
    }]}]}
    rows = schedule_rows(sched, 2026)
    assert len(rows) == 1, rows
    assert rows[0]["away_abbreviation"] == "RUTG"
    assert rows[0]["point_spread"] - rows[0]["opening_point_spread"] == -0.5
    assert set(rows[0]) == set(SCHEDULE_COLUMNS)

    best = {"game_odds": [
        {"game_id": 31104, "prop_type": "game_away_home_spread", "spread": -3.5,
         "has_value": True, "locked": "premium", "home_cash": 48, "home_tickets": 69},
        {"game_id": 31104, "prop_type": "game_point_total", "line": 54.5,
         "has_value": True, "locked": "premium", "over": -110, "under_cash": 94},
    ]}
    srows = split_rows(best, 2026)
    assert len(srows) == 2, srows
    assert srows[0]["home_cash"] == 48 and srows[0]["spread"] == -3.5
    assert srows[1]["line"] == 54.5 and srows[1]["over_odds"] == -110
    assert set(srows[0]) == set(SPLIT_COLUMNS)

    assert schedule_rows({"weeks": [{"games": None}]}, 2026) == []
    assert split_rows({}, 2026) == []
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument("--league", default="ncaa")
    ap.add_argument("--report", action="store_true", help="counts only, write nothing")
    ap.add_argument("--self-check", action="store_true", help="offline parser check")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    sched = get("scoreboard/schedule", f"league={args.league}&season={args.season}")
    games = schedule_rows(sched, args.season)
    if not games:
        raise SystemExit(
            f"no games for season {args.season} -- this feed serves the current season only"
        )

    # One request per game, so ask only where PFF says a priced market exists.
    flagged = [g["pff_game_id"] for g in games if (g["betting_value_count"] or 0) > 0]
    splits = []
    for i, gid in enumerate(flagged):
        splits += split_rows(
            get("betting/best_bets", f"league={args.league}&game_id={gid}"), args.season
        )
        if i + 1 < len(flagged):
            time.sleep(PACING_SECONDS)

    moved = sum(
        1 for g in games
        if g["opening_point_spread"] is not None and g["point_spread"] is not None
        and g["opening_point_spread"] != g["point_spread"]
    )
    print(f"season {args.season}: {len(games)} games, {moved} with spread movement off the opener")
    print(f"{len(flagged)} games flagged with betting value -> {len(splits)} market rows")

    if args.report:
        return

    sched_path = OUT_DIR / f"pff_schedule_{args.season}.csv"
    split_path = OUT_DIR / f"pff_bet_split_{args.season}.csv"
    write_csv(sched_path, SCHEDULE_COLUMNS, games)
    write_csv(split_path, SPLIT_COLUMNS, splits)
    print(f"wrote {sched_path}")
    print(f"wrote {split_path}")


if __name__ == "__main__":
    main()
