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

from pathlib import Path
import argparse
import os
import sys

import duckdb

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from cfb_paths import DATA_ROOT  # noqa: E402

DEFAULT_SCHEMAS = ["raw", "stg", "core", "meta"]

# Tables that must exist locally before anything remote can be called an orphan. A
# warehouse missing these is not "a warehouse with fewer tables", it is a warehouse
# that did not finish building.
ANCHOR_TABLES = [("core", "fact_game"), ("core", "fact_game_line"), ("stg", "an_scoreboard")]


def _assert_local_is_the_promoted_warehouse(con) -> None:
    """Fail closed unless the local file is complete AND is the promoted source.

    Orphan classification is a set difference: every remote table with no local
    counterpart gets dropped. So an empty or half-built local warehouse does not
    produce a small orphan list -- it produces a total one. Two gates:

    1. Anchor tables present, which rejects empty and partially-rebuilt files.
    2. Exact local/remote meta.warehouse_version match, which rejects a *stale*
       warehouse -- complete, passes gate 1, and still the wrong one. promote
       writes this stamp to both sides, so a mismatch means the local file is not
       what the mirror was built from.
    """
    missing = [
        f"{schema}.{table}"
        for schema, table in ANCHOR_TABLES
        if not con.execute(
            "SELECT count(*) FROM duckdb_tables() WHERE database_name = 'src' "
            "AND schema_name = ? AND table_name = ?",
            [schema, table],
        ).fetchone()[0]
    ]
    if missing:
        raise SystemExit(
            "Refusing to prune: local warehouse is missing " + ", ".join(missing) + ".\n"
            "Every remote table would classify as an orphan. Rebuild before pruning."
        )

    def _version(db: str):
        present = con.execute(
            "SELECT count(*) FROM duckdb_tables() WHERE database_name = ? "
            "AND schema_name = 'meta' AND table_name = 'warehouse_version'",
            [db],
        ).fetchone()[0]
        if not present:
            return None
        return con.execute(f"SELECT * FROM {db}.meta.warehouse_version").fetchall()

    local_version, remote_version = _version("src"), _version("md")
    if local_version is None or remote_version is None:
        raise SystemExit(
            "Refusing to prune: meta.warehouse_version is missing "
            f"({'local' if local_version is None else 'remote'}). Run "
            "promote_to_motherduck.py first so both sides carry a comparable stamp."
        )
    if local_version != remote_version:
        raise SystemExit(
            "Refusing to prune: meta.warehouse_version differs.\n"
            f"  local:  {local_version}\n"
            f"  remote: {remote_version}\n"
            "The local file is not the warehouse this mirror was promoted from."
        )



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=DATA_ROOT)
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
    _assert_local_is_the_promoted_warehouse(con)

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
