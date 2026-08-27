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


def test_enrich_surfaces_running_success_off_from_prior_games(tmp_path):
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
    (raw_dir / f"advanced_game_stats_{season}.json").write_text(
        json.dumps(
            [
                {"gameId": 1, "team": "Alpha", "offense": {"successRate": 0.47}},
                {"gameId": 1, "team": "Beta", "offense": {"successRate": 0.33}},
            ]
        ),
        encoding="utf-8",
    )

    games = [
        GameRecord(1, season, 1, "Alpha", "Beta", None, None, 21, 14, "consensus", -3.5, None),
        GameRecord(2, season, 2, "Alpha", "Beta", None, None, 10, 20, "consensus", -3.5, None),
    ]

    features = enrich_games(tmp_path, games)

    assert features["1"]["home_running_success_off"] is None  # first game: no prior
    assert features["2"]["home_running_success_off"] == 0.47  # only prior game (Alpha, game 1)
    assert features["2"]["away_running_success_off"] == 0.33  # Beta's prior game 1


def test_enrich_success_off_fails_closed_on_dict_shaped_field(tmp_path):
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
    # Malformed: successRate is a dict, not a float. Must yield None, never raise.
    (raw_dir / f"advanced_game_stats_{season}.json").write_text(
        json.dumps([{"gameId": 1, "team": "Alpha", "offense": {"successRate": {"total": 0.5}}}]),
        encoding="utf-8",
    )

    games = [
        GameRecord(1, season, 1, "Alpha", "Beta", None, None, 21, 14, "consensus", -3.5, None),
        GameRecord(2, season, 2, "Alpha", "Beta", None, None, 10, 20, "consensus", -3.5, None),
    ]

    features = enrich_games(tmp_path, games)  # must not raise
    assert features["2"]["home_running_success_off"] is None


def test_enrich_prior_off_wepa_uses_prior_season_only(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)

    # Prior season (2022): Alpha players sum to 5.0 (3.0 + 2.0).
    (raw_dir / "adjusted_player_passing_2022.json").write_text(
        json.dumps(
            [
                {"athleteId": 10, "team": "Alpha", "wepa": 3.0, "year": 2022},
                {"athleteId": 11, "team": "Alpha", "wepa": 2.0, "year": 2022},
            ]
        ),
        encoding="utf-8",
    )
    # Same season (2023): sentinel that must NEVER leak into the 2023 game feature.
    (raw_dir / "adjusted_player_passing_2023.json").write_text(
        json.dumps([{"athleteId": 10, "team": "Alpha", "wepa": 99.0, "year": 2023}]),
        encoding="utf-8",
    )

    games = [GameRecord(1, 2023, 1, "Alpha", "Beta", None, None, 21, 14, "consensus", -3.5, None)]
    features = enrich_games(tmp_path, games)
    row = features["1"]

    assert row["home_prior_off_wepa"] == 5.0   # 2022 aggregation only
    assert row["home_prior_off_wepa"] != 99.0  # 2023's own season never leaks
    assert row["away_prior_off_wepa"] is None   # Beta absent from 2022 file -> None


def test_enrich_prior_off_wepa_none_when_prior_file_absent(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    # No adjusted_player_passing_2020.json on disk -> fails closed to None.

    games = [GameRecord(1, 2021, 1, "Alpha", "Beta", None, None, 21, 14, "consensus", -3.5, None)]
    features = enrich_games(tmp_path, games)
    assert features["1"]["home_prior_off_wepa"] is None
    assert features["1"]["away_prior_off_wepa"] is None


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


def _accumulation_raw(tmp_path, *, lines_cover_full_season):
    """Weeks 1-4 played, week 5 unplayed. ``lines_cover_full_season`` toggles the broken shape."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    games = [
        {
            "id": 3000 + week,
            "season": 2026,
            "week": week,
            "seasonType": "regular",
            "startDate": f"2026-09-{week:02d} 19:00:00+00:00",
            "completed": True,
            "homeTeam": "Alpha",
            "awayTeam": "Beta",
            "homePoints": 28,
            "awayPoints": 21,
        }
        for week in range(1, 5)
    ] + [
        {
            "id": 3005,
            "season": 2026,
            "week": 5,
            "seasonType": "regular",
            "startDate": "2026-09-30 19:00:00+00:00",
            "completed": False,
            "homeTeam": "Alpha",
            "awayTeam": "Gamma",
            "homePoints": None,
            "awayPoints": None,
        }
    ]
    lined_ids = [3001, 3002, 3003, 3004, 3005] if lines_cover_full_season else [3005]
    lines = [
        {"id": game_id, "lines": [{"provider": "DraftKings", "spread": -7.0, "overUnder": 52.5}]}
        for game_id in lined_ids
    ]

    (raw_dir / "games_2026.json").write_text(json.dumps(games), encoding="utf-8")
    (raw_dir / "lines_2026.json").write_text(json.dumps(lines), encoding="utf-8")


def _target_record():
    return GameRecord(3005, 2026, 5, "Alpha", "Gamma", None, None, None, None, "consensus", -7.0, 52.5)


def test_enrich_upcoming_accumulates_the_seasons_completed_weeks(tmp_path):
    from cfb_system_maker.upcoming import enrich_upcoming

    _accumulation_raw(tmp_path, lines_cover_full_season=True)

    features = enrich_upcoming(tmp_path, 2026, [_target_record()])

    assert features["3005"]["home_running_games_played"] == 4
    assert features["3005"]["home_running_win_pct"] == 1.0


def test_enrich_upcoming_is_null_when_the_lines_dump_covers_only_the_target_week(tmp_path):
    """The failure this plan exists to prevent, made expressible.

    With a target-week-only lines dump the completed weeks normalize to nothing and
    every entering-game value comes back null -- with no error anywhere. The paired
    non-null assertion above is only meaningful because this shape is reachable.
    """
    from cfb_system_maker.upcoming import enrich_upcoming

    _accumulation_raw(tmp_path, lines_cover_full_season=False)

    features = enrich_upcoming(tmp_path, 2026, [_target_record()])

    assert features["3005"]["home_running_games_played"] == 0
    assert features["3005"]["home_running_win_pct"] is None


def test_enrich_upcoming_never_overwrites_the_historical_features_sidecar(tmp_path):
    from cfb_system_maker.upcoming import enrich_upcoming

    _accumulation_raw(tmp_path, lines_cover_full_season=True)
    historical = save_features(tmp_path, {"1": {"neutralSite": True}})
    before = historical.read_bytes()

    enrich_upcoming(tmp_path, 2026, [_target_record()])

    assert historical.read_bytes() == before
    assert (tmp_path / "processed" / "upcoming_features.json").exists()


def test_upcoming_sidecar_loads_through_the_existing_features_reader(tmp_path):
    from cfb_system_maker.enrich import load_features_from, upcoming_features_path
    from cfb_system_maker.features import registry_version
    from cfb_system_maker.upcoming import enrich_upcoming

    _accumulation_raw(tmp_path, lines_cover_full_season=True)
    enrich_upcoming(tmp_path, 2026, [_target_record()])

    payload = json.loads(upcoming_features_path(tmp_path).read_text(encoding="utf-8"))
    assert payload["_meta"]["registry_version"] == registry_version()
    assert payload["_meta"]["game_count"] == 1
    assert set(load_features_from(upcoming_features_path(tmp_path))) == {3005}


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


def test_v1_over_prob_null_when_no_fit_cached(tmp_path):
    games = [GameRecord(1, 2023, 1, "Alpha", "Beta", None, None, 21, 14, "consensus", -3.5, 45.5)]
    features = enrich_games(tmp_path, games)
    assert features["1"]["v1_over_prob"] is None


def test_v1_over_prob_populated_from_cached_fit(tmp_path):
    from cfb_system_maker.v1_model import V1Fit, save_v1_fit

    fit = V1Fit(tobit_dog_sigma=14.0, tobit_fav_sigma=14.0, probit_const=0.0, probit_slope=0.05, n_games=1000)
    save_v1_fit(tmp_path, fit)

    games = [
        GameRecord(1, 2023, 1, "Alpha", "Beta", None, None, None, None, "consensus", -3.5, 45.5),
        GameRecord(2, 2023, 1, "Gamma", "Delta", None, None, None, None, "consensus", 0, 50.0),
    ]
    features = enrich_games(tmp_path, games)
    assert isinstance(features["1"]["v1_over_prob"], float)
    assert 0.0 <= features["1"]["v1_over_prob"] <= 1.0
    # pick'em (spread == 0) is skipped, same as the fit-time filter
    assert features["2"]["v1_over_prob"] is None


def test_coach_style_cluster_from_embedded_mapping(tmp_path):
    season = 2023
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / f"coaches_{season}.json").write_text(
        json.dumps(
            [
                {
                    "firstName": "Kirby",
                    "lastName": "Smart",
                    "seasons": [{"year": season, "school": "Alpha", "games": 14}],
                },
                {
                    "firstName": "Totally",
                    "lastName": "Unknown",
                    "seasons": [{"year": season, "school": "Beta", "games": 12}],
                },
            ]
        ),
        encoding="utf-8",
    )

    games = [GameRecord(1, season, 1, "Alpha", "Beta", None, None, 21, 14, "consensus", -3.5, None)]
    features = enrich_games(tmp_path, games)
    assert features["1"]["home_coach_style_cluster"] == "bend_dont_break"
    assert features["1"]["away_coach_style_cluster"] is None
