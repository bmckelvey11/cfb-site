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
