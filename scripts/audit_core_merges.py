"""What each GraphQL source would add to the ``core`` table it merges into.

The Bucket C/B merges in `duckdb_core.py` build *new* `core` tables, so a wrong join
shows up as a table nobody had before. These four merge into tables that already exist
and already have consumers, so the failure mode is the opposite: a row count that moves,
or a column whose values change under a query that was already written. ADR-0001 is the
rule -- `fact_game` gains columns, not rows -- and this is the measurement that says
whether a merge obeys it.

    python scripts/audit_core_merges.py                 # all four
    python scripts/audit_core_merges.py --merge game

Read-only. Prints numbers and exits 0; it does not decide anything. The three things it
is built to catch:

* **Row growth.** `matched` + `core-only` must equal the current `core` row count, and
  `gql-only (in span)` must be 0. Anything else means the merge adds rows.
* **Silent value change.** `disagree` counts rows where both sides are non-NULL and
  differ. It was 3,714/3,985 on `fact_game`'s conference ids before the FK repair; a
  merge that overwrites without reading this number is guessing.
* **A column not worth carrying.** Fill rate on the GraphQL-exclusive columns. `srName`
  fills 1 of 256 rows -- a §5 drop-list candidate, not a merge input.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT  # noqa: E402


def scalar(con: duckdb.DuckDBPyConnection, sql: str):
    return con.execute(sql).fetchone()


def fill(con: duckdb.DuckDBPyConnection, table: str, cols: list[str]) -> None:
    total = scalar(con, f"SELECT count(*) FROM {table}")[0]
    if not total:
        return
    counts = scalar(con, f"SELECT {', '.join(f'count(\"{c}\")' for c in cols)} FROM {table}")
    for c, n in zip(cols, counts):
        print(f"    fill  {c:26s} {n:8d} / {total:<8d} {n / total:.3f}")


def audit_conference(con: duckdb.DuckDBPyConnection) -> None:
    print("== conference  stg.conference -> core.dim_conference  (key: conferenceId)")
    print("    core rows            ", scalar(con, "SELECT count(*) FROM core.dim_conference")[0])
    print("    gql rows / distinct  ",
          scalar(con, "SELECT count(*), count(DISTINCT \"conferenceId\") FROM stg.conference"))
    print("    matched              ", scalar(con, """
        SELECT count(*) FROM core.dim_conference c
        JOIN stg.conference g ON g."conferenceId" = c.conference_id""")[0])
    print("    gql-only             ", scalar(con, """
        SELECT count(*) FROM stg.conference g
        LEFT JOIN core.dim_conference c ON c.conference_id = g."conferenceId"
        WHERE c.conference_id IS NULL""")[0])
    print("    name disagree        ", scalar(con, """
        SELECT count(*) FROM core.dim_conference c
        JOIN stg.conference g ON g."conferenceId" = c.conference_id
        WHERE c.name IS DISTINCT FROM g.name""")[0])
    fill(con, "stg.conference", ["division", "srName"])
    # The reason fact_game cannot resolve a conference by name.
    print("    duplicate core names ", scalar(con, """
        SELECT count(*) FROM (SELECT name FROM core.dim_conference
                              GROUP BY 1 HAVING count(*) > 1)""")[0])


def audit_game(con: duckdb.DuckDBPyConnection) -> None:
    print("== game  stg.game -> core.fact_game  (key: gameId)")
    print("    core rows / span     ",
          scalar(con, "SELECT count(*), min(season), max(season) FROM core.fact_game"))
    print("    gql rows / span      ",
          scalar(con, "SELECT count(*), min(season), max(season) FROM stg.game"))
    print("    matched              ", scalar(con, """
        SELECT count(*) FROM core.fact_game f
        JOIN stg.game g ON g."gameId" = f.game_id""")[0])
    print("    core-only            ", scalar(con, """
        SELECT count(*) FROM core.fact_game f
        LEFT JOIN stg.game g ON g."gameId" = f.game_id WHERE g."gameId" IS NULL""")[0])
    # Must be 0: anything here is a row core.fact_game would have to grow to hold.
    print("    gql-only (in span)   ", scalar(con, """
        SELECT count(*) FROM stg.game g
        LEFT JOIN core.fact_game f ON f.game_id = g."gameId"
        WHERE f.game_id IS NULL
          AND g.season >= (SELECT min(season) FROM core.dim_week)""")[0])
    print("    gql below span       ", scalar(con, """
        SELECT count(*) FROM stg.game
        WHERE season < (SELECT min(season) FROM core.dim_week)""")[0],
          " -> core.fact_game_historical (ADR-0001)")
    for side in ("home", "away"):
        print(f"    {side} conf-id disagree ", scalar(con, f"""
            SELECT count(*) FROM core.fact_game f
            JOIN stg.game g ON g."gameId" = f.game_id
            WHERE f.{side}_conference_id IS NOT NULL
              AND g."{side}ConferenceId" IS NOT NULL
              AND f.{side}_conference_id <> g."{side}ConferenceId" """)[0])
    fill(con, "stg.game", ["homeConferenceId", "awayConferenceId", "status"])


def audit_calendar(con: duckdb.DuckDBPyConnection) -> None:
    print("== calendar  stg.calendar_gql -> core.dim_week  (key: year, week, seasonType)")
    print("    core rows / span     ",
          scalar(con, "SELECT count(*), min(season), max(season) FROM core.dim_week"))
    print("    gql rows / span      ",
          scalar(con, "SELECT count(*), min(year), max(year) FROM stg.calendar_gql"))
    # Both zero is the no-op verdict: nothing to gain in span, and the out-of-span rows
    # cannot be taken because dim_week is what bounds core.fact_game.
    print("    gql-only (in span)   ", scalar(con, """
        SELECT count(*) FROM stg.calendar_gql g
        LEFT JOIN core.dim_week w
          ON w.season = g.year AND w.week = g.week AND w.season_type = g."seasonType"
        WHERE w.season IS NULL
          AND g.year >= (SELECT min(season) FROM core.dim_week)""")[0])
    print("    gql below span       ", scalar(con, """
        SELECT count(*) FROM stg.calendar_gql
        WHERE year < (SELECT min(season) FROM core.dim_week)""")[0],
          " -> not taken; would expand core.fact_game's bound")


def audit_lines(con: duckdb.DuckDBPyConnection) -> None:
    print("== lines  stg.game_lines -> core.fact_game_line  (key: gameId, provider)")
    print("    core rows / grain    ",
          scalar(con, "SELECT count(*), count(DISTINCT (game_id, provider_key))"
                      " FROM core.fact_game_line"))
    print("    gql period='game'    ",
          scalar(con, "SELECT count(*), count(DISTINCT (\"gameId\", \"linesProviderId\"))"
                      " FROM stg.game_lines WHERE period = 'game'"))
    # game_lines is not a pure GraphQL scrape -- it already carries the ActionNetwork
    # ingest, which is where the providers core.fact_game_line has never seen come from.
    print("    by line_source       ", con.execute(
        "SELECT line_source, count(*) FROM stg.game_lines WHERE period = 'game'"
        " GROUP BY 1 ORDER BY 2 DESC").fetchall())
    print("    providers gql lacks in core:")
    for name, n in con.execute("""
        SELECT lower(p.name) AS k, count(*) AS n
        FROM stg.game_lines l JOIN stg.lines_provider p USING ("linesProviderId")
        WHERE l.period = 'game'
          AND lower(p.name) NOT IN (SELECT provider_key FROM core.fact_game_line)
        GROUP BY 1 ORDER BY 2 DESC""").fetchall():
        print(f"      {name:34s} {n}")

    # Section 7's gate: REST offers matching a period='game' row on (gameId, provider),
    # **both directions**. `core-only` is what a straight repoint would silently drop.
    con.execute("""
        CREATE OR REPLACE TEMP VIEW _gl AS
        SELECT l."gameId" AS game_id, lower(p.name) AS provider_key,
               l.spread, l."spreadOpen" AS spread_open,
               l."overUnder" AS total, l."overUnderOpen" AS total_open,
               l."moneylineHome" AS ml_h, l."moneylineAway" AS ml_a, l.line_source
        FROM stg.game_lines l JOIN stg.lines_provider p USING ("linesProviderId")
        WHERE l.period = 'game'
    """)
    print("    matched              ", scalar(con,
        "SELECT count(*) FROM core.fact_game_line c JOIN _gl g USING (game_id, provider_key)")[0])
    print("    core-only            ", scalar(con, """
        SELECT count(*) FROM core.fact_game_line c
        LEFT JOIN _gl g USING (game_id, provider_key) WHERE g.game_id IS NULL""")[0],
          " <- a repoint would DROP these")
    print("    gql-only             ", scalar(con, """
        SELECT count(*) FROM _gl g
        LEFT JOIN core.fact_game_line c USING (game_id, provider_key)
        WHERE c.game_id IS NULL""")[0])
    print("    core-only by provider", con.execute("""
        SELECT c.provider_key, count(*) FROM core.fact_game_line c
        LEFT JOIN _gl g USING (game_id, provider_key)
        WHERE g.game_id IS NULL GROUP BY 1 ORDER BY 2 DESC""").fetchall())
    # A value that moves under a query already written is the quiet failure. `differ` here
    # counts only rows where BOTH sides are non-NULL -- a real conflict, not a gain.
    print("    value conflicts on the shared grain (both non-NULL, different):")
    for core_col, gql_col in (("spread_close", "spread"), ("spread_open", "spread_open"),
                              ("total_close", "total"), ("total_open", "total_open"),
                              ("moneyline_home", "ml_h"), ("moneyline_away", "ml_a")):
        conflict, gain, loss = scalar(con, f"""
            SELECT count(*) FILTER (WHERE c.{core_col} IS NOT NULL AND g.{gql_col} IS NOT NULL
                                      AND c.{core_col} <> g.{gql_col}),
                   count(*) FILTER (WHERE c.{core_col} IS NULL AND g.{gql_col} IS NOT NULL),
                   count(*) FILTER (WHERE c.{core_col} IS NOT NULL AND g.{gql_col} IS NULL)
            FROM core.fact_game_line c JOIN _gl g USING (game_id, provider_key)""")
        print(f"      {core_col:16s} conflict={conflict:6d}  gql-fills={gain:6d}  gql-loses={loss:6d}")


MERGES = {
    "conference": audit_conference,
    "game": audit_game,
    "calendar": audit_calendar,
    "lines": audit_lines,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, default=DATA_ROOT / "cfb.duckdb")
    ap.add_argument("--merge", choices=sorted(MERGES), help="one merge; default is all")
    args = ap.parse_args()

    con = duckdb.connect(str(args.db), read_only=True)
    try:
        for name in ([args.merge] if args.merge else list(MERGES)):
            MERGES[name](con)
            print()
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
