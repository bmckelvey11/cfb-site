"""Check the falsifiable claims in the warehouse rationalization master plan.

`docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md` asserts structural
invariants (step 0 preflight), an all-NULL column census (section 5) and merge keys
(sections 6-7). Every one of those rots the moment the warehouse is rebuilt, and section 5
already had: it was measured before the ActionNetwork rename and now names three columns
that hold 6.4M populated values.

Containment between REST/GraphQL pairs is `scripts/audit_canonical_sources.py`, not here.
That script reports year coverage only from a column literally named `season`, so it reads
None for every GraphQL table (they use `year`) -- `--coverage` covers that gap.

Exit code is the number of failed checks, so this gates a step.
"""

from __future__ import annotations

import argparse

import duckdb

# Section 1. Measured 2026-09-08; step 0 asserts these before anything else runs.
STRUCTURE = {"core": None, "meta": None, "raw": 116, "stg": 124, "stg_gql": 38}
RAW_GQL_PREFIXED = 34
COLLIDERS = ["calendar", "draft_picks", "predicted_points"]

# Section 5's drop list. Kept verbatim so the check reports which entries have gone stale
# rather than quietly tracking the warehouse.
DEAD_CLAIMED = [
    ("stg", "plays", "defenseTimeouts"),
    ("stg", "plays", "offenseTimeouts"),
    ("stg", "plays", "wallclock"),
    ("stg_gql", "game_weather", "windGust"),
    ("stg_gql", "poll_type", "abbreviation"),
    ("stg_gql", "recruit", "overallRank"),
    ("stg_gql", "recruit", "positionRank"),
    ("stg", "team_stats", "statValue_anyof_schema_1_validator"),
    ("stg", "team_stats__statValue_any_of_schemas", "statValue_anyof_schema_1_validator"),
    ("stg", "actionnetwork_scoreboard__teams", "teams_standings_overtime_losses"),
    (
        "stg",
        "actionnetwork_scoreboard__markets__markets_event_moneyline",
        "markets_event_moneyline_odds_coefficient_score",
    ),
    (
        "stg",
        "actionnetwork_scoreboard__markets__markets_event_core_bet_type_6_team_score",
        "markets_event_core_bet_type_6_team_score_odds_coefficient_score",
    ),
]

# Loader scaffolding, bound from the dump filename. Section 5 claims 308 all-NULL copies
# of these survive into `stg`; R3 asks for them to stop being materialized there.
SPINE = ("season", "week", "season_type")

# Section 6 merge keys, as declared. `calendar` is declared `(season, week)`; the GraphQL
# side spells `season` as `year`, hence the per-side key.
MERGE_KEYS = [
    (
        "calendar",
        ("stg_gql", "calendar", ("year", "week")),
        ("stg", "calendar", ("season", "week")),
    ),
    (
        "draft_picks",
        ("stg_gql", "draft_picks", ("year", "round", "pick")),
        ("stg", "draft_picks", ("year", "round", "pick")),
    ),
    (
        "game_lines",
        ("stg_gql", "game_lines", ("gameId", "linesProviderId", "period")),
        None,
    ),
]

# Section 3's pairs, for --coverage. (concept, gql table, rest table).
PAIRS = [
    ("draft_position", "draft_position", "draft_positions"),
    ("draft_team", "draft_team", "draft_teams"),
    ("predicted_points", "predicted_points", "predicted_points"),
    ("coach_season", "coach_season", "coach_seasons"),
    ("talent", "team_talent", "talent"),
    ("recruit", "recruit", "recruits"),
    ("game", "game", "games"),
    ("draft_picks", "draft_picks", "draft_picks"),
    ("coach", "coach", "coaches"),
    ("conference", "conference", "conferences"),
    ("recruiting_team", "recruiting_team", "recruiting_teams"),
    ("calendar", "calendar", "calendar"),
]


def _columns(con, schema: str, table: str) -> list[str]:
    return [
        row[0]
        for row in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
            [schema, table],
        ).fetchall()
    ]


def _filled(con, schema: str, table: str) -> tuple[int, dict[str, int]]:
    """Row count and non-NULL count per column, in one scan."""
    cols = _columns(con, schema, table)
    if not cols:
        return 0, {}
    parts = ", ".join(f'COUNT("{c}")' for c in cols)
    row = con.execute(f'SELECT COUNT(*), {parts} FROM "{schema}"."{table}"').fetchone()
    return row[0], dict(zip(cols, row[1:]))


def check_structure(con) -> list[str]:
    counts = dict(
        con.execute(
            "SELECT table_schema, COUNT(*) FROM information_schema.tables GROUP BY 1"
        ).fetchall()
    )
    fails = []
    for schema, expected in STRUCTURE.items():
        got = counts.get(schema, 0)
        ok = expected is None or got == expected
        if not ok:
            fails.append(f"{schema}: {got} tables, plan says {expected}")
        note = "" if expected is None else f" (plan {expected})"
        print(f"  [{'ok' if ok else 'FAIL':4}] {schema:8} {got} tables{note}")

    prefixed = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = 'raw' AND starts_with(table_name, 'gql_')"
    ).fetchone()[0]
    ok = prefixed == RAW_GQL_PREFIXED
    if not ok:
        fails.append(f"raw gql_-prefixed: {prefixed}, plan says {RAW_GQL_PREFIXED}")
    print(f"  [{'ok' if ok else 'FAIL':4}] raw gql_ prefix {prefixed} (plan {RAW_GQL_PREFIXED})")

    colliders = [
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'stg' "
            "INTERSECT "
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'stg_gql' "
            "ORDER BY 1"
        ).fetchall()
    ]
    ok = colliders == COLLIDERS
    if not ok:
        fails.append(f"colliders: {colliders}, plan says {COLLIDERS}")
    print(f"  [{'ok' if ok else 'FAIL':4}] colliders       {colliders}")
    return fails


def check_dead_columns(con) -> list[str]:
    """Census every all-NULL column, then score the plan's drop list against it."""
    tables = con.execute(
        "SELECT table_schema, table_name FROM information_schema.tables "
        "WHERE table_schema IN ('stg', 'stg_gql') ORDER BY 1, 2"
    ).fetchall()
    census: dict[tuple[str, str, str], int] = {}
    for schema, table in tables:
        rows, filled = _filled(con, schema, table)
        for col, non_null in filled.items():
            if non_null == 0:
                census[(schema, table, col)] = rows

    spine_dead = [key for key in census if key[2] in SPINE]
    print(f"  all-NULL columns in stg + stg_gql: {len(census)} (plan section 5 says 332)")
    print(f"    of which loader spine {SPINE}: {len(spine_dead)} (plan says 308)")
    for key in sorted(census):
        print(f"      {key[0]}.{key[1]}.{key[2]}  rows={census[key]}")

    fails = []
    print("  plan's 12-column drop list, checked:")
    for schema, table, col in DEAD_CLAIMED:
        exists = con.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = ? AND table_name = ? AND column_name = ?",
            [schema, table, col],
        ).fetchone()[0]
        if not exists:
            fails.append(f"{schema}.{table}.{col} no longer exists")
            print(f"    [GONE] {schema}.{table}.{col}")
            continue
        rows, filled = _filled(con, schema, table)
        non_null = filled[col]
        if non_null:
            fails.append(
                f"{schema}.{table}.{col} holds {non_null} populated values -- do not drop"
            )
            print(f"    [LIVE] {schema}.{table}.{col}  rows={rows} non-null={non_null}")
        else:
            print(f"    [dead] {schema}.{table}.{col}  rows={rows}")

    claimed = {tuple(entry) for entry in DEAD_CLAIMED}
    unlisted = sorted(k for k in census if k not in claimed and k[2] not in SPINE)
    if unlisted:
        print("  all-NULL but absent from the plan's list:")
        for key in unlisted:
            print(f"    {key[0]}.{key[1]}.{key[2]}  rows={census[key]}")
    return fails


def check_merge_keys(con) -> list[str]:
    fails = []
    for concept, *sides in MERGE_KEYS:
        for side in sides:
            if side is None:
                continue
            schema, table, key = side
            cols = _columns(con, schema, table)
            missing = [k for k in key if k not in cols]
            if missing:
                fails.append(f"{concept}: {schema}.{table} has no column {missing}")
                print(f"  [FAIL] {concept:12} {schema}.{table} missing {missing}")
                continue
            tup = ", ".join(f'"{k}"' for k in key)
            rows, distinct = con.execute(
                f'SELECT COUNT(*), COUNT(DISTINCT ({tup})) FROM "{schema}"."{table}"'
            ).fetchone()
            ok = rows == distinct
            if not ok:
                fails.append(
                    f"{concept}: {schema}.{table} key {key} is not unique "
                    f"({rows} rows, {distinct} distinct)"
                )
            print(
                f"  [{'ok' if ok else 'FAIL':4}] {concept:12} {schema}.{table} {key} "
                f"rows={rows} distinct={distinct}"
            )
    return fails


def report_coverage(con) -> None:
    """Year span per side. `audit_canonical_sources.py` misses this on the GraphQL side."""
    print("| concept | gql rows | gql years | rest rows | rest years |")
    print("|---|---|---|---|---|")
    for concept, gql, rest in PAIRS:
        cells = []
        for schema, table in (("stg_gql", gql), ("stg", rest)):
            cols = _columns(con, schema, table)
            if not cols:
                cells.append(("MISSING", ""))
                continue
            rows = con.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"').fetchone()[0]
            year_col = next((c for c in ("season", "year") if c in cols), None)
            if year_col is None:
                cells.append((rows, "-"))
                continue
            lo, hi = con.execute(
                f'SELECT MIN("{year_col}"), MAX("{year_col}") FROM "{schema}"."{table}"'
            ).fetchone()
            cells.append((rows, f"{lo}-{hi}"))
        print(f"| {concept} | {cells[0][0]} | {cells[0][1]} | {cells[1][0]} | {cells[1][1]} |")


def _selftest() -> int:
    """The census and key checks, against a warehouse small enough to reason about."""
    global MERGE_KEYS

    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    con.execute("CREATE SCHEMA stg_gql")
    # Quoted, never `stg.t`: tests/test_catalog_resolution.py reads every `<schema>.<table>`
    # literal in scripts/ as a live warehouse reference, and these fixtures are not one.
    con.execute('CREATE TABLE "stg"."t" AS SELECT 1 AS a, NULL::INTEGER AS b')
    con.execute('CREATE TABLE "stg_gql"."k" AS SELECT * FROM (VALUES (1,1),(1,2)) v(year, week)')
    con.execute('CREATE TABLE "stg_gql"."dup" AS SELECT * FROM (VALUES (1,1),(1,1)) v(year, week)')

    rows, filled = _filled(con, "stg", "t")
    assert rows == 1 and filled == {"a": 1, "b": 0}, filled

    saved = MERGE_KEYS
    try:
        MERGE_KEYS = [("uniq", ("stg_gql", "k", ("year", "week")), None)]
        assert check_merge_keys(con) == []
        MERGE_KEYS = [("dup", ("stg_gql", "dup", ("year", "week")), None)]
        assert len(check_merge_keys(con)) == 1
        MERGE_KEYS = [("absent", ("stg_gql", "k", ("nope",)), None)]
        assert len(check_merge_keys(con)) == 1
    finally:
        MERGE_KEYS = saved
    print("selftest ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/cfb.duckdb")
    ap.add_argument("--coverage", action="store_true", help="year span per pair, then exit")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()

    con = duckdb.connect(args.db, read_only=True)
    if args.coverage:
        report_coverage(con)
        return 0

    fails: list[str] = []
    print("structure (plan section 1 / step 0)")
    fails += check_structure(con)
    print("\ndead columns (plan section 5)")
    fails += check_dead_columns(con)
    print("\nmerge keys (plan sections 6-7)")
    fails += check_merge_keys(con)

    print(f"\n{len(fails)} failed check(s)")
    for line in fails:
        print(f"  - {line}")
    return len(fails)


if __name__ == "__main__":
    raise SystemExit(main())
