import json

from cfb_system_maker.enrich import enrich_games, save_features
from cfb_system_maker.models import GameRecord


def test_enrich_game_id_join_and_team_scoped_mapping(tmp_path):
    season = 2023
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)

    (raw_dir / f"games_{season}.json").write_text(
        json.dumps(
            [
                {
                    "id": 1,
                    "season": season,
                    "neutralSite": True,
                    "conferenceGame": False,
                    "venue": "Stadium",
                    "seasonType": "regular",
                    "homePregameElo": 1600,
                    "awayPregameElo": 1500,
                    "attendance": 50000,
                }
            ]
        ),
        encoding="utf-8",
    )
    (raw_dir / f"weather_{season}.json").write_text(
        json.dumps([{"id": 1, "temperature": 62.0, "gameIndoors": False, "weatherCondition": "Clear"}]),
        encoding="utf-8",
    )
    (raw_dir / f"returning_production_{season}.json").write_text(
        json.dumps(
            [
                {"team": "Alpha", "season": season, "percentPPA": 0.55},
                {"team": "Beta", "season": season, "percentPPA": 0.41},
            ]
        ),
        encoding="utf-8",
    )

    games = [
        GameRecord(
            game_id=1,
            season=season,
            week=1,
            home_team="Alpha",
            away_team="Beta",
            home_conference="ACC",
            away_conference="SEC",
            home_points=21,
            away_points=14,
            provider="consensus",
            spread=-3.5,
            total=45.5,
        )
    ]

    features = enrich_games(tmp_path, games)
    row = features["1"]

    assert row["neutralSite"] is True
    assert row["weather_temperature"] == 62.0
    assert row["home_returning_ppa"] == 0.55
    assert row["away_returning_ppa"] == 0.41
    assert row["attendance"] == 50000

    path = save_features(tmp_path, features)
    assert path.exists()
