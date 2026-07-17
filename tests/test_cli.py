from cfb_system_maker.cli import main


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
