"""The prune guard must fail closed on an empty, partial, or stale local warehouse.

prune_motherduck_orphans classifies by set difference, so a local warehouse that is
empty or wrong does not yield a short orphan list -- it yields a total one, and the
drops are not recoverable from local. These are the negative cases.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import duckdb
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

_spec = importlib.util.spec_from_file_location(
    "prune_motherduck_orphans", REPO / "scripts" / "prune_motherduck_orphans.py"
)
prune = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prune)


def _build(con: duckdb.DuckDBPyConnection, db: str, *, anchors: bool, version):
    """Attach an in-memory-backed database and optionally seed it."""
    for schema in ("core", "stg", "meta"):
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {db}.{schema}")
    if anchors:
        for schema, table in prune.ANCHOR_TABLES:
            con.execute(f"CREATE TABLE {db}.{schema}.{table} (game_id BIGINT)")
    if version is not None:
        con.execute(f"CREATE TABLE {db}.meta.warehouse_version (v VARCHAR)")
        con.execute(f"INSERT INTO {db}.meta.warehouse_version VALUES (?)", [version])


@pytest.fixture
def con(tmp_path):
    c = duckdb.connect()
    c.execute(f"ATTACH '{tmp_path / 'src.duckdb'}' AS src")
    c.execute(f"ATTACH '{tmp_path / 'md.duckdb'}' AS md")
    yield c
    c.close()


def test_empty_local_warehouse_refuses(con):
    _build(con, "src", anchors=False, version=None)
    _build(con, "md", anchors=True, version="323")
    with pytest.raises(SystemExit, match="missing core.fact_game"):
        prune._assert_local_is_the_promoted_warehouse(con)


def test_partial_local_warehouse_refuses(con):
    # core.fact_game present, the rest absent -- the shape a rebuild OOM leaves behind.
    con.execute("CREATE SCHEMA IF NOT EXISTS src.core")
    con.execute("CREATE TABLE src.core.fact_game (game_id BIGINT)")
    _build(con, "md", anchors=True, version="323")
    with pytest.raises(SystemExit, match="fact_game_line"):
        prune._assert_local_is_the_promoted_warehouse(con)


def test_version_mismatch_refuses(con):
    # Complete local warehouse -- passes the anchor gate -- but the wrong one.
    _build(con, "src", anchors=True, version="322")
    _build(con, "md", anchors=True, version="323")
    with pytest.raises(SystemExit, match="warehouse_version differs"):
        prune._assert_local_is_the_promoted_warehouse(con)


def test_missing_version_table_refuses(con):
    _build(con, "src", anchors=True, version=None)
    _build(con, "md", anchors=True, version="323")
    with pytest.raises(SystemExit, match="warehouse_version is missing"):
        prune._assert_local_is_the_promoted_warehouse(con)


def test_matching_warehouse_passes(con):
    _build(con, "src", anchors=True, version="323")
    _build(con, "md", anchors=True, version="323")
    prune._assert_local_is_the_promoted_warehouse(con)  # does not raise
