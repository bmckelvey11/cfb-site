"""Check that the ``stg.pff_*`` tables still match their pinned schema.

Three checks, reported separately because they fail for unrelated reasons.

**tables** -- every name in ``pff_schema.PFF_TABLES`` present in ``stg``. A missing one
means the flattener stopped writing that CSV, or the loader skipped it; the table list is
pinned by hand precisely so that is visible rather than silent.

**types** -- every column's type against ``pff_schema.column_type``. A drift here means the
table was built by something other than the pinned loader -- ``read_csv_auto`` sniffing, a
hand-made ``CREATE TABLE`` -- and the fix is to reload, not to retype. This is the check
that would have caught `team` arriving as an INTEGER holding "KANSAS".

**join** -- every mapped ``pff_franchise.cfbd_team_id`` reaching ``stg.teams``. That is what
the S4 name map buys; a shortfall means CFBD renumbered a team, not that the map is wrong.

    python scripts/check_pff_pin.py
    python scripts/check_pff_pin.py --db path/to/other.duckdb

Exits 0 when all three pass, 1 otherwise. Read-only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT  # noqa: E402
from cfb_system_maker.pff_schema import PFF_TABLES, column_type  # noqa: E402


def check_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    present = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'stg'").fetchall()}
    return [t for t in PFF_TABLES if t not in present]


def check_types(con: duckdb.DuckDBPyConnection, tables: list[str]) -> list[str]:
    drift = []
    for table in tables:
        rows = con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'stg' AND table_name = ? ORDER BY ordinal_position",
            [table]).fetchall()
        for name, actual in rows:
            wanted = column_type(name)
            if actual.upper() != wanted:
                drift.append(f"{table}.{name}: {actual} (pinned {wanted})")
    return drift


def check_join(con: duckdb.DuckDBPyConnection) -> str | None:
    """Mapped franchises that do not reach `stg.teams`, and the coverage that do."""
    if not con.execute("SELECT count(*) FROM information_schema.tables "
                       "WHERE table_schema = 'stg' AND table_name = 'teams'").fetchone()[0]:
        return "stg.teams is not in this database -- join unchecked"
    mapped, hit = con.execute(
        "SELECT count(*), count(t.teamId) FROM stg.pff_franchise f "
        "LEFT JOIN (SELECT DISTINCT teamId FROM stg.teams) t ON t.teamId = f.cfbd_team_id "
        "WHERE f.cfbd_team_id IS NOT NULL").fetchone()
    return None if mapped == hit else f"{mapped - hit} of {mapped} mapped franchises miss stg.teams"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DATA_ROOT / "cfb.duckdb")
    args = ap.parse_args()
    if not args.db.exists():
        print(f"no warehouse at {args.db}")
        return 1

    con = duckdb.connect(str(args.db), read_only=True)
    missing = check_tables(con)
    print(f"[tables] {len(PFF_TABLES) - len(missing)}/{len(PFF_TABLES)} present"
          + (f" -- missing {', '.join(missing)}" if missing else ""))

    present = [t for t in PFF_TABLES if t not in missing]
    drift = check_types(con, present)
    print(f"[types]  {'ok' if not drift else f'{len(drift)} columns drifted'}")
    for line in drift[:20]:
        print(f"  {line}")

    join = check_join(con)
    print(f"[join]   {'ok' if join is None else join}")
    return 0 if not missing and not drift and join is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
