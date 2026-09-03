"""Bring the live warehouse to match the code without a 4.9 GB rebuild.

Two changes land here, both of which a full ``duckdb --explode`` would produce
from scratch (see ``docs/warehouse-schema-recommendation.md`` §7 and §8):

1. **Action Network** -- rename the three roots ``actionnetwork_*`` -> ``an_*``
   in ``raw`` and ``stg``, drop the ten generic
   ``actionnetwork_scoreboard__*`` children, and build the three hand-written
   ones (``an_market``, ``an_team``, ``an_linescore``).
2. **Massey** -- load ``processed/massey/*.csv`` into ``stg``. Scraped since
   August and never in the warehouse at all.

Renames are metadata-only ``ALTER TABLE ... RENAME TO``; nothing crosses a
schema. Resumable, and each step is skipped when it has already been applied.

DuckDB takes an exclusive lock, so **every other connection must be closed** --
including a ``duckdb cfb.duckdb -readonly`` shell, which still blocks a writer.

    python scripts/migrate_live_warehouse.py            # dry run
    python scripts/migrate_live_warehouse.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cfb_paths  # noqa: E402
from cfb_system_maker.duckdb_load import _MASSEY_TABLES, explode_an_children  # noqa: E402

AN_RENAMES = {
    "actionnetwork_scoreboard": "an_scoreboard",
    "actionnetwork_history": "an_history",
    "actionnetwork_odds": "an_odds",
}


def tables(con: duckdb.DuckDBPyConnection, schema: str) -> set[str]:
    return {
        row[0]
        for row in con.execute(
            f"SELECT table_name FROM duckdb_tables() WHERE schema_name = '{schema}'"
        ).fetchall()
    }


def plan_an(con: duckdb.DuckDBPyConnection) -> tuple[list[tuple[str, str, str]], list[str]]:
    """``(schema, old, new)`` renames, and the ``stg`` children to drop."""
    renames = []
    for schema in ("raw", "stg"):
        have = tables(con, schema)
        for old, new in AN_RENAMES.items():
            if old in have and new not in have:
                renames.append((schema, old, new))
    drops = sorted(
        t for t in tables(con, "stg") if t.startswith("actionnetwork_scoreboard__")
    )
    return renames, drops


def plan_massey(root: Path) -> list[tuple[str, Path]]:
    massey = root / "processed" / "massey"
    return [
        (name, massey / f"{name}.csv")
        for name in _MASSEY_TABLES
        if (massey / f"{name}.csv").is_file()
    ]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(cfb_paths.DB_PATH))
    p.add_argument("--root", default=str(cfb_paths.DATA_ROOT))
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()

    massey = plan_massey(Path(a.root))
    con = duckdb.connect(a.db, read_only=not a.apply)
    try:
        renames, drops = plan_an(con)
        for schema, old, new in renames:
            print(f"  rename {schema}.{old}  ->  {schema}.{new}")
        for name in drops:
            print(f"  drop   stg.{name}")
        for name, path in massey:
            print(f"  load   stg.{name}  <-  {path.name} ({path.stat().st_size / 1e6:.0f} MB)")
        if not a.apply:
            print(
                f"\n{len(renames)} rename(s), {len(drops)} drop(s),"
                f" {len(massey)} load(s). Pass --apply."
            )
            return 0

        for schema, old, new in renames:
            con.execute(f'ALTER TABLE {schema}."{old}" RENAME TO "{new}"')
        for name in drops:
            con.execute(f'DROP TABLE stg."{name}"')
        for report in explode_an_children(con):
            print(f"  build  stg.{report.name}  {report.error or f'{report.rows:,} rows'}")
        con.execute("CREATE SCHEMA IF NOT EXISTS stg")
        for name, path in massey:
            con.execute(f'DROP TABLE IF EXISTS stg."{name}"')
            con.execute(
                f'CREATE TABLE stg."{name}" AS'
                f" SELECT * FROM read_csv_auto('{path.as_posix()}')"
            )
            rows = con.execute(f'SELECT COUNT(*) FROM stg."{name}"').fetchone()[0]
            print(f"  load   stg.{name}  {rows:,} rows")
        con.execute("CHECKPOINT")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
