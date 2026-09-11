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
