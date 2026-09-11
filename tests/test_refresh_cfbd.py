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


# ------------------------------------------------------------------ graphql dump re-pull

from cfb_system_maker.graphql_client import GqlReport  # noqa: E402


def _gql_env(tmp_path, monkeypatch, existing_rows):
    """A live `data/graphql/game.json` with `existing_rows` rows, and a staging root."""
    import cfb_paths

    live = tmp_path / "graphql"
    live.mkdir()
    (live / "game.json").write_text(
        "[" + ", ".join('{"id": %d}' % i for i in range(existing_rows)) + "]",
        encoding="utf-8",
    )
    monkeypatch.setattr(cfb_paths, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(rc.cfb_paths, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(rc, "_GQL_REFRESH_TABLES", ("game",))
    return live / "game.json"


def _fake_scrape(rows):
    """Stand in for `graphql_scrape`: writes `rows` rows where the real one would."""

    def scrape(*, tables, data_dir, token):
        staged = Path(data_dir) / "graphql"
        staged.mkdir(parents=True, exist_ok=True)
        (staged / f"{tables[0]}.json").write_text(
            "[" + ", ".join('{"id": %d}' % i for i in range(rows)) + "]",
            encoding="utf-8",
        )
        return [GqlReport(tables[0], rows, 1)]

    return scrape


def test_short_pull_keeps_the_dump_already_on_disk(tmp_path, monkeypatch, capsys):
    """The failure the guard exists for is the quiet one.

    A pull that raises is already safe -- `_write` runs only after `_paginate` returns, so
    the staged file never appears. A pull that returns 5,000 rows instead of 112,675 and
    reports success is the one that would replace `game.json` with a truncated copy, and
    nothing downstream would say so: the rebuild would load it, `core` would shrink, and the
    next audit would read it as CFBD losing rows rather than as a bad read.
    """
    live = _gql_env(tmp_path, monkeypatch, existing_rows=1000)
    monkeypatch.setattr(rc, "graphql_scrape", _fake_scrape(500))

    rc._pull_graphql("token")

    assert rc._json_rows(live) == 1000, "a short pull must not replace the live dump"
    assert "SHORT READ" in capsys.readouterr().err
    assert not (tmp_path / ".graphql-pull" / "graphql" / "game.json").exists(), \
        "the rejected pull is cleaned up, not left to be mistaken for a good one"


def test_a_full_pull_replaces_the_dump(tmp_path, monkeypatch):
    """The ordinary path: both tables are append-mostly, so the count grows."""
    live = _gql_env(tmp_path, monkeypatch, existing_rows=1000)
    monkeypatch.setattr(rc, "graphql_scrape", _fake_scrape(1003))

    rc._pull_graphql("token")

    assert rc._json_rows(live) == 1003


def test_a_small_real_shrink_is_allowed_through(tmp_path, monkeypatch):
    """CFBD does remove rows -- it dropped game 401866625 outright on 2026-09-11. The guard
    is sized to let that through and stop a truncation, so it must not fire on a few rows."""
    live = _gql_env(tmp_path, monkeypatch, existing_rows=1000)
    monkeypatch.setattr(rc, "graphql_scrape", _fake_scrape(996))

    rc._pull_graphql("token")

    assert rc._json_rows(live) == 996


def test_pull_never_passes_seasons(monkeypatch):
    """`graphql_scrape` turns `seasons=` into a `where` clause but `_write` replaces the
    whole file, so a season-scoped pull truncates `game.json` from 1869-2026 to one season.
    Pinned because the argument is right there and looks like an optimisation."""
    seen = {}

    def spy(*, tables, data_dir, token, **kwargs):
        seen.update(kwargs)
        return [GqlReport(tables[0], 0, 0, error="stop")]

    monkeypatch.setattr(rc, "graphql_scrape", spy)
    monkeypatch.setattr(rc, "_GQL_REFRESH_TABLES", ("game",))
    rc._pull_graphql("token")
    assert "seasons" not in seen
