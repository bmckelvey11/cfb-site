"""A second `build_duckdb` in another process must refuse, not clobber the first.

Every rebuild stages at the one fixed path `<db>.building` and opens by unlinking whatever
is there, so two overlapping rebuilds delete each other's temp file and then race on the
final `replace`. The atomic replace is what made this easy to miss -- it makes *one* rebuild
safe and says nothing about two. An hourly scheduled refresh plus a hand-run is all it takes;
a refresh is ~26 minutes.

**The lock is cross-process only.** DuckDB shares one instance per file inside a process, so
a same-process second `connect` succeeds and is *not* refused. That is the right scope --
the hazard is a scheduled run against a hand-run, never one process racing itself -- but it
means the refusal has to be tested through a real subprocess, which is what the first test
here does. An in-process `pytest.raises` would pass for the wrong reason.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import duckdb
import pytest

from cfb_system_maker.duckdb_load import (
    RebuildInProgress,
    _exclusive_rebuild,
    build_duckdb,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _rebuild_in_another_process(tmp_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {str(REPO_ROOT)!r})
            from cfb_system_maker.duckdb_load import RebuildInProgress, build_duckdb
            try:
                build_duckdb({str(tmp_path)!r}, {str(tmp_path / "cfb.duckdb")!r})
            except RebuildInProgress as exc:
                print(exc)
                sys.exit(3)
            sys.exit(0)
        """)],
        capture_output=True, text=True, timeout=120,
    )


def test_a_second_process_refuses_and_leaves_the_first_staged_file_alone(tmp_path):
    """The specific damage: the loser used to `unlink()` the winner's `.building`."""
    db = tmp_path / "cfb.duckdb"
    building = tmp_path / "cfb.duckdb.building"
    with _exclusive_rebuild(db):
        building.write_text("first run's work in progress", encoding="utf-8")
        done = _rebuild_in_another_process(tmp_path)
    assert done.returncode == 3, f"expected a refusal, got {done.returncode}: {done.stderr}"
    assert ".lock" in done.stdout, "the message must name what to wait on"
    assert building.read_text(encoding="utf-8") == "first run's work in progress", \
        "the refused rebuild destroyed the running one's staged file"


def test_a_second_process_succeeds_once_the_lock_is_released(tmp_path):
    """Sequential rebuilds are ordinary; only overlapping ones are refused."""
    db = tmp_path / "cfb.duckdb"
    with _exclusive_rebuild(db):
        pass
    done = _rebuild_in_another_process(tmp_path)
    assert done.returncode == 0, done.stderr


def test_the_lock_is_released_when_the_rebuild_raises(tmp_path):
    """A crashed rebuild must not strand the lock -- that is why it is a held file handle
    and not a pid file: there is no staleness case to get wrong."""
    db = tmp_path / "cfb.duckdb"
    with pytest.raises(ValueError):
        with _exclusive_rebuild(db):
            raise ValueError("boom")
    assert _rebuild_in_another_process(tmp_path).returncode == 0


def test_stale_building_debris_is_cleared_under_the_lock(tmp_path):
    """Holding the lock means an existing `.building` is debris from a crash, not a rebuild
    in flight -- so clearing it is safe, which it was not before."""
    db = tmp_path / "cfb.duckdb"
    (tmp_path / "cfb.duckdb.building").write_text("debris", encoding="utf-8")
    out, _ = build_duckdb(tmp_path, db)
    assert out == db
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM duckdb_schemas()").fetchone()[0] > 0
    finally:
        con.close()


# ----------------------------------------------------------------- memory limit


def test_every_loader_connection_gets_the_memory_limit():
    """DuckDB defaults `memory_limit` to ~80% of RAM, and on 2026-09-11 that killed a rebuild
    on a 15.4 GB machine with 2.9 GB free: `stg.an_scoreboard` died with an allocation
    failure, its children were never built, and `core.fact_game_line` lost 8,587 rows. The
    two settings that *were* present -- threads and preserve_insertion_order -- are DuckDB's
    other two OOM recommendations and were not enough on their own.

    Asserted against the source because the failure mode is a call site that forgets one of
    the three, which is exactly how the limit stayed at its default at all four of them.
    """
    source = (REPO_ROOT / "cfb_system_maker" / "duckdb_load.py").read_text(encoding="utf-8")
    assert "SET memory_limit" in source
    assert source.count('con.execute("SET threads = 1")') == 1, \
        "tuning belongs in _tune(); a second copy is a site that can drift"
    assert source.count("_tune(con)") == 4, \
        "every loader connection must be tuned, not just the rebuild's"


def test_the_memory_limit_actually_applies(tmp_path):
    """The setting has to reach the connection, not just the source file."""
    import duckdb as _d

    from cfb_system_maker.duckdb_load import _tune
    con = _d.connect(str(tmp_path / "t.duckdb"))
    try:
        _tune(con)
        limit = con.execute(
            "SELECT value FROM duckdb_settings() WHERE name = 'memory_limit'"
        ).fetchone()[0]
        # DuckDB normalises '4GB' to '3.7 GiB', so assert the invariant rather than the
        # string: the limit must be far below the ~80%-of-RAM default that caused the OOM.
        gib = float(limit.split()[0])
        assert "GiB" in limit and gib <= 4.0, f"limit is not conservative: {limit}"
    finally:
        con.close()


def test_the_memory_limit_is_overridable(tmp_path, monkeypatch):
    """A machine with more headroom should not be pinned to the conservative default."""
    monkeypatch.setenv("CFB_DUCKDB_MEMORY_LIMIT", "1GB")
    import importlib

    import cfb_system_maker.duckdb_load as dl
    importlib.reload(dl)
    try:
        assert dl._MEMORY_LIMIT == "1GB"
    finally:
        monkeypatch.delenv("CFB_DUCKDB_MEMORY_LIMIT")
        importlib.reload(dl)
