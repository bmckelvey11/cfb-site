"""Report coverage metrics for each GraphQL/REST table pair.

Designating canonical source is judgement call; script supplies evidence and deliberately
does not pick winner. Row count alone misleads — REST `coaches` has more rows than GraphQL
`coach`, while GraphQL `game` has twice rows of `games`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# (concept, gql_table, rest_table) — both live in `stg` since the collapse (ADR-0003);
# gql_table carries a `_gql` suffix for exactly the three names REST also owns. rest_table
# lives in stg. A concept whose two spellings collide once bare (draft_pick) still has
# distinct entries here because the two tables live in different schemas.
PAIRS = [
    ("game", "game", "games"),
    ("coach", "coach", "coaches"),
    ("conference", "conference", "conferences"),
    ("draft_pick", "draft_picks_gql", "draft_picks"),
    ("draft_position", "draft_position", "draft_positions"),
    ("draft_team", "draft_team", "draft_teams"),
    ("recruit", "recruit", "recruits"),
    ("recruiting_team", "recruiting_team", "recruiting_teams"),
    ("coach_season", "coach_season", "coach_seasons"),
    ("predicted_points", "predicted_points_gql", "predicted_points"),
    ("talent", "team_talent", "talent"),
    ("lines", "game_lines", "lines"),
    ("calendar", "calendar_gql", "calendar"),
]


def _cols(con: duckdb.DuckDBPyConnection, schema: str, table: str) -> list[str]:
    return [
        row[0]
        for row in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = ? AND table_name = ?",
            [schema, table],
        ).fetchall()
    ]


def _seasons(
    con: duckdb.DuckDBPyConnection, schema: str, table: str, cols: list[str]
) -> tuple[int, int] | None:
    if "season" not in cols:
        return None
    row = con.execute(f'SELECT MIN(season), MAX(season) FROM "{schema}"."{table}"').fetchone()
    return None if row is None or row[0] is None else (int(row[0]), int(row[1]))


def _null_rate(
    con: duckdb.DuckDBPyConnection, schema: str, table: str, cols: list[str]
) -> float | None:
    if not cols:
        return None
    total = con.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"').fetchone()[0]
    if not total:
        return None
    parts = " + ".join(f'COUNT("{c}")' for c in cols)
    filled = con.execute(f'SELECT {parts} FROM "{schema}"."{table}"').fetchone()[0]
    return round(1 - (filled / (total * len(cols))), 4)


def concept_metrics(
    con: duckdb.DuckDBPyConnection, gql_table: str, rest_table: str
) -> dict:
    gcols = _cols(con, "stg", gql_table)
    rcols = _cols(con, "stg", rest_table)
    return {
        "gql_rows": con.execute(f'SELECT COUNT(*) FROM "stg"."{gql_table}"').fetchone()[0],
        "rest_rows": con.execute(f'SELECT COUNT(*) FROM "stg"."{rest_table}"').fetchone()[0],
        "gql_cols": len(gcols),
        "rest_cols": len(rcols),
        "gql_seasons": _seasons(con, "stg", gql_table, gcols),
        "rest_seasons": _seasons(con, "stg", rest_table, rcols),
        "gql_null_rate": _null_rate(con, "stg", gql_table, gcols),
        "rest_null_rate": _null_rate(con, "stg", rest_table, rcols),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/cfb.duckdb")
    args = ap.parse_args()
    con = duckdb.connect(args.db, read_only=True)
    gql_present = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'stg'"
        ).fetchall()
    }
    rest_present = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'stg'"
        ).fetchall()
    }
    print("| concept | gql rows | rest rows | gql seasons | rest seasons "
          "| gql cols | rest cols | gql null | rest null |")
    print("|---|---|---|---|---|---|---|---|---|")
    for concept, g, r in PAIRS:
        if g not in gql_present or r not in rest_present:
            print(f"| {concept} | MISSING ({g} or {r}) | | | | | | | |")
            continue
        m = concept_metrics(con, g, r)
        print(
            f"| {concept} | {m['gql_rows']} | {m['rest_rows']} | {m['gql_seasons']} "
            f"| {m['rest_seasons']} | {m['gql_cols']} | {m['rest_cols']} "
            f"| {m['gql_null_rate']} | {m['rest_null_rate']} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
