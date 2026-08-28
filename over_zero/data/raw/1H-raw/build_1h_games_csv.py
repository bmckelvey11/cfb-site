"""Build a 1H games.csv from ActionNetwork scoreboard_2025_wk*.json files,
matching the schema of data/processed/games.csv (with home/away first-half
points instead of full-game points).

Run: python data/raw/1H-raw/build_1h_games_csv.py
"""

import csv
import json
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent / "scoreboard"
OUT_CSV = RAW_DIR.parent.parent.parent / "processed" / "1h_games.csv"

COLUMNS = [
    "game_id", "season", "week", "home_team", "away_team",
    "home_conference", "away_conference",
    "home_points", "away_points", "provider", "spread", "total",
]


def team_lookup(game):
    teams = {t["id"]: t for t in game["teams"]}
    return teams


def rows_from_file(path):
    data = json.loads(path.read_text())
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

        bx = game["boxscore"]
        home_pts = bx.get("total_home_firsthalf_points")
        away_pts = bx.get("total_away_firsthalf_points")
        if home_pts is None or away_pts is None:
            continue

        yield {
            "game_id": game["id"],
            "season": game["season"],
            "week": game["week"],
            "home_team": home["full_name"],
            "away_team": away["full_name"],
            "home_conference": home.get("conference_type", ""),
            "away_conference": away.get("conference_type", ""),
            "home_points": home_pts,
            "away_points": away_pts,
            "provider": "actionnetwork",
            "spread": odds.get("spread_home"),
            "total": odds.get("total"),
        }


def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(RAW_DIR.glob("scoreboard_*.json"))
    seen = set()
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        n = 0
        for path in files:
            for row in rows_from_file(path):
                if row["game_id"] in seen:
                    continue
                seen.add(row["game_id"])
                writer.writerow(row)
                n += 1
    print(f"wrote {n} rows from {len(files)} files -> {OUT_CSV}")


if __name__ == "__main__":
    main()
