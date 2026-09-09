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
import re
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cfb_system_maker.graphql_client import (  # noqa: E402
    GQL_ENTITY_TO_RAW,
    GQL_ENTITY_TO_STG,
)

# Section 1's table counts are state, not invariants -- `stg` grows with every new source
# (PFF's S5 adds ~19 `stg.pff_*` tables, and pff-ingest-plan.md owns that work). Pinning
# them here would fail step 0 for a non-problem. So the counts are printed, and what gets
# asserted is what section 2's argument actually rests on: the GraphQL entities are all
# present under both spellings, nothing outside those three names collides, and the two
# completed migrations have not regressed.
REPORTED_COUNTS = {"raw": 116, "stg": 124, "stg_gql": 38}  # measured 2026-09-09
COLLIDERS = ["calendar", "draft_picks", "predicted_points"]

# A `stg` table whose name still carries the transport, or its casing, means the naming
# rationalization or the schema separation came undone.
GQL_PREFIXED = re.compile(r"^gql_")
CAMEL_CASE = re.compile(r"[A-Z]")

# Section 5's drop list, as revised 2026-09-09. Transcribed rather than derived: the point is
# to fail when the plan and the warehouse disagree, which a self-deriving list cannot do.
# The 2026-09-08 list held three `stg.plays` columns carrying 6.4M values and three
# `actionnetwork_scoreboard__*` tables the AN rename had already replaced.
DEAD_CLAIMED = [
    ("stg", "an_team", "overtime_losses"),
    ("stg", "team_stats", "statValue_anyof_schema_1_validator"),
    ("stg", "team_stats__statValue_any_of_schemas", "statValue_anyof_schema_1_validator"),
    ("stg_gql", "game_weather", "windGust"),
    ("stg_gql", "poll_type", "abbreviation"),
    ("stg_gql", "recruit", "overallRank"),
    ("stg_gql", "recruit", "positionRank"),
]

# Section 5's headline count, printed for comparison but never a failure: it moves every time a
# 2026 game is played or a new weekly `lines_*` dump lands. A hard count here would fail step 0
# for a non-problem, which is how section 5 rotted in the first place.
ALL_NULL_REPORTED = 11

# The only all-NULL columns allowed off the drop list are unplayed games' scores. This is the
# shape check that replaces counting them.
FUTURE_DATED = re.compile(r"^lines_.*$")
FUTURE_DATED_COLUMN = re.compile(r"^(home|away)Score$")

# Loader scaffolding, bound from the dump filename. Section 5 claims 308 all-NULL copies
# of these survive into `stg`; R3 asks for them to stop being materialized there.
SPINE = ("season", "week", "season_type")

# Section 6 merge keys, as declared. `calendar` is declared `(season, week)`; the GraphQL
# side spells `season` as `year`, hence the per-side key.
MERGE_KEYS = [
    (
        "calendar",
        ("stg_gql", "calendar", ("year", "week", "seasonType")),
        ("stg", "calendar", ("season", "week", "seasonType")),
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
    tables: dict[str, set[str]] = {}
    for schema, table in con.execute(
        "SELECT table_schema, table_name FROM information_schema.tables"
    ).fetchall():
        tables.setdefault(schema, set()).add(table)

    fails = []
    for schema in sorted(tables):
        got = len(tables[schema])
        note = ""
        if schema in REPORTED_COUNTS:
            note = f" (was {REPORTED_COUNTS[schema]} on 2026-09-09; counts move with the data)"
        print(f"  [--  ] {schema:8} {got} tables{note}")

    # Every GraphQL entity must have landed under both spellings. This is what the old
    # `stg_gql == 38` / `raw gql_ == 34` counts were reaching for, said precisely: extra
    # `stg_gql` tables are explode children and are fine, a *missing* entity is not.
    for label, mapping, schema in (
        ("stg_gql", GQL_ENTITY_TO_STG, "stg_gql"),
        ("raw gql_", GQL_ENTITY_TO_RAW, "raw"),
    ):
        missing = sorted(set(mapping.values()) - tables.get(schema, set()))
        if missing:
            fails.append(f"{schema} is missing {len(missing)} GraphQL entities: {missing}")
        print(f"  [{'ok' if not missing else 'FAIL':4}] {label:8} all {len(mapping)} "
              f"entities present")

    colliders = sorted(tables.get("stg", set()) & tables.get("stg_gql", set()))
    ok = colliders == COLLIDERS
    if not ok:
        fails.append(f"colliders: {colliders}, plan says {COLLIDERS}")
    print(f"  [{'ok' if ok else 'FAIL':4}] colliders       {colliders}")

    # Postconditions of the two migrations section 1 says are done.
    stray = sorted(t for t in tables.get("stg", set()) if GQL_PREFIXED.match(t))
    if stray:
        fails.append(f"stg still holds gql_-prefixed tables: {stray}")
    print(f"  [{'ok' if not stray else 'FAIL':4}] no gql_ in stg  {len(stray)} found")

    # Reported, not asserted. Step 0's prose claims no camelCase `stg` table remains; 15 do
    # (2026-09-09), most of them explode children named after a camelCase JSON key, plus
    # `gameMedia` and `gamePlayerStat` -- which ADR-0003 already noted "need snake_casing, not
    # relocation." Renaming them is its own job, and failing step 0 on it would block the
    # rationalization on unrelated work.
    camel = sorted(
        f"{s}.{t}"
        for s in ("stg", "stg_gql")
        for t in tables.get(s, set())
        if CAMEL_CASE.search(t)
    )
    print(f"  [--  ] camelCase names {len(camel)} (step 0's prose says 0 -- see --camel)")
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

    fails = []
    spine_dead = [key for key in census if key[2] in SPINE]
    if spine_dead:
        fails.append(f"loader spine is all-NULL somewhere: {spine_dead} -- R3 has regressed")
    print(f"  all-NULL columns in stg + stg_gql: {len(census)} "
          f"(plan section 5 reported {ALL_NULL_REPORTED}; this count moves with the data)")
    print(f"    of which loader spine {SPINE}: {len(spine_dead)} (plan says 0)")
    for key in sorted(census):
        print(f"      {key[0]}.{key[1]}.{key[2]}  rows={census[key]}")

    print(f"  plan's {len(DEAD_CLAIMED)}-column drop list, checked:")
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
    # Future-dated scores are all-NULL on purpose -- those games have not been played. How many
    # there are changes weekly, so assert the shape and not the count.
    future = [
        k for k in unlisted if FUTURE_DATED.match(k[1]) and FUTURE_DATED_COLUMN.match(k[2])
    ]
    other = [k for k in unlisted if k not in future]
    print(f"  future-dated scores, kept on purpose: {len(future)}")
    if other:
        fails.append(f"all-NULL but neither on the drop list nor a future-dated score: {other}")
        print("  all-NULL but on neither list -- triage these:")
        for key in other:
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

    assert _selftest_structure() == 0, "structure check is not PFF-proof"
    print("selftest ok")
    return 0


def _selftest_structure() -> int:
    """A minimal warehouse, then the same one after PFF's S5 lands.

    The point of this check: a new source must not fail step 0. `stg` growing by 19
    `pff_*` tables is the concrete case, and it is why the table counts are printed
    rather than asserted.
    """
    con = duckdb.connect(":memory:")
    for schema in ("raw", "stg", "stg_gql"):
        con.execute(f"CREATE SCHEMA {schema}")

    def make(schema: str, name: str) -> None:
        con.execute(f'CREATE TABLE "{schema}"."{name}" (x INTEGER)')

    for entity, name in GQL_ENTITY_TO_STG.items():
        make("stg_gql", name)
        make("raw", GQL_ENTITY_TO_RAW[entity])
    for name in COLLIDERS:
        make("stg", name)

    assert check_structure(con) == [], "a clean warehouse must pass"

    # S5: 19 PFF tables land in `stg`. Nothing about the plan's argument changes.
    for i in range(19):
        make("stg", f"pff_table_{i}")
    fails = check_structure(con)
    assert fails == [], f"PFF broke step 0: {fails}"

    # Guard the checks that must still bite.
    make("stg", "gql_leftover")
    assert any("gql_-prefixed" in f for f in check_structure(con))
    con.execute('DROP TABLE "stg"."gql_leftover"')

    make("stg", "athlete")  # a fourth collider
    assert any("colliders" in f for f in check_structure(con))
    con.execute('DROP TABLE "stg"."athlete"')

    con.execute(f'DROP TABLE "stg_gql"."{COLLIDERS[0]}"')
    assert any("missing" in f for f in check_structure(con))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/cfb.duckdb")
    ap.add_argument("--coverage", action="store_true", help="year span per pair, then exit")
    ap.add_argument("--camel", action="store_true", help="list camelCase table names, then exit")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()

    con = duckdb.connect(args.db, read_only=True)
    if args.coverage:
        report_coverage(con)
        return 0
    if args.camel:
        for schema, table in con.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema IN ('stg', 'stg_gql') ORDER BY 1, 2"
        ).fetchall():
            if CAMEL_CASE.search(table):
                print(f"{schema}.{table}")
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
