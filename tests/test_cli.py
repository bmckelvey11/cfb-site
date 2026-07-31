import random
from datetime import datetime, timezone
from types import SimpleNamespace

from cfb_system_maker.cli import main
from cfb_system_maker.models import GameRecord
from cfb_system_maker.storage import save_processed_games


def _fake_cfbd():
    """Always-current single-week fake, so the test is independent of the clock."""

    class _Config:
        def __init__(self, access_token=None):
            self.access_token = access_token

    class _Client:
        def __init__(self, configuration):
            self.configuration = configuration

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class _GamesApi:
        def __init__(self, client):
            pass

        def get_calendar(self, year=None):
            return [
                {
                    "season": year,
                    "week": 1,
                    "seasonType": "regular",
                    "startDate": datetime(1900, 1, 1, tzinfo=timezone.utc),
                    "endDate": datetime(2999, 1, 1, tzinfo=timezone.utc),
                }
            ]

        def get_games(self, year=None, week=None, season_type=None, **rest):
            return [
                {
                    "id": 7001,
                    "season": year,
                    "week": 1,
                    "seasonType": "regular",
                    "startDate": datetime(year, 9, 5, 19, tzinfo=timezone.utc),
                    "startTimeTBD": False,
                    "completed": False,
                    "homeTeam": "Alpha",
                    "awayTeam": "Beta",
                    "homeConference": "SEC",
                    "awayConference": "Big Ten",
                    "homePoints": None,
                    "awayPoints": None,
                }
            ]

    class _BettingApi:
        def __init__(self, client):
            pass

        def get_lines(self, year=None, week=None, season_type=None, provider=None, **rest):
            return [{"id": 7001, "lines": [{"provider": "DraftKings", "spread": -7.0, "overUnder": 52.5}]}]

    return SimpleNamespace(
        Configuration=_Config,
        ApiClient=_Client,
        GamesApi=_GamesApi,
        BettingApi=_BettingApi,
    )


def test_upcoming_command_writes_upcoming_files_and_not_games_csv(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("cfb_system_maker.upcoming._load_cfbd_module", _fake_cfbd)
    monkeypatch.setattr("cfb_system_maker.upcoming.find_cfbd_token", lambda *a, **k: "test-token")

    exit_code = main(["upcoming", "--data-dir", str(tmp_path)])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "week 1" in captured
    assert "test-token" not in captured
    assert (tmp_path / "processed" / "upcoming.csv").exists()
    assert (tmp_path / "processed" / "upcoming_meta.json").exists()
    # D-01: the historical table is out of this command's reach.
    assert not (tmp_path / "processed" / "games.csv").exists()


def test_sample_command_prints_metrics_and_writes_cache(tmp_path, capsys):
    exit_code = main(["sample", "--data-dir", str(tmp_path)])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Home favorites" in captured
    assert "Bets: 2" in captured
    assert "ROI:" in captured
    assert (tmp_path / "raw" / "games_2023.json").exists()
    assert (tmp_path / "raw" / "lines_2023.json").exists()
    assert (tmp_path / "processed" / "games.csv").exists()


def test_backtest_command_accepts_filters(tmp_path, capsys):
    assert main(["sample", "--data-dir", str(tmp_path)]) == 0

    exit_code = main(
        [
            "backtest",
            "--data-dir",
            str(tmp_path),
            "--side",
            "away",
            "--underdog",
            "--min-spread",
            "3",
        ]
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Custom system" in captured
    assert "Bets: 2" in captured


def test_backtest_command_fade_flag_flips_grading(tmp_path, capsys):
    assert main(["sample", "--data-dir", str(tmp_path)]) == 0

    main(["backtest", "--data-dir", str(tmp_path), "--side", "home", "--favorite"])
    normal_output = capsys.readouterr().out

    main(["backtest", "--data-dir", str(tmp_path), "--side", "home", "--favorite", "--fade"])
    faded_output = capsys.readouterr().out

    assert normal_output != faded_output
    assert "Bets: 2" in normal_output
    assert "Bets: 2" in faded_output


def test_backtest_command_prints_per_season_breakdown(tmp_path, capsys):
    assert main(["sample", "--data-dir", str(tmp_path)]) == 0

    exit_code = main(["backtest", "--data-dir", str(tmp_path), "--side", "home", "--favorite"])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Per-season breakdown:" in captured
    assert "Profitable in" in captured


def test_backtest_command_prints_permutation_p_value(tmp_path, capsys):
    assert main(["sample", "--data-dir", str(tmp_path)]) == 0

    exit_code = main(["backtest", "--data-dir", str(tmp_path), "--side", "home", "--favorite"])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Permutation p-value:" in captured


def test_backtest_command_prints_holdout_columns_when_holdout_season_given(tmp_path, capsys):
    assert main(["sample", "--data-dir", str(tmp_path)]) == 0
    capsys.readouterr()  # Clear the sample output

    exit_code = main(
        [
            "backtest", "--data-dir", str(tmp_path),
            "--side", "home", "--favorite",
            "--holdout-season", "2023",
        ]
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Custom system (in-sample)" in captured
    assert "Custom system (holdout)" in captured
    assert captured.count("Bets:") == 2


# --- MVP-005: search CLI command -----------------------------------------------


def _search_fixture_games(n: int = 300, *, home_cover_rate: float = 0.8, seed: int = 1) -> list[GameRecord]:
    rng = random.Random(seed)
    games = []
    for i in range(n):
        season = 2023 if i < n * 2 // 3 else 2024
        home_covers = rng.random() < home_cover_rate
        home_points, away_points = (30, 16) if home_covers else (17, 20)
        games.append(
            GameRecord(
                game_id=i, season=season, week=(i % 12) + 1,
                home_team=f"H{i}", away_team=f"A{i}",
                home_conference="X", away_conference="Y",
                home_points=home_points, away_points=away_points,
                provider="consensus", spread=-7.0, total=45.0,
            )
        )
    return games


def test_search_command_missing_games_csv_errors(tmp_path, capsys):
    exit_code = main(["search", "--data-dir", str(tmp_path), "--holdout-season", "2024"])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error=missing_data" in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_search_command_missing_features_json_errors(tmp_path, capsys):
    save_processed_games(tmp_path, _search_fixture_games())

    exit_code = main(["search", "--data-dir", str(tmp_path), "--holdout-season", "2024"])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error=missing_features" in captured.err
    assert "enrich" in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_search_command_requires_holdout_season(tmp_path, capsys):
    save_processed_games(tmp_path, _search_fixture_games())
    main(["enrich", "--data-dir", str(tmp_path)])
    capsys.readouterr()

    try:
        main(["search", "--data-dir", str(tmp_path)])
    except SystemExit as exc:
        assert exc.code != 0
    else:
        raise AssertionError("expected argparse to reject a missing --holdout-season")


def test_search_command_unknown_holdout_season_errors(tmp_path, capsys):
    save_processed_games(tmp_path, _search_fixture_games())
    main(["enrich", "--data-dir", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(["search", "--data-dir", str(tmp_path), "--holdout-season", "1999"])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error=unknown_holdout_season" in captured.err


def test_search_command_season_scope_excluding_holdout_errors(tmp_path, capsys):
    save_processed_games(tmp_path, _search_fixture_games())
    main(["enrich", "--data-dir", str(tmp_path)])
    capsys.readouterr()

    # --season scope excludes the holdout season entirely -> refuse, don't silently
    # proceed with zero holdout games (mirror of the zero-in-sample-seasons case).
    exit_code = main(
        ["search", "--data-dir", str(tmp_path), "--holdout-season", "2024", "--season", "2023"]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error=empty_holdout" in captured.err


def test_search_command_unknown_season_scope_value_errors(tmp_path, capsys):
    save_processed_games(tmp_path, _search_fixture_games())
    main(["enrich", "--data-dir", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(
        ["search", "--data-dir", str(tmp_path), "--holdout-season", "2024", "--season", "2023", "--season", "1999"]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error=unknown_season" in captured.err


def test_search_command_rejects_non_positive_search_params(tmp_path, capsys):
    save_processed_games(tmp_path, _search_fixture_games())
    main(["enrich", "--data-dir", str(tmp_path)])
    capsys.readouterr()

    for flag in ("--max-filters", "--beam-width", "--top-k", "--min-decided-bets"):
        exit_code = main(["search", "--data-dir", str(tmp_path), "--holdout-season", "2024", flag, "0"])
        captured = capsys.readouterr()
        assert exit_code != 0, f"{flag} 0 should be rejected"
        assert "error=invalid_search_params" in captured.err


def test_search_command_output_includes_expected_fields(tmp_path, capsys):
    save_processed_games(tmp_path, _search_fixture_games())
    main(["enrich", "--data-dir", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(
        ["search", "--data-dir", str(tmp_path), "--holdout-season", "2024", "--min-decided-bets", "30"]
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "beam_width=100" in captured
    assert "top_k=20" in captured
    assert "min_decided_bets=30" in captured
    assert "alpha=0.05" in captured
    assert "search_candidates_tested=" in captured
    assert "finalists_graded=" in captured
    assert "raw_p=" in captured
    assert "corrected_p=" in captured
    assert "bh_significant=" in captured


def test_search_command_byte_identical_repeat_run(tmp_path, capsys):
    save_processed_games(tmp_path, _search_fixture_games())
    main(["enrich", "--data-dir", str(tmp_path)])
    capsys.readouterr()

    args = ["search", "--data-dir", str(tmp_path), "--holdout-season", "2024", "--min-decided-bets", "30"]
    main(args)
    first = capsys.readouterr().out
    main(args)
    second = capsys.readouterr().out

    assert first == second
    assert len(first) > 0
