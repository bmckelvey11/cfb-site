"""Report what pre-2013 betting lines exist, and where.

`core.fact_game_line` is empty before 2013 because CFBD serves no lines there.
The Prediction Tracker tape under `ingest/` does cover 2001-2012. This prints
both sides so the gap is measured rather than assumed.

    python scripts/probe_pre2013_lines.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT  # noqa: E402

PT_LINES = DATA_ROOT / "ingest" / "prediction_tracker_lines.csv"


def main() -> None:
    con = duckdb.connect(str(DATA_ROOT / "cfb.duckdb"), read_only=True)

    print("=== warehouse core.fact_game_line, games per season ===")
    rows = con.execute(
        """select g.season, count(distinct l.game_id) as with_line
           from core.fact_game g join core.fact_game_line l using(game_id)
           group by 1 order by 1"""
    ).fetchall()
    print(f"  seasons present: {rows[0][0]}-{rows[-1][0]}; nothing before {rows[0][0]}")

    if not PT_LINES.exists():
        print(f"\n{PT_LINES} missing - run research/spread/scripts/build_prediction_tracker.py")
        return

    con.execute(
        f"create or replace temp view pt as "
        f"select * from read_csv('{PT_LINES.as_posix()}', header=true, all_varchar=true)"
    )

    print("\n=== Prediction Tracker tape, pre-2013 ===")
    print("season  rows  game_id  close  open")
    for r in con.execute(
        """select season, count(*) as n,
             sum((game_id is not null and game_id <> '')::int) as gid,
             sum((line is not null and line <> '')::int) as close,
             sum((lineopen is not null and lineopen <> '')::int) as open
           from pt where try_cast(season as int) < 2013
           group by 1 order by 1"""
    ).fetchall():
        print("  " + "  ".join(str(x) for x in r))

    # PT's `total` is hscore+vscore, not an over/under. Prove it rather than assert it.
    same, tot = con.execute(
        """select sum((try_cast(total as double)
                       = try_cast(home_points as double) + try_cast(away_points as double))::int),
                  count(*)
           from pt where total is not null and total <> ''
             and home_points is not null and away_points is not null"""
    ).fetchone()
    print(f"\npt.total == final points scored on {same}/{tot} rows -> not an over/under")
    print("No over/under exists in the Prediction Tracker tape for any season.")


if __name__ == "__main__":
    main()
