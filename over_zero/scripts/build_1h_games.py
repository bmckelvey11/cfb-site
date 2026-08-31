"""Build 2025 first-half games from local Action Network warehouse payloads."""

import csv
import json
import sys
from pathlib import Path

import duckdb


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "cfb_paths.py").is_file():
            return parent
    raise RuntimeError("Cannot locate repository root containing cfb_paths.py")


sys.path.insert(0, str(_repo_root()))
from cfb_paths import DB_PATH, PROCESSED  # noqa: E402


OUT_CSV = PROCESSED / "over_zero" / "1h_games.csv"
COLUMNS = [
    "game_id", "season", "week", "home_team", "away_team",
    "home_conference", "away_conference", "home_points", "away_points",
    "provider", "spread", "total",
]


def team_lookup(game):
    return {team["id"]: team for team in game["teams"]}


def rows_from_payload(payload):
    data = json.loads(payload)
    for game in data.get("games", []):
        if game.get("real_status") != "closed":
            continue
        odds = game.get("boxscore", {}).get("latest_odds", {}).get("firsthalf")
        if not odds:
            continue
        teams = team_lookup(game)
        home = teams.get(game["home_team_id"])
        away = teams.get(game["away_team_id"])
        if home is None or away is None:
            continue
        boxscore = game["boxscore"]
        home_points = boxscore.get("total_home_firsthalf_points")
        away_points = boxscore.get("total_away_firsthalf_points")
        if home_points is None or away_points is None:
            continue
        yield {
            "game_id": game["id"],
            "season": game["season"],
            "week": game["week"],
            "home_team": home["full_name"],
            "away_team": away["full_name"],
            "home_conference": home.get("conference_type", ""),
            "away_conference": away.get("conference_type", ""),
            "home_points": home_points,
            "away_points": away_points,
            "provider": "actionnetwork",
            "spread": odds.get("spread_home"),
            "total": odds.get("total"),
        }


def scoreboard_payloads(connection, season=2025):
    return connection.execute(
        """
        SELECT payload, source_file
        FROM raw.actionnetwork_scoreboard
        WHERE season = ?
        ORDER BY source_file
        """,
        [season],
    ).fetchall()


def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(DB_PATH), read_only=True) as connection:
        payloads = scoreboard_payloads(connection)

    with OUT_CSV.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=COLUMNS)
        writer.writeheader()
        seen = set()
        count = 0
        for payload, _source_file in payloads:
            for row in rows_from_payload(payload):
                if row["game_id"] in seen:
                    continue
                seen.add(row["game_id"])
                writer.writerow(row)
                count += 1
    print(f"wrote {count} rows from {len(payloads)} warehouse payloads -> {OUT_CSV}")


if __name__ == "__main__":
    main()
