"""How stale are the GraphQL dumps that `core` is built from?

`refresh_cfbd.py` re-scrapes REST, reflattens ActionNetwork/PFF/odds and rebuilds the
warehouse -- but nothing on that path re-pulls `data/graphql/*.json`. A full rebuild
therefore reloads whatever those dumps held the last time someone pulled them by hand, and
every `core` builder that reads a GraphQL-backed `stg` table is merging fresh REST against
a dump of unknown age.

    python scripts/audit_graphql_dump_age.py
    python scripts/audit_graphql_dump_age.py --stale-days 14

50 dumps exist; **10 feed `core`** and only those are audited. They split in two, and the
split is the point:

* **Group A -- a fresh comparator exists.** `game`, `calendar`, `conference` and
  `gameLines` have REST twins that `refresh_cfbd.py` scrapes on every run, so a coverage
  gap measured against them is real evidence about the dump.
* **Group B -- no fresh comparator.** `coach`, `coachSeason`, `recruit`, `teamTalent`,
  `draftPicks` and `linesProvider` have REST sides that are themselves only pulled by hand,
  so a gap against them is uninterpretable in both directions. These get file age, row
  count and an append-only/mutable classification -- and are reported as **unmeasured on
  divergence, not measured-and-clean**. Treating a blank there as "no gap" is the specific
  mistake this layout exists to prevent.

Note for `gameLines`: `stg.game_lines` is no longer the dump -- the ActionNetwork backfill
rebuilt it from `raw.gql_game_lines` unioned with the AN tape, so its row count mixes three
vintages. The dump's own contribution is `raw.gql_game_lines`, which is what is measured.

Read-only. Exits 0 always -- it reports, it does not decide.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT  # noqa: E402

# entity -> (dump stem, stg table, one-line note)
GROUP_B = {
    "coach": ("coach", "coach", "append-only: a row per coach, new hires only"),
    "coachSeason": ("coachSeason", "coach_season", "append-only: a row per coach-season"),
    "recruit": ("recruit", "recruit", "append-only per cycle; already reaches 2027"),
    "teamTalent": ("teamTalent", "team_talent", "append-only: a row per team-season"),
    "draftPicks": ("draftPicks", "draft_picks_gql", "append-only: frozen until the draft"),
    "linesProvider": ("linesProvider", "lines_provider", "static enum, 17 rows"),
}

# Each returns (label, value). A gap of 0 is evidence; None means the query could not run.
GROUP_A_CHECKS = {
    "game": [
        ("in-span REST games the dump lacks", """
            SELECT count(*) FROM stg.games r
            LEFT JOIN stg.game g ON g."gameId" = r."gameId"
            WHERE g."gameId" IS NULL
              AND r.season >= (SELECT min(season) FROM core.dim_week)"""),
        ("finished games the dump still calls scheduled", """
            SELECT count(*) FROM stg.games r JOIN stg.game g ON g."gameId" = r."gameId"
            WHERE r."homePoints" IS NOT NULL AND g.status = 'scheduled'"""),
    ],
    "calendar": [
        ("REST weeks the dump lacks", """
            SELECT count(*) FROM stg.calendar r
            LEFT JOIN stg.calendar_gql g
              ON g.year = r.season AND g.week = r.week AND g."seasonType" = r."seasonType"
            WHERE g.week IS NULL"""),
    ],
    "conference": [
        ("REST conferences the dump lacks", """
            SELECT count(*) FROM stg.conferences r
            LEFT JOIN stg.conference g ON g."conferenceId" = r."conferenceId"
            WHERE g."conferenceId" IS NULL"""),
    ],
    "gameLines": [
        ("REST-lined games the dump lacks", """
            SELECT count(DISTINCT r."gameId") FROM stg.lines r
            WHERE r."gameId" NOT IN (
              SELECT DISTINCT TRY_CAST(json_extract_string(payload, '$.gameId') AS BIGINT)
              FROM raw.gql_game_lines)"""),
    ],
}

GROUP_A_STG = {
    "game": "stg.game", "calendar": "stg.calendar_gql",
    "conference": "stg.conference", "gameLines": "raw.gql_game_lines",
}


def _age_days(path: Path) -> float | None:
    return None if not path.is_file() else (time.time() - path.stat().st_mtime) / 86400


def _rows(con: duckdb.DuckDBPyConnection, qualified: str) -> int | None:
    schema, table = qualified.split(".", 1)
    try:
        return con.execute(f'SELECT count(*) FROM {schema}."{table}"').fetchone()[0]
    except duckdb.Error:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, default=DATA_ROOT / "cfb.duckdb")
    ap.add_argument("--graphql-dir", type=Path, default=DATA_ROOT / "graphql")
    ap.add_argument("--stale-days", type=float, default=14.0,
                    help="flag a dump older than this (default 14)")
    args = ap.parse_args()

    con = duckdb.connect(str(args.db), read_only=True)
    try:
        dumps = sorted(args.graphql_dir.glob("*.json"))
        print(f"{len(dumps)} dump(s) in {args.graphql_dir}; 10 feed core, audited below.")
        ages = [a for a in (_age_days(p) for p in dumps) if a is not None]
        if ages:
            print(f"  age span across all dumps: newest {min(ages):.1f}d,"
                  f" oldest {max(ages):.1f}d\n")

        print("GROUP A -- fresh REST comparator, so a gap is evidence")
        for entity, checks in GROUP_A_CHECKS.items():
            path = args.graphql_dir / f"{entity}.json"
            age = _age_days(path)
            flag = "  <-- STALE" if age is not None and age > args.stale_days else ""
            n = _rows(con, GROUP_A_STG[entity])
            age_s = "missing" if age is None else f"{age:5.1f}d"
            print(f"  {entity:16s} {age_s}  {n:>9,} rows{flag}" if n is not None
                  else f"  {entity:16s} {age_s}  {'?':>9} rows{flag}")
            for label, sql in checks:
                try:
                    value = con.execute(sql).fetchone()[0]
                    mark = "  <-- BEHIND" if value else ""
                    print(f"      {label:48s} {value:>8,}{mark}")
                except duckdb.Error as exc:
                    print(f"      {label:48s} {'ERR':>8}  {str(exc).splitlines()[0][:50]}")

        print()
        print("GROUP B -- no fresh comparator; UNMEASURED on divergence, not clean")
        for entity, (stem, table, note) in GROUP_B.items():
            age = _age_days(args.graphql_dir / f"{stem}.json")
            flag = "  <-- STALE" if age is not None and age > args.stale_days else ""
            n = _rows(con, f"stg.{table}")
            age_s = "missing" if age is None else f"{age:5.1f}d"
            n_s = "?" if n is None else f"{n:,}"
            print(f"  {entity:16s} {age_s}  {n_s:>9} rows  {note}{flag}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
