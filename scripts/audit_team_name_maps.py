"""How well does each vendor's team name reach `core.dim_team`?

Four places in this repo map a vendor's own team name onto a CFBD `team_id`, and each
maintains its own rules: `stg.massey_teams` (`cfbd_id`), `stg.pff_franchise`
(`cfbd_team_id`), and two that join on the school string alone --
`stg.recruiting_teams.team` and `stg.coaches__seasons.seasons_school`. `#core-dim-team` in
TODO.md proposes collapsing them onto one shared mapping; this script is what says whether
that would fix data or only consolidate code.

The number that matters is not raw coverage. A vendor that carries FCS and D2 schools will
always have rows CFBD has no team for, and counting those as misses makes a clean map look
broken. So every unmapped name is checked against `core.dim_team` a second way -- exact
school, then CFBD's own `alternateNames` -- and reported separately from the ones that
simply do not exist upstream.

    python scripts/audit_team_name_maps.py
    python scripts/audit_team_name_maps.py --db path/to/other.duckdb --list

Read-only. Exits 0 always: this reports a state, it does not gate anything.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT  # noqa: E402

# (label, SQL yielding one row per distinct vendor name with its resolved id or NULL)
SOURCES = (
    ("massey_teams", """
        SELECT massey_team AS name, cfbd_id AS team_id FROM stg.massey_teams
    """),
    # `kind = 'allstar'` is excluded on purpose: PFF's 96 all-star and exhibition
    # franchises are not schools, so a CFBD team for them is not a thing to be missing.
    # Four of them (FAIRST, OBERLIN, THMORE, WCU) do resolve through `alternateNames`, so
    # counting them makes a complete map look like it has four gaps.
    ("pff_franchise", """
        SELECT team_name AS name, cfbd_team_id AS team_id
        FROM stg.pff_franchise WHERE kind = 'team'
    """),
    ("recruiting_teams", """
        SELECT DISTINCT r.team AS name, d.team_id
        FROM stg.recruiting_teams r LEFT JOIN core.dim_team d ON d.school = r.team
    """),
    ("coaches__seasons", """
        SELECT DISTINCT c.seasons_school AS name, d.team_id
        FROM stg.coaches__seasons c LEFT JOIN core.dim_team d ON d.school = c.seasons_school
    """),
)


def unresolvable(con: duckdb.DuckDBPyConnection, names: list[str]) -> list[str]:
    """Of `names`, the ones no dim_team school or CFBD alternate name matches either.

    These are schools CFBD does not carry at all -- the vendor is broader than FBS -- so
    they are the floor a shared mapping could never lift.
    """
    if not names:
        return []
    return [r[0] for r in con.execute("""
        SELECT n.name FROM (SELECT unnest(?::VARCHAR[]) AS name) n
        LEFT JOIN core.dim_team d ON d.school = n.name
        LEFT JOIN stg."teams__alternateNames" a ON a.alternateNames = n.name
        WHERE d.team_id IS NULL AND a."teamId" IS NULL
        ORDER BY 1
    """, [names]).fetchall()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, default=DATA_ROOT / "cfb.duckdb")
    ap.add_argument("--list", action="store_true", help="print every unmapped name")
    args = ap.parse_args()

    con = duckdb.connect(str(args.db), read_only=True)
    total, fbs = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE is_fbs) FROM core.dim_team").fetchone()
    print(f"core.dim_team: {total} teams, {fbs} FBS\n")
    print(f"{'source':20s} {'names':>6s} {'mapped':>7s} {'unmapped':>9s} "
          f"{'not in CFBD':>12s} {'real gaps':>10s}")

    for label, sql in SOURCES:
        rows = con.execute(sql).fetchall()
        unmapped = sorted({r[0] for r in rows if r[1] is None and r[0] is not None})
        absent = unresolvable(con, unmapped)
        gaps = [n for n in unmapped if n not in set(absent)]
        print(f"{label:20s} {len(rows):6d} {len(rows) - len(unmapped):7d} "
              f"{len(unmapped):9d} {len(absent):12d} {len(gaps):10d}")
        if args.list and unmapped:
            for n in absent:
                print(f"    not in CFBD  {n}")
            for n in gaps:
                print(f"    REAL GAP     {n}")

    print("\n`real gaps` is the only column a shared mapping could close: a name CFBD does\n"
          "carry, under its school or an alternate name, that the vendor's own rules missed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
