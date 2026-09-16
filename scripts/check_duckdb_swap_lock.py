"""Does an open DuckDB connection block the rebuild's atomic swap?

`build_duckdb` stages at `cfb.duckdb.building` and finishes with
`tmp_path.replace(db_path)` (duckdb_load.py). On Windows that replace fails if
another process holds the destination open -- and DuckDB holds the file open
even at `read_only=True`. So any long-lived reader (a Flask process querying the
warehouse, a notebook left open) breaks the 05:00 refresh.

Run before wiring a new long-lived consumer onto `cfb.duckdb`:

    python scripts/check_duckdb_swap_lock.py

Exit 0 = the swap succeeded while a reader was attached (no lock problem on this
platform). Exit 1 = a reader blocks the swap; that consumer must open and close
per query, or read a file extract instead.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import duckdb


def swap_blocked_by_reader() -> tuple[bool, str]:
    """Stage a db, hold it open read-only, and try the rebuild's final replace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        live = Path(tmpdir) / "live.duckdb"
        staged = Path(tmpdir) / "live.duckdb.building"
        for path in (live, staged):
            con = duckdb.connect(str(path))
            con.execute("CREATE TABLE t (x INTEGER)")
            con.close()

        reader = duckdb.connect(str(live), read_only=True)
        try:
            staged.replace(live)
        except OSError as exc:
            return True, f"{type(exc).__name__}: {exc}"
        finally:
            reader.close()
        return False, "replace succeeded with a reader attached"


def main() -> int:
    blocked, detail = swap_blocked_by_reader()
    if blocked:
        print(f"BLOCKED -- a long-lived reader breaks the rebuild swap.\n  {detail}")
        return 1
    print(f"OK -- {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
