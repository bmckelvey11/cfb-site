"""Pull the PFF website's public scoreboard feeds to CSV.

    python scripts/pull_pff_scoreboard.py                 # current season
    python scripts/pull_pff_scoreboard.py --season 2026
    python scripts/pull_pff_scoreboard.py --greenline --week 2   # picks, needs a cookie
    python scripts/pull_pff_scoreboard.py --report        # counts only, write nothing
    python scripts/pull_pff_scoreboard.py --self-check    # offline parser check

Writes to $CFB_DATA_ROOT/ingest/pff_scoreboard/ (not globbed by the warehouse):

  pff_schedule_<season>.csv          one row per game: opener + current spread/total/ML
  pff_bet_split_<season>.csv         one row per (game, market): line, prices, public
                                     cash% / ticket% split, and PFF's `has_value` flag
  pff_greenline_<season>_w<week>.csv one row per game: PFF's own projected spread and
                                     total, cover probabilities, and the side it likes

These are www.pff.com endpoints, NOT the api.pff.com developer API -- that spec has
no picks or odds operations at all, and its API key does not authenticate this host
(tried Bearer and x-api-key; both return `is_premium_subscriber: false`).

TWO AUTH SURFACES. The schedule and best_bets feeds are public. Greenline -- the
picks -- lives on /api/scoreboard/matchup and is server-side gated: without a
logged-in premium session, greenline_{spread,total,money_line}_prop come back null
and every best_bets market reads `locked: "premium"`. With one, the props carry
`greenline_spread`, the total `projection`, per-side cover probabilities, and
`best_side`/`best_value`. Verified 2026-09-09 against a Pro web session.

So `--greenline` needs the browser session cookie, in `PFF_WEB_COOKIE` (environment
or env.env). To get it: signed into pff.com, open DevTools -> Network on any
/api/scoreboard/matchup request -> Request Headers -> copy the whole `cookie:`
value. It is a credential; it expires, and a 401 or a `premium: False` row means
re-copy it.

CURRENT SEASON ONLY, and that is a server-side fact, not a missing parameter.
Swept 2019-2027 for NCAA and 2025-2026 for NFL against a premium session: every
season but 2026 returns zero games, with or without `&week=`. Asking the matchup
endpoint for a 2025 game by its real id answers `No game in schedules with id
29099 and 5` -- the scoreboard's schedule store holds this season and nothing
else. So there is no backfill here; like the Action Network history, coverage
starts when you log it.

For historical PFF game ids, use the developer API instead: `/v1/games?league=
ncaa&season=<year>&week=<n>` serves back to at least 2014 (id, teams, kickoff,
final score, stadium). No odds and no Greenline on it -- it is a game index, good
for joining PFF ids to the warehouse, not for lines.

Each run overwrites its CSVs; the schedule snapshot is self-describing (it carries
both opener and current), so re-running gives a fresh state, not an appended one.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
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

GREENLINE_COLUMNS = [
    "pff_game_id", "season", "pff_week", "kickoff_raw",
    "away_abbreviation", "home_abbreviation",
    "market_spread", "greenline_spread", "spread_best_side", "spread_best_value",
    "spread_value_label", "spread_value_level",
    "spread_away_cover_probability", "spread_home_cover_probability",
    "market_over_under", "greenline_total_projection", "total_best_side", "total_best_value",
    "total_value_label", "total_value_level",
    "over_cover_probability", "under_cover_probability",
    "market_money_line_away", "market_money_line_home",
    "greenline_money_line_away", "greenline_money_line_home",
    "money_line_best_side", "money_line_best_value",
    "money_line_value_label", "money_line_value_level",
    "money_line_away_cover_probability", "money_line_home_cover_probability",
]


def get(path: str, query: str, cookie: str | None = None) -> dict:
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(f"{BASE}/{path}?{query}", headers=headers)
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.load(fh)


def web_cookie() -> str:
    value = os.environ.get("PFF_WEB_COOKIE")
    if value:
        return value
    env_file = Path(__file__).resolve().parents[1] / "env.env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("PFF_WEB_COOKIE="):
                return line.split("=", 1)[1].strip()
    raise SystemExit(
        "PFF_WEB_COOKIE not set -- Greenline needs a logged-in premium session; "
        "see the module docstring for how to copy the cookie header"
    )


def raw_games(payload: dict) -> list[dict]:
    """Every game once. The feed repeats some -- 5 of week 2's 89 entries in the
    2026 pull were a second listing of the same `pff_game_id` -- so first wins."""
    seen, out = set(), []
    for week in payload.get("weeks") or []:
        for g in week.get("games") or []:
            gid = g.get("pff_game_id")
            if gid in seen:
                continue
            seen.add(gid)
            out.append(g)
    return out


def schedule_rows(payload: dict, season: int) -> list[dict]:
    rows = []
    for g in raw_games(payload):
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


def greenline_row(game: dict, matchup: dict, season: int) -> dict | None:
    """One row per game. None when the session did not unlock the props."""
    gl = matchup.get("greenline") or {}
    spread = gl.get("greenline_spread_prop") or {}
    total = gl.get("greenline_total_prop") or {}
    money = gl.get("greenline_money_line_prop") or {}
    if not (spread or total or money):
        return None
    return {
        "pff_game_id": game.get("pff_game_id"),
        "season": season,
        "pff_week": game.get("pff_week"),
        "kickoff_raw": game.get("kickoff_raw"),
        "away_abbreviation": (game.get("away_franchise") or {}).get("abbreviation"),
        "home_abbreviation": (game.get("home_franchise") or {}).get("abbreviation"),
        "market_spread": gl.get("market_spread"),
        "greenline_spread": spread.get("greenline_spread"),
        "spread_best_side": spread.get("best_side"),
        "spread_best_value": spread.get("best_value"),
        "spread_value_label": gl.get("greenline_spread_value_label"),
        "spread_value_level": gl.get("greenline_spread_value_level"),
        "spread_away_cover_probability": spread.get("away_cover_probability"),
        "spread_home_cover_probability": spread.get("home_cover_probability"),
        "market_over_under": gl.get("market_over_under"),
        "greenline_total_projection": total.get("projection"),
        "total_best_side": total.get("best_side"),
        "total_best_value": total.get("best_value"),
        "total_value_label": gl.get("greenline_total_value_label"),
        "total_value_level": gl.get("greenline_total_value_level"),
        "over_cover_probability": total.get("over_cover_probability"),
        "under_cover_probability": total.get("under_cover_probability"),
        "market_money_line_away": gl.get("market_money_line_away"),
        "market_money_line_home": gl.get("market_money_line_home"),
        "greenline_money_line_away": gl.get("greenline_money_line_away"),
        "greenline_money_line_home": gl.get("greenline_money_line_home"),
        "money_line_best_side": money.get("best_side"),
        "money_line_best_value": money.get("best_value"),
        "money_line_value_label": gl.get("greenline_money_line_value_label"),
        "money_line_value_level": gl.get("greenline_money_line_value_level"),
        "money_line_away_cover_probability": money.get("away_cover_probability"),
        "money_line_home_cover_probability": money.get("home_cover_probability"),
    }


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

    # The feed repeats games across weeks; one row each.
    dupe = {"weeks": [sched["weeks"][0], sched["weeks"][0]]}
    assert len(schedule_rows(dupe, 2026)) == 1

    game = sched["weeks"][0]["games"][0]
    unlocked = {"greenline": {
        "market_spread": -3.5, "market_over_under": 54.5,
        "greenline_spread_value_label": "away", "greenline_spread_value_level": 1,
        "greenline_spread_prop": {
            "greenline_spread": -1.8, "best_side": "away", "best_value": 0.0719,
            "away_cover_probability": 0.5958, "home_cover_probability": 0.4042,
        },
        "greenline_total_prop": {"projection": 55.9, "best_side": "over", "best_value": 0.0073},
        "greenline_money_line_prop": {"best_side": "away", "best_value": 0.0406},
    }}
    grow = greenline_row(game, unlocked, 2026)
    assert grow is not None
    assert set(grow) == set(GREENLINE_COLUMNS)
    assert grow["greenline_spread"] == -1.8 and grow["market_spread"] == -3.5
    assert grow["spread_best_side"] == "away"
    assert grow["greenline_total_projection"] == 55.9
    assert grow["home_abbreviation"] == "BC"

    # The paywalled shape: props present as keys but null. Must not become a row.
    locked = {"greenline": {
        "market_spread": -3.5, "greenline_spread_prop": None,
        "greenline_total_prop": None, "greenline_money_line_prop": None,
    }}
    assert greenline_row(game, locked, 2026) is None
    assert greenline_row(game, {}, 2026) is None
    print("self-check ok")


def greenline_pull(sched: dict, args, games: list[dict]) -> list[dict]:
    if args.from_dump:
        dump = json.loads(args.from_dump.read_text(encoding="utf-8"))
        return [
            r for r in (greenline_row(e["game"], e["matchup"], args.season) for e in dump)
            if r is not None
        ]

    raw = raw_games(sched)
    week = args.week or next(
        (g["pff_week"] for g in sorted(raw, key=lambda x: x.get("kickoff_raw") or "")
         if not g.get("is_over")),
        None,
    )
    if week is None:
        raise SystemExit("no unplayed games left; pass --week")
    wanted = [g for g in raw if str(g.get("pff_week")) == str(week)]
    print(f"week {week}: {len(wanted)} games")

    cookie = web_cookie()
    rows, locked = [], 0
    for i, g in enumerate(wanted):
        slug = g.get("slug") or (g.get("matchup_path") or "").rsplit("/", 1)[-1]
        matchup = get(
            "scoreboard/matchup",
            f"league={args.league}&season={args.season}&week={week}&game={slug}",
            cookie=cookie,
        )
        row = greenline_row(g, matchup, args.season)
        if row is None:
            locked += 1
        else:
            rows.append(row)
        if i + 1 < len(wanted):
            time.sleep(PACING_SECONDS)
    if locked and not rows:
        raise SystemExit(
            "every game came back locked -- PFF_WEB_COOKIE is expired or not a premium session"
        )
    if locked:
        print(f"{locked} games returned no props (not yet priced, or locked)")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument("--league", default="ncaa")
    ap.add_argument("--report", action="store_true", help="counts only, write nothing")
    ap.add_argument("--self-check", action="store_true", help="offline parser check")
    ap.add_argument("--greenline", action="store_true", help="also pull the picks (needs PFF_WEB_COOKIE)")
    ap.add_argument("--week", help="week to pull Greenline for; defaults to the next unplayed one")
    ap.add_argument(
        "--from-dump",
        type=Path,
        help="flatten Greenline from a saved [{game, matchup}] JSON instead of fetching",
    )
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

    if args.greenline or args.from_dump:
        rows = greenline_pull(sched, args, games)
        print(f"{len(rows)} games with Greenline props")
        if not args.report:
            week = args.week or (rows[0]["pff_week"] if rows else "na")
            path = OUT_DIR / f"pff_greenline_{args.season}_w{week}.csv"
            write_csv(path, GREENLINE_COLUMNS, rows)
            print(f"wrote {path}")
        return

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
