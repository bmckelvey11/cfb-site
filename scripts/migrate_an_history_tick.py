"""Retype the live ``stg.an_history_tick`` to the schema the loader now pins.

``stg.an_history_tick`` was created by ``read_csv_auto``, which sniffed the id
columns as integers. ``stg.an_history`` and ``stg.an_market`` come out of
``_AN_OFFERING_COLS``, where ``market_id``/``outcome_id`` are extracted as
strings and ``book_id`` is cast to INTEGER. Joining the tick series to either of
them therefore needed a cast on one side:

    book_id     BIGINT  ->  INTEGER
    market_id   BIGINT  ->  VARCHAR
    outcome_id  BIGINT  ->  VARCHAR

``duckdb_load._AN_TICK_COLUMNS`` now pins those types at load time, so a full
rebuild produces this shape from scratch; this script is only for the warehouse
already on disk. Idempotent -- it reads the current types and alters only the
columns that still differ, so a second run is a no-op.

DuckDB takes an exclusive lock, so **every other connection must be closed**,
including a ``duckdb cfb.duckdb -readonly`` shell.

    python scripts/migrate_an_history_tick.py            # dry run
    python scripts/migrate_an_history_tick.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cfb_paths  # noqa: E402
from cfb_system_maker.duckdb_load import _AN_TICK_COLUMNS, _AN_TICK_TABLE  # noqa: E402

TABLE = f"stg.{_AN_TICK_TABLE}"


def plan(current: dict[str, str]) -> list[tuple[str, str, str]]:
    """``(column, from, to)`` for every column whose live type has drifted.

    Columns the live table does not have are not added here -- a shape that far
    from the loader's wants the rebuild, not an ALTER.
    """
    return [
        (name, current[name], want)
        for name, want in _AN_TICK_COLUMNS.items()
        if name in current and current[name] != want
    ]


def live_types(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    rows = con.execute(
        "SELECT column_name, data_type FROM duckdb_columns()"
        f" WHERE schema_name = 'stg' AND table_name = '{_AN_TICK_TABLE}'"
    ).fetchall()
    return {name: dtype for name, dtype in rows}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--db", default=str(cfb_paths.DB_PATH))
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()

    con = duckdb.connect(a.db, read_only=not a.apply)
    try:
        current = live_types(con)
        if not current:
            print(f"{TABLE} does not exist; nothing to migrate")
            return 0
        changes = plan(current)
        for name, was, want in changes:
            print(f"  alter  {TABLE}.{name}  {was} -> {want}")
        if not changes:
            print(f"{TABLE} already matches the pinned schema")
            return 0
        if not a.apply:
            print(f"\n{len(changes)} column(s) to retype. Pass --apply.")
            return 0

        for name, _, want in changes:
            con.execute(f'ALTER TABLE {TABLE} ALTER "{name}" TYPE {want}')
        con.execute("CHECKPOINT")
        rows = con.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
        print(f"\n{TABLE}: {len(changes)} column(s) retyped, {rows:,} rows intact")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
