"""One-shot migration: move every ``stg_gql.<x>`` table into ``stg``, and snake-case the
two camelCase roots. Reverses `migrate_gql_stg_names.py`, which this replaces.

The argument is section 2 of the rationalization plan: a schema called `stg_gql` tags all
38 tables to disambiguate 3, and 28 of them have no counterpart of any spelling to be
disambiguated from. ADR-0002's own reasoning cuts against it -- it rejected a `gql_` prefix
because provenance would be "encoded in a string a reader has to know to interpret" -- and
that objection applies verbatim to a *schema* named after a transport, at coarser
granularity. ADR-0003 records the decision.

Three names stay tagged, and **permanently**, which is the part the plan got wrong: it
predicted the suffix count would reach zero because `predicted_points` would drop its REST
side and `draft_picks`/`calendar` would "merge into core". `predicted_points` failed R6,
and merging a pair into `core` never retires its `stg` sources because `core` is built
*from* them. See docs/stg-gql-collapse-2026-09-10.md.

DuckDB has no `ALTER TABLE ... SET SCHEMA` (verified 1.5.2), so each table is a
`CREATE TABLE ... AS SELECT * FROM ...` copy followed by a `DROP TABLE`. Resumable: a table
already at its destination is skipped, so a partial prior run is safe to re-run.

    python scripts/collapse_stg_gql.py --dry-run
    python scripts/collapse_stg_gql.py --apply

A copy, not a rename, so it needs room for the largest table twice. Refuses to overwrite: a
destination that already exists and is not this migration's own prior output is an error,
not a silent clobber.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from cfb_paths import DATA_ROOT  # noqa: E402
from cfb_system_maker.duckdb_load import _REST_STG_RENAMES  # noqa: E402
from cfb_system_maker.graphql_client import (  # noqa: E402
    GQL_ENTITY_TO_RAW,
    GQL_ENTITY_TO_STG,
)


@dataclass(frozen=True)
class Move:
    src: str
    dest: str
    rows: int = 0
    error: str | None = None


def plan_moves(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str, str, str]]:
    """``(src_schema, src_name, dest_schema, dest_name)``, parents then children.

    Parents come from `GQL_ENTITY_TO_STG`, which is the source of truth for the destination
    name and already carries the `_gql` suffix on the three colliders. Children are
    *scanned* for rather than hand-listed -- a new nested column in a GraphQL payload
    creates a `<parent>__<child>` table nobody edited a list for, and stranding one in a
    schema the rest of the code no longer reads is exactly the silent break this whole
    migration is being careful about.
    """
    moves: list[tuple[str, str, str, str]] = []
    present = {
        (schema, name)
        for schema, name in con.execute(
            "SELECT schema_name, table_name FROM duckdb_tables()"
            " WHERE schema_name IN ('stg', 'stg_gql')"
        ).fetchall()
    }
    gql = {name for schema, name in present if schema == "stg_gql"}

    for entity in GQL_ENTITY_TO_RAW:
        src_name = _snake_of(entity)
        dest_name = GQL_ENTITY_TO_STG[entity]
        if src_name in gql:
            moves.append(("stg_gql", src_name, "stg", dest_name))
        prefix = src_name + "__"
        for child in sorted(n for n in gql if n.startswith(prefix)):
            moves.append(
                ("stg_gql", child, "stg", dest_name + "__" + child[len(prefix):])
            )

    # The two camelCase roots, which are already in `stg` and only change spelling.
    for src_name, dest_name in sorted(_REST_STG_RENAMES.items()):
        if ("stg", src_name) in present:
            moves.append(("stg", src_name, "stg", dest_name))
        prefix = src_name + "__"
        for schema, child in sorted(present):
            if schema == "stg" and child.startswith(prefix):
                moves.append(
                    ("stg", child, "stg", dest_name + "__" + child[len(prefix):])
                )
    return moves


def _snake_of(entity: str) -> str:
    """The `stg_gql` name an entity currently sits under: the un-suffixed snake case.

    Not `GQL_ENTITY_TO_STG[entity]` -- that is the *destination* and now carries `_gql` on
    the colliders, which is precisely the name the source does not have.
    """
    stg = GQL_ENTITY_TO_STG[entity]
    return stg[: -len("_gql")] if stg.endswith("_gql") else stg


def apply_moves(
    con: duckdb.DuckDBPyConnection,
    moves: list[tuple[str, str, str, str]],
    *,
    apply: bool,
) -> list[Move]:
    reports: list[Move] = []
    for src_schema, src_name, dest_schema, dest_name in moves:
        src, dest = f'"{src_schema}"."{src_name}"', f'"{dest_schema}"."{dest_name}"'
        label = Move(f"{src_schema}.{src_name}", f"{dest_schema}.{dest_name}")
        exists = con.execute(
            "SELECT count(*) FROM duckdb_tables() WHERE schema_name = ? AND table_name = ?",
            [dest_schema, dest_name],
        ).fetchone()[0]
        if exists:
            # Resumable, but only for this migration's own output: a destination that
            # exists while the source is gone is a completed move, and one that exists
            # while the source is still there is a name clash nobody has resolved.
            src_still_there = con.execute(
                "SELECT count(*) FROM duckdb_tables()"
                " WHERE schema_name = ? AND table_name = ?",
                [src_schema, src_name],
            ).fetchone()[0]
            if src_still_there:
                reports.append(Move(label.src, label.dest,
                                    error="destination exists and source still does too"))
                continue
            reports.append(Move(label.src, label.dest, error="already moved"))
            continue
        if not apply:
            rows = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
            reports.append(Move(label.src, label.dest, rows=rows))
            continue
        try:
            con.execute(f"CREATE TABLE {dest} AS SELECT * FROM {src}")
            rows = con.execute(f"SELECT count(*) FROM {dest}").fetchone()[0]
            source_rows = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
            if rows != source_rows:
                raise RuntimeError(f"copied {rows} of {source_rows} rows")
            con.execute(f"DROP TABLE {src}")
        except Exception as exc:
            detail = str(exc).splitlines()[0] if str(exc) else ""
            reports.append(Move(label.src, label.dest,
                                error=f"{type(exc).__name__}: {detail}"))
        else:
            reports.append(Move(label.src, label.dest, rows=rows))
    return reports


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, default=DATA_ROOT / "cfb.duckdb")
    ap.add_argument("--apply", action="store_true", help="write; default is a dry run")
    args = ap.parse_args(argv)

    con = duckdb.connect(str(args.db), read_only=not args.apply)
    try:
        moves = plan_moves(con)
        if not moves:
            print("nothing to move -- stg_gql is already collapsed")
            return 0
        reports = apply_moves(con, moves, apply=args.apply)
        if args.apply:
            con.execute("CHECKPOINT")
    finally:
        con.close()

    failed = [r for r in reports if r.error and r.error != "already moved"]
    for r in reports:
        note = f"  ({r.error})" if r.error else f"  {r.rows} rows"
        print(f"  {r.src:44s} -> {r.dest:34s}{note}")
    print(f"{'moved' if args.apply else 'would move'}: {len(reports) - len(failed)}"
          f", failed: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
