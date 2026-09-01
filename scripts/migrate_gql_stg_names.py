"""Rename GraphQL-sourced stg tables to explicit gql_ destinations.

One-shot and idempotent. `meta.load_report` keys on (schema, name), so renaming a table
without repairing report desyncs bookkeeping; both happen in one transaction.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cfb_system_maker.graphql_client import GQL_ENTITY_TO_STG  # noqa: E402


def plan_renames(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    existing = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'stg'"
        ).fetchall()
    }
    pairs: list[tuple[str, str]] = []
    for entity, dest in GQL_ENTITY_TO_STG.items():
        # `calendar_gql` is legacy suffix order-dependent helper produced when REST
        # table won bare name. Prefer it over bare entity name, which then belongs to
        # REST and must not be touched.
        legacy_source = f"{entity}_gql"
        if legacy_source in existing:
            source = legacy_source
        elif entity in existing and dest not in existing:
            source = entity
        else:
            source = None
        if source is not None and source != dest:
            pairs.append((source, dest))
        for name in sorted(existing):
            if name.startswith(f"{entity}__"):
                child = name[len(entity):]
                pairs.append((name, dest + _snake_child(child)))
    return sorted(set(pairs))


def _snake_child(suffix: str) -> str:
    import re

    return re.sub(r"(?<!^)(?=[A-Z])", "_", suffix).lower()


def migrate(
    con: duckdb.DuckDBPyConnection, *, dry_run: bool
) -> list[tuple[str, str]]:
    pairs = plan_renames(con)
    if dry_run or not pairs:
        return pairs
    con.execute("BEGIN TRANSACTION")
    try:
        for old, new in pairs:
            con.execute(f'ALTER TABLE stg."{old}" RENAME TO "{new}"')
            con.execute(
                "UPDATE meta.load_report SET name = ? WHERE schema = 'stg' AND name = ?",
                [new, old],
            )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/cfb.duckdb")
    ap.add_argument("--apply", action="store_true", help="without this, dry-run only")
    args = ap.parse_args()
    con = duckdb.connect(args.db, read_only=not args.apply)
    pairs = migrate(con, dry_run=not args.apply)
    verb = "renamed" if args.apply else "would rename"
    for old, new in pairs:
        print(f"  {old} -> {new}")
    print(f"{verb} {len(pairs)} tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
