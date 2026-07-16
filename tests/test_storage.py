import json
from datetime import datetime

from cfb_system_maker.models import GameRecord
from cfb_system_maker.storage import load_processed_games, load_raw_json, save_processed_games, save_raw_json


def test_raw_json_round_trip(tmp_path):
    rows = [{"id": 1, "homeTeam": "A"}, {"id": 2, "homeTeam": "B"}]

    path = save_raw_json(tmp_path, "games", 2023, rows)

    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == rows
    assert load_raw_json(tmp_path, "games", 2023) == rows


def test_raw_json_serializes_api_datetimes(tmp_path):
    rows = [{"id": 1, "startDate": datetime(2023, 9, 2, 12, 0, 0)}]

    path = save_raw_json(tmp_path, "games", 2023, rows)

    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": 1, "startDate": "2023-09-02 12:00:00"}]


def test_processed_games_csv_round_trip(tmp_path):
    games = [
        GameRecord(
            game_id=1,
            season=2023,
            week=1,
            home_team="A",
            away_team="B",
            home_conference="ACC",
            away_conference="SEC",
            home_points=28,
            away_points=21,
            provider="consensus",
            spread=-6.5,
            total=49.5,
        )
    ]

    path = save_processed_games(tmp_path, games)
    loaded = load_processed_games(tmp_path)

    assert path.name == "games.csv"
    assert loaded == games
