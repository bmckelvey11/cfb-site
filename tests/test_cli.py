from datetime import datetime, timezone
from types import SimpleNamespace

from cfb_system_maker.cli import main


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
