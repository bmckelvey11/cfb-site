"""Drop md:cfb tables that no longer exist in the local warehouse.

promote_to_motherduck.py does CREATE OR REPLACE per table and never drops, so a
table removed or renamed locally survives in the mirror indefinitely and reads
as live data. This prunes those orphans.

The local file is source of truth: an orphan has no local counterpart, so the
drop is not recoverable from local. Run --dry-run first and read the list.

Usage:
    python scripts/prune_motherduck_orphans.py --dry-run
    python scripts/prune_motherduck_orphans.py --yes

Requires `motherduck_token` (or `MOTHERDUCK_TOKEN`) env var, or a prior
`duckdb -c "ATTACH 'md:'"` interactive login on this machine.
"""

import argparse
import os
import sys

import duckdb

DEFAULT_SCHEMAS = ["raw", "stg", "core", "meta"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=os.environ.get("CFB_DATA_ROOT", "data"))
    parser.add_argument("--schemas", nargs="+", default=DEFAULT_SCHEMAS)
    parser.add_argument("--dry-run", action="store_true", help="list orphans, drop nothing")
    parser.add_argument("--yes", action="store_true", help="required to actually drop")
    args = parser.parse_args()

    src_path = f"{args.data_dir}/cfb.duckdb"
    if not os.path.exists(src_path):
        print(f"No local DuckDB file at {src_path}.", file=sys.stderr)
        return 1

    if not args.dry_run and not args.yes:
        print("Refusing to drop without --yes (md:cfb is shared).", file=sys.stderr)
        print("Run with --dry-run first to see what would be dropped.", file=sys.stderr)
        return 1

    con = duckdb.connect()
    con.execute(f"ATTACH '{src_path}' AS src (READ_ONLY)")
    con.execute("ATTACH 'md:cfb' AS md")

    local = {
        (schema, table)
        for schema, table in con.execute(
            """
            SELECT schema_name, table_name FROM duckdb_tables()
            WHERE database_name = 'src' AND schema_name = ANY(?)
            """,
            [args.schemas],
        ).fetchall()
    }
    remote = con.execute(
        """
        SELECT schema_name, table_name, estimated_size FROM duckdb_tables()
        WHERE database_name = 'md' AND schema_name = ANY(?)
        ORDER BY estimated_size DESC
        """,
        [args.schemas],
    ).fetchall()

    orphans = [row for row in remote if (row[0], row[1]) not in local]
    if not orphans:
        print("No orphans: every md:cfb table exists locally.", file=sys.stderr)
        return 0

    total = sum(n for _, _, n in orphans)
    for schema, table, n in orphans:
        prefix = "[dry-run] " if args.dry_run else ""
        print(f"{prefix}{schema}.{table}: {n} rows")

    if args.dry_run:
        print(f"[dry-run] {len(orphans)} orphans, {total} rows", file=sys.stderr)
        return 0

    for schema, table, _ in orphans:
        con.execute(f'DROP TABLE md."{schema}"."{table}"')

    con.close()
    print(f"Dropped {len(orphans)} orphan tables ({total} rows) from md:cfb.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
