import random
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

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


def test_search_command_save_flag_persists_top_finalist_with_search_provenance(tmp_path, capsys):
    save_processed_games(tmp_path, _search_fixture_games())
    main(["enrich", "--data-dir", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(
        [
            "search", "--data-dir", str(tmp_path),
            "--holdout-season", "2024", "--min-decided-bets", "30",
            "--save", "found-it",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Saved system as found-it" in captured

    from cfb_system_maker.storage import load_saved_system

    loaded = load_saved_system("found-it", tmp_path)
    assert loaded.source == "search"
    assert loaded.search_candidates_tested is not None
    assert loaded.search_candidates_tested > 0


def test_search_command_save_flag_errors_when_no_finalists(tmp_path, capsys):
    save_processed_games(tmp_path, _search_fixture_games())
    main(["enrich", "--data-dir", str(tmp_path)])
    capsys.readouterr()

    # min_decided_bets set impossibly high -> zero finalists survive.
    exit_code = main(
        [
            "search", "--data-dir", str(tmp_path),
            "--holdout-season", "2024", "--min-decided-bets", "1000000",
            "--save", "nothing-found",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error=nothing_to_save" in captured.err


def test_search_command_save_run_flag_persists_full_finalist_list(tmp_path, capsys):
    save_processed_games(tmp_path, _search_fixture_games())
    main(["enrich", "--data-dir", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(
        [
            "search", "--data-dir", str(tmp_path),
            "--holdout-season", "2024", "--min-decided-bets", "30",
            "--save-run", "my-run",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Saved run as my-run" in captured

    from cfb_system_maker.storage import load_search_run

    run = load_search_run("my-run", tmp_path)
    assert run.candidates_tested > 0
    assert run.finalists_graded == len(run.finalists)
    assert run.effective_params["beam_width"] == 100
    if run.finalists:
        assert run.finalists[0].corrected_p >= 0.0


def test_web_command_defaults_to_production_server(monkeypatch, tmp_path):
    monkeypatch.delenv("CFB_WEB_HOST", raising=False)
    served = {}

    def fake_serve(app, host, port, threads):
        served.update(host=host, port=port, threads=threads)

    monkeypatch.setattr("waitress.serve", fake_serve)

    exit_code = main(["web", "--data-dir", str(tmp_path), "--port", "5000"])

    assert exit_code == 0
    assert served == {"host": "127.0.0.1", "port": 5000, "threads": 8}


def test_web_command_debug_uses_flask_dev_server(monkeypatch, tmp_path):
    monkeypatch.delenv("CFB_WEB_HOST", raising=False)
    ran = {}

    def fake_run(self, host, port, debug):
        ran.update(host=host, port=port, debug=debug)

    monkeypatch.setattr("flask.Flask.run", fake_run)

    exit_code = main(["web", "--data-dir", str(tmp_path), "--port", "5000", "--debug"])

    assert exit_code == 0
    assert ran == {"host": "127.0.0.1", "port": 5000, "debug": True}


def test_web_command_reads_env_defaults(monkeypatch, tmp_path):
    # _web() does a LOCAL `from cfb_system_maker.web import create_app` inside the
    # function body, re-executed on every call -- so patching the name on the
    # source module (cfb_system_maker.web.create_app) works, since the local
    # import re-binds from that module's current attribute at call time. A patch
    # on `cfb_system_maker.cli.create_app` would not: no such module-level name
    # exists there to intercept.
    created = {}

    def fake_create_app(data_dir):
        created["data_dir"] = data_dir
        import flask

        return flask.Flask("fake")

    served = {}

    def fake_serve(app, host, port, threads):
        served.update(host=host, port=port, threads=threads)

    monkeypatch.setattr("cfb_system_maker.web.create_app", fake_create_app)
    monkeypatch.setattr("waitress.serve", fake_serve)
    # CFB_DATA_DIR is marker-checked like CFB_DATA_ROOT, so the override target has
    # to be an initialized root -- see test_web_command_rejects_unmarked_data_dir.
    (tmp_path / ".cfb-data-root").touch()
    monkeypatch.setenv("CFB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CFB_WEB_HOST", "0.0.0.0")
    monkeypatch.setenv("CFB_WEB_PORT", "8123")

    exit_code = main(["web"])

    assert exit_code == 0
    assert created["data_dir"] == str(tmp_path)
    assert served == {"host": "0.0.0.0", "port": 8123, "threads": 8}

    # Explicit CLI flags still win over env vars (this task's Interfaces contract),
    # with the same env vars from above still set -- a real conflict, not just the
    # absence of one.
    created.clear()
    served.clear()
    exit_code = main(["web", "--data-dir", "cli-dir", "--host", "1.2.3.4", "--port", "6001"])

    assert exit_code == 0
    assert created["data_dir"] == "cli-dir"
    assert served == {"host": "1.2.3.4", "port": 6001, "threads": 8}


def test_web_command_rejects_unmarked_data_dir(monkeypatch, tmp_path):
    """An unmarked CFB_DATA_DIR must fail loudly, not serve an empty warehouse.

    This is the override's half of the marker contract: a directory that merely
    exists is not a data root, and the web app silently reading one would show an
    empty board rather than saying anything was wrong.
    """
    monkeypatch.setenv("CFB_DATA_DIR", str(tmp_path))  # exists, but no marker

    with pytest.raises(SystemExit, match="not an initialized CFB data root"):
        main(["web"])


def test_betlog_import_command_reports_summary(tmp_path, monkeypatch, capsys):
    from cfb_system_maker import cli

    def fake_import(csv_path, data_dir):
        from cfb_system_maker.betlog import ImportSummary
        return ImportSummary(
            total_rows=580, in_scope=344, already_imported=0,
            newly_imported=344, matched=338, unmatched=["2023-09-01 XYZ @ ABC"],
            malformed=15,
        )

    monkeypatch.setattr("cfb_system_maker.cli.import_betlog", fake_import)
    exit_code = cli.main(["betlog", "import", "--csv", "fake.csv", "--data-dir", str(tmp_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "344" in captured.out
    assert "338" in captured.out


def test_search_command_save_run_flag_persists_even_with_zero_finalists(tmp_path, capsys, monkeypatch):
    save_processed_games(tmp_path, _search_fixture_games())
    main(["enrich", "--data-dir", str(tmp_path)])
    capsys.readouterr()

    import cfb_system_maker.cli as cli_module

    def _empty_grade_finalists(beam_result, holdout_games, holdout_feature_map, *, alpha=0.05, american_odds=-110):
        from cfb_system_maker.search import FinalistGradingResult
        return FinalistGradingResult(finalists=(), candidates_tested=beam_result.candidates_tested, finalists_graded=0)

    monkeypatch.setattr(cli_module, "grade_finalists", _empty_grade_finalists)

    exit_code = main(
        [
            "search", "--data-dir", str(tmp_path),
            "--holdout-season", "2024", "--min-decided-bets", "30",
            "--save-run", "empty-run",
        ]
    )
    assert exit_code == 0

    from cfb_system_maker.storage import load_search_run

    run = load_search_run("empty-run", tmp_path)
    assert run.finalists_graded == 0
    assert run.finalists == ()
