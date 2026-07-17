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


def test_enrich_computes_running_stats_from_prior_games(tmp_path):
    season = 2023
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)

    (raw_dir / f"games_{season}.json").write_text(
        json.dumps(
            [
                {"id": 1, "season": season, "startDate": "2023-09-02 17:00:00+00:00"},
                {"id": 2, "season": season, "startDate": "2023-09-09 17:00:00+00:00"},
            ]
        ),
        encoding="utf-8",
    )
    (raw_dir / f"ppa_games_{season}.json").write_text(
        json.dumps(
            [
                {"gameId": 1, "team": "Alpha", "offense": {"overall": 0.5}, "defense": {"overall": -0.2}},
                {"gameId": 1, "team": "Beta", "offense": {"overall": 0.1}, "defense": {"overall": 0.3}},
            ]
        ),
        encoding="utf-8",
    )

    games = [
        GameRecord(1, season, 1, "Alpha", "Beta", None, None, 21, 14, "consensus", -3.5, None),
        GameRecord(2, season, 2, "Alpha", "Beta", None, None, 10, 20, "consensus", -3.5, None),
    ]

    features = enrich_games(tmp_path, games)

    entering_g1 = features["1"]
    assert entering_g1["home_running_games_played"] == 0
    assert entering_g1["home_running_win_pct"] is None

    entering_g2 = features["2"]
    assert entering_g2["home_running_games_played"] == 1
    assert entering_g2["home_running_win_pct"] == 1.0       # Alpha won game 1
    assert entering_g2["home_running_ats_pct"] == 1.0        # -3.5, won by 7: covered
    assert entering_g2["away_running_ats_pct"] == 0.0        # Beta failed to cover +3.5
    assert entering_g2["home_running_ppa_off"] == 0.5
    assert entering_g2["away_running_ppa_def"] == 0.3


def test_save_features_writes_meta_and_load_reads_both_shapes(tmp_path):
    from cfb_system_maker.enrich import load_features, load_features_meta
    from cfb_system_maker.features import registry_version

    path = save_features(tmp_path, {"1": {"neutralSite": True}})
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["_meta"]["registry_version"] == registry_version()
    assert payload["_meta"]["game_count"] == 1
    assert load_features(tmp_path) == {1: {"neutralSite": True}}
    assert load_features_meta(tmp_path)["game_count"] == 1

    # Legacy flat shape still loads, meta reads as None
    path.write_text(json.dumps({"2": {"neutralSite": False}}), encoding="utf-8")
    assert load_features(tmp_path) == {2: {"neutralSite": False}}
    assert load_features_meta(tmp_path) is None


def test_enrich_resolves_venue_fields_via_venue_id(tmp_path):
    season = 2023
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / f"games_{season}.json").write_text(
        json.dumps([{"id": 1, "season": season, "venueId": 55}]), encoding="utf-8"
    )
    (raw_dir / "venues.json").write_text(
        json.dumps([{"id": 55, "dome": True, "grass": False, "elevation": "177.0", "capacity": 70000}]),
        encoding="utf-8",
    )

    games = [GameRecord(1, season, 1, "Alpha", "Beta", None, None, 21, 14, "consensus", -3.5, None)]
    features = enrich_games(tmp_path, games)
    row = features["1"]
    assert row["venue_dome"] is True
    assert row["venue_grass"] is False
    assert row["venue_elevation"] == "177.0"
    assert row["venue_capacity"] == 70000


def test_enrich_resolves_conference_classification_per_side(tmp_path):
    season = 2023
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "conferences.json").write_text(
        json.dumps(
            [
                {"name": "ACC", "classification": "fbs"},
                {"name": "Big Sky", "classification": "fcs"},
            ]
        ),
        encoding="utf-8",
    )

    games = [GameRecord(1, season, 1, "Alpha", "Beta", "ACC", "Big Sky", 21, 14, "consensus", -3.5, None)]
    features = enrich_games(tmp_path, games)
    assert features["1"]["home_conference_classification"] == "fbs"
    assert features["1"]["away_conference_classification"] == "fcs"

    games_no_conf = [GameRecord(2, season, 1, "Gamma", "Delta", None, None, 7, 3, "consensus", -1.0, None)]
    features = enrich_games(tmp_path, games_no_conf)
    assert features["2"]["home_conference_classification"] is None


def test_enrich_wind_direction_and_rest_pregame_win_prob(tmp_path):
    season = 2023
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / f"weather_{season}.json").write_text(
        json.dumps([{"id": 1, "windDirection": 270}]), encoding="utf-8"
    )
    (raw_dir / f"pregame_win_prob_{season}.json").write_text(
        json.dumps([{"gameId": 1, "homeWinProbability": 0.731}]), encoding="utf-8"
    )

    games = [GameRecord(1, season, 1, "Alpha", "Beta", None, None, 21, 14, "consensus", -3.5, None)]
    features = enrich_games(tmp_path, games)
    assert features["1"]["weather_windDirection"] == 270
    assert features["1"]["pregame_home_win_prob"] == 0.731
