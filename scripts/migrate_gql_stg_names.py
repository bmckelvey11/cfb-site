"""One-shot migration: move stg.gql_<x> tables into stg_gql.<x>.

DuckDB has no `ALTER TABLE ... SET SCHEMA` (verified 1.5.2), so each table is a
`CREATE TABLE ... AS SELECT * FROM ...` copy followed by a `DROP TABLE`, not a
metadata rename. Resumable: a table already present at its destination is skipped,
so a partial prior run (or a re-run after this script itself failed partway) is safe.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import duckdb

from cfb_system_maker.graphql_client import GQL_ENTITY_TO_RAW, GQL_ENTITY_TO_STG


@dataclass(frozen=True)
class MoveReport:
    src_schema: str
    src_name: str
    dest_schema: str
    dest_name: str
    rows: int = 0
    error: str | None = None


def plan_moves(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str, str, str]]:
    """``(src_schema, src_name, dest_schema, dest_name)`` for every table to move.

    Parents come from the mapping (the source of truth for which raw name maps to
    which bare destination). Children are discovered by scanning `stg` for
    `<parent>__%` tables rather than hand-listed, so a new nested column doesn't
    silently strand its child table in `stg`.
    """
    moves: list[tuple[str, str, str, str]] = []
    existing = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'stg'"
        ).fetchall()
    }
    for entity, raw_name in GQL_ENTITY_TO_RAW.items():
        dest_name = GQL_ENTITY_TO_STG[entity]
        if raw_name in existing:
            moves.append(("stg", raw_name, "stg_gql", dest_name))
        # Child scan is independent of the parent's presence in `stg`: a prior run may
        # have moved the parent and then died before reaching its children, which
        # would otherwise strand them in `stg` forever on every future re-run.
        prefix = raw_name + "__"
        for child in sorted(name for name in existing if name.startswith(prefix)):
            dest_child = dest_name + "__" + child[len(prefix):]
            moves.append(("stg", child, "stg_gql", dest_child))
    return moves


def migrate(con: duckdb.DuckDBPyConnection) -> list[MoveReport]:
    con.execute("CREATE SCHEMA IF NOT EXISTS stg_gql")
    reports: list[MoveReport] = []
    for src_schema, src_name, dest_schema, dest_name in plan_moves(con):
        already_moved = con.execute(
            "SELECT COUNT(*) FROM duckdb_tables()"
            f" WHERE schema_name = '{dest_schema}' AND table_name = '{dest_name}'"
        ).fetchone()[0]
        if already_moved:
            # plan_moves() only includes an entry when the source is still present in
            # `stg`, so reaching this branch means BOTH the source and destination exist
            # at once -- a resumed run would have already dropped the source once moved.
            # That state means something is wrong (e.g. a rebuild regenerated the source
            # while a prior partial migration already created the destination from an
            # older copy). Report it as a failure rather than silently folding it into
            # "moved" -- never overwrite the destination and never abandon the source.
            reports.append(
                MoveReport(
                    src_schema, src_name, dest_schema, dest_name,
                    error=(
                        f"destination {dest_schema}.{dest_name} already exists but "
                        f"source {src_schema}.{src_name} is still present -- "
                        "not overwriting; investigate before re-running"
                    ),
                )
            )
            continue
        try:
            con.execute("BEGIN TRANSACTION")
            con.execute(
                f'CREATE TABLE "{dest_schema}"."{dest_name}" AS'
                f' SELECT * FROM "{src_schema}"."{src_name}"'
            )
            con.execute(f'DROP TABLE "{src_schema}"."{src_name}"')
            con.execute(
                "UPDATE meta.load_report SET schema = ?, name = ?"
                " WHERE schema = ? AND name = ?",
                [dest_schema, dest_name, src_schema, src_name],
            )
            con.execute("COMMIT")
            rows = con.execute(
                f'SELECT COUNT(*) FROM "{dest_schema}"."{dest_name}"'
            ).fetchone()[0]
            reports.append(MoveReport(src_schema, src_name, dest_schema, dest_name, rows=int(rows)))
        except Exception as exc:
            con.execute("ROLLBACK")
            detail = str(exc).split("\n", 1)[0]
            reports.append(
                MoveReport(
                    src_schema, src_name, dest_schema, dest_name,
                    error=f"{type(exc).__name__}: {detail}",
                )
            )
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to cfb.duckdb")
    parser.add_argument("--yes", action="store_true", help="Apply the migration (default: dry run)")
    args = parser.parse_args()

    con = duckdb.connect(args.db, read_only=not args.yes)
    moves = plan_moves(con)
    print(f"{len(moves)} tables to move (stg -> stg_gql):")
    for src_schema, src_name, dest_schema, dest_name in moves:
        print(f"  {src_schema}.{src_name} -> {dest_schema}.{dest_name}")
    if not args.yes:
        print("\nDry run only. Re-run with --yes to apply.")
        con.close()
        return 0
    reports = migrate(con)
    con.close()
    failed = [r for r in reports if r.error]
    print(f"\n{len(reports) - len(failed)} moved, {len(failed)} failed")
    for r in failed:
        print(f"  FAILED {r.src_schema}.{r.src_name}: {r.error}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
