"""Promote local data/cfb.duckdb to md:cfb (MotherDuck mirror).

Local file is source of truth. This script never writes to md:cfb implicitly —
run it manually, after a rebuild has passed agreement tests. See the
"MotherDuck promote" runbook in docs/duckdb-warehouse-plan.md.

Usage:
    python scripts/promote_to_motherduck.py --dry-run   # show what would push
    python scripts/promote_to_motherduck.py --yes       # actually push

Requires `motherduck_token` (or `MOTHERDUCK_TOKEN`) in the environment or as a
line in the gitignored hub-root `env.env`, or a prior
`duckdb -c "ATTACH 'md:'"` interactive login on this machine.
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb

DEFAULT_SCHEMAS = ["raw", "stg", "core", "meta"]


_MD_TOKEN_KEYS = ("motherduck_token", "MOTHERDUCK_TOKEN")


def load_md_token() -> bool:
    """Put the MotherDuck token in the environment. True if one was found.

    Same resolution order as ``cfbd_client.find_cfbd_token``: env first, then the
    gitignored hub-root ``env.env``. Without this, ATTACH falls back to browser SSO,
    which cannot complete in a non-interactive run.
    """
    for key in _MD_TOKEN_KEYS:
        if os.environ.get(key):
            os.environ["motherduck_token"] = os.environ[key]
            return True
    for parent in Path(__file__).resolve().parents:
        env = parent / "env.env"
        if not env.exists():
            continue
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() in _MD_TOKEN_KEYS and value.strip():
                os.environ["motherduck_token"] = value.strip()
                return True
    return False


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=os.environ.get("CFB_DATA_ROOT", "data"))
    parser.add_argument("--schemas", nargs="+", default=DEFAULT_SCHEMAS)
    parser.add_argument(
        "--dry-run", action="store_true", help="list tables, push nothing"
    )
    parser.add_argument("--yes", action="store_true", help="required to actually push")
    parser.add_argument(
        "--memory-limit",
        default="2GB",
        help="DuckDB memory budget for the copy (default 2GB; the rest spills to disk)",
    )
    args = parser.parse_args()

    src_path = f"{args.data_dir}/cfb.duckdb"
    if not os.path.exists(src_path):
        print(f"No local DuckDB file at {src_path}. Rebuild first.", file=sys.stderr)
        return 1

    if not args.dry_run and not args.yes:
        print(
            "Refusing to push without --yes (md:cfb is shared, not scratch).",
            file=sys.stderr,
        )
        print("Run with --dry-run first to see what would be pushed.", file=sys.stderr)
        return 1

    if not load_md_token():
        print(
            "No motherduck_token found in env or env.env — ATTACH 'md:' will prompt "
            "for browser SSO, which times out in a non-interactive run."
        )

    con = duckdb.connect()
    # Streaming a multi-million-row table into md is what blows up: without these,
    # gamePlayerStat-sized copies hit "Out of Memory Error: Allocation failure" and
    # abort the promote half-done. Dropping insertion order lets the copy run in
    # bounded chunks, and a temp dir gives it somewhere to spill.
    con.execute(f"SET memory_limit='{args.memory_limit}'")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET temp_directory='{os.path.join(args.data_dir, '.duckdb_tmp')}'")
    # Not READ_ONLY: the warehouse_version stamp below writes back to src too.
    con.execute(f"ATTACH '{src_path}' AS src")

    if not args.dry_run:
        con.execute("ATTACH 'md:cfb' AS md")

    tables = con.execute(
        """
        SELECT schema_name, table_name
        FROM duckdb_tables()
        WHERE database_name = 'src' AND schema_name = ANY(?)
        ORDER BY schema_name, table_name
        """,
        [args.schemas],
    ).fetchall()

    if not tables:
        print(
            f"No tables found in schemas {args.schemas} on {src_path}.", file=sys.stderr
        )
        return 1

    for schema, table in tables:
        n = con.execute(f'SELECT COUNT(*) FROM src."{schema}"."{table}"').fetchone()[0]
        if args.dry_run:
            print(f"[dry-run] {schema}.{table}: {n} rows")
            continue

        con.execute(f"CREATE SCHEMA IF NOT EXISTS md.{schema}")
        t0 = time.time()
        con.execute(
            f'CREATE OR REPLACE TABLE md."{schema}"."{table}" AS '
            f'SELECT * FROM src."{schema}"."{table}"'
        )
        dst_n = con.execute(f'SELECT COUNT(*) FROM md."{schema}"."{table}"').fetchone()[
            0
        ]
        status = "OK" if dst_n == n else f"MISMATCH (src={n} dst={dst_n})"
        print(
            f"{schema}.{table}: {dst_n} rows ({time.time()-t0:.1f}s) {status}",
            file=sys.stderr,
        )

    if args.dry_run:
        return 0

    promoted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    sha = git_sha()
    for target in ("src", "md"):
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {target}.meta")
        con.execute(
            f"CREATE OR REPLACE TABLE {target}.meta.warehouse_version "
            "AS SELECT ? AS git_sha, ? AS promoted_at",
            [sha, promoted_at],
        )

    con.close()
    print(f"Promoted {len(tables)} tables to md:cfb (git_sha={sha}).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
