import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "refresh_cfbd",
    Path(__file__).resolve().parents[1] / "scripts" / "refresh_cfbd.py",
)
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)


def test_current_season_keeps_bowls_with_the_prior_year():
    """Jan-Jun belongs to the season that started the previous July."""
    import datetime

    jan = datetime.datetime(2027, 1, 12, tzinfo=datetime.timezone.utc)
    sep = datetime.datetime(2026, 9, 8, tzinfo=datetime.timezone.utc)
    assert rc._current_season(jan) == 2026
    assert rc._current_season(sep) == 2026


def test_flatten_failure_does_not_cost_the_rebuild(tmp_path, monkeypatch, capsys):
    """A locked CSV (Excel takes an exclusive lock) must not abort the refresh --
    the rebuild is the expensive half and the CSV already on disk still loads."""
    (tmp_path / "history_1.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(rc, "AN_HISTORY_DIR", tmp_path)
    monkeypatch.setattr(rc, "an_collect", lambda files: ([], {"files": len(files)}))

    def locked(rows):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(rc, "an_write", locked)

    rc._flatten_actionnetwork()  # must not raise

    out = capsys.readouterr()
    assert "rebuilding against the CSV already on disk" in out.out
    assert "PermissionError" in out.err


def test_flatten_skips_when_nothing_was_ever_scraped(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(rc, "AN_HISTORY_DIR", tmp_path)

    def unreachable(files):
        raise AssertionError("must not walk an empty directory")

    monkeypatch.setattr(rc, "an_collect", unreachable)

    rc._flatten_actionnetwork()

    assert "nothing to flatten" in capsys.readouterr().out
