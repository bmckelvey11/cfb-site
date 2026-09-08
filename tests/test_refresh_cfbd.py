import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "refresh_cfbd",
    Path(__file__).resolve().parents[1] / "scripts" / "refresh_cfbd.py",
)
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)


def test_current_season_keeps_bowls_with_the_prior_year():
    """Jan-Jun belongs to the season that started the previous July.

    Lives in `cfb_paths` so every script defaulting a `--season` agrees on the
    boundary; asserted from here because this refresh was where the rule started.
    """
    import datetime

    import cfb_paths

    jan = datetime.datetime(2027, 1, 12, tzinfo=datetime.timezone.utc)
    jun = datetime.datetime(2026, 6, 30, tzinfo=datetime.timezone.utc)
    jul = datetime.datetime(2026, 7, 1, tzinfo=datetime.timezone.utc)
    sep = datetime.datetime(2026, 9, 8, tzinfo=datetime.timezone.utc)
    assert cfb_paths.current_season(jan) == 2026
    assert cfb_paths.current_season(jun) == 2025
    assert cfb_paths.current_season(jul) == 2026
    assert cfb_paths.current_season(sep) == 2026


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


def _warehouse(tmp_path, tick_market_id="'164'", history_market_id="'164'"):
    """A two-table warehouse just big enough for the pin check to have an opinion."""
    import duckdb

    from cfb_system_maker.duckdb_load import _AN_TICK_COLUMNS

    db = tmp_path / "cfb.duckdb"
    con = duckdb.connect(str(db))
    cols = ", ".join(f'NULL::{t} AS "{c}"' for c, t in _AN_TICK_COLUMNS.items())
    con.execute(f"CREATE SCHEMA stg; CREATE TABLE stg.an_history_tick AS SELECT {cols}")
    con.execute(
        "UPDATE stg.an_history_tick SET event_id = 500, book_id = 15,"
        f" side = 'home', market_id = {tick_market_id}"
    )
    con.execute(
        "CREATE TABLE stg.an_history AS SELECT 500::BIGINT AS event_id,"
        f" 15::INTEGER AS book_id, 'home' AS side, {history_market_id} AS market_id"
    )
    con.close()
    return db


def test_pin_check_passes_on_a_warehouse_the_loader_would_produce(tmp_path, capsys):
    assert rc._check_an_tick_pin(_warehouse(tmp_path)) is True
    assert "schema : ok" in capsys.readouterr().out


def test_pin_check_fails_loudly_without_claiming_the_warehouse_is_broken(tmp_path, capsys):
    """The rebuild already succeeded; only the check failed. A scheduler log that
    says otherwise sends the next reader after a warehouse that is fine."""
    db = _warehouse(tmp_path, history_market_id="'999'")  # tick orphaned
    assert rc._check_an_tick_pin(db) is False
    out = capsys.readouterr().out
    assert "0/1 tick rows reach stg.an_history" in out
    assert "warehouse is rebuilt and usable" in out
    # check() writes its stale-CSV hint for a command-line reader; this path
    # reflattened first, so the log has to say the hint does not apply here.
    assert "staleness is not the cause" in out
