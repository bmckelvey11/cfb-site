"""Bucket C/B merges: the key must stay unique and the join must stay a full outer.

These run against the live warehouse when it has the sources, and skip when it does not --
the same stance the PFF and odds tests take. What they defend is the pair of mistakes a
merge makes silently: a fan-out from a non-unique key, and a left join that truncates the
side with more rows.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT  # noqa: E402

DB = DATA_ROOT / "cfb.duckdb"

# (table, key expression) -- one row per key is the invariant every merge has to hold.
KEYED = [
    ("core.dim_coach", "(coach_id)"),
    ("core.dim_draft_pick", "(year, round, pick)"),
    ("core.dim_recruit", "(recruit_id)"),
    ("core.fact_team_talent", "(season, school)"),
    ("core.fact_coach_season", "(coach_id, team_id, season)"),
]


@pytest.fixture(scope="module")
def con():
    if not DB.exists():
        pytest.skip("no warehouse on disk")
    import duckdb

    connection = duckdb.connect(str(DB), read_only=True)
    have = {r[0] for r in connection.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'core'"
    ).fetchall()}
    if "dim_draft_pick" not in have:
        pytest.skip("merges not built in this warehouse")
    yield connection
    connection.close()


@pytest.mark.parametrize("table,key", KEYED)
def test_the_merge_key_is_unique(con, table, key):
    """A fan-out is how a bad key shows up, and it shows up as a row count nobody checks.

    `stg.talent` carries three byte-identical duplicate (season, team) rows; left in, they
    made core.fact_team_talent three rows long, which is exactly how they were found.
    """
    rows, distinct = con.execute(f"SELECT count(*), count(DISTINCT {key}) FROM {table}").fetchone()
    assert rows == distinct, f"{table} fans out on {key}: {rows} rows, {distinct} keys"


@pytest.mark.parametrize("table", [t for t, _ in KEYED if t != "core.dim_coach"])
def test_the_merge_kept_the_graphql_only_rows(con, table):
    """Full outer, not left. GraphQL out-rows REST on every pair, so a join anchored on the
    REST side silently truncates -- and would still look like a working table."""
    sources = {r[0]: r[1] for r in con.execute(
        f"SELECT _source, count(*) FROM {table} GROUP BY 1").fetchall()}
    assert sources.get("gql", 0) > 0, f"{table} kept no GraphQL-only rows: {sources}"
    assert sources.get("both", 0) > 0, f"{table} matched nothing across the two: {sources}"


def test_talent_keeps_the_rest_only_rows(con):
    """The 17 school-seasons REST has and GraphQL does not (Jacksonville, St. Francis (PA))
    are why stg.talent is not droppable. If they stop arriving, the R6 verdict changes."""
    rest_only = con.execute(
        "SELECT count(*) FROM core.fact_team_talent WHERE _source = 'rest'").fetchone()[0]
    assert rest_only > 0, "no REST-only talent rows: either the merge or the source changed"


def test_coach_season_unmatched_exists_even_when_empty(con):
    """It is currently 0 -- every coaches__seasons name resolves to exactly one coach and
    every school to a dim_team row. The table still has to exist, because a populated one is
    the only place an unresolvable row is preserved rather than guessed into the fact."""
    assert con.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = 'core' AND table_name = 'coach_season_unmatched'"
    ).fetchone()[0] == 1


def test_every_merge_builder_is_guarded():
    """build_core runs on every refresh. A builder that raises on a missing GraphQL-side table
    takes the whole rebuild down with it."""
    source = (REPO_ROOT / "cfb_system_maker" / "duckdb_core.py").read_text(encoding="utf-8")
    for fn in ("_build_dim_coach", "_build_dim_draft_pick", "_build_dim_recruit",
               "_build_fact_team_talent", "_build_fact_coach_season"):
        block = source[source.index(f"def {fn}("):]
        block = block[:block.index("\ndef ", 1)]
        assert "_has(con," in block and "return False" in block, f"{fn} is unguarded"


# ---------------------------------------------------------- merges into existing tables
#
# The five above build tables that did not exist, so a bad join is loud. These four merge
# into tables `core` already had and consumers already query, so the failure is quiet: a
# row count that moves. ADR-0001 is the rule -- fact_game gains columns, not rows.
# Measured in docs/core-merge-bucket-c-2026-09-10.md.


def test_fact_game_did_not_grow_to_hold_graphql_rows(con):
    """GraphQL reaches back to 1869. Every one of its in-span games is already in
    fact_game; the 78,030 older ones belong in fact_game_historical, not here."""
    assert con.execute("""
        SELECT count(*) FROM stg.game g
        LEFT JOIN core.fact_game f ON f.game_id = g."gameId"
        WHERE f.game_id IS NULL
          AND g.season >= (SELECT min(season) FROM core.dim_week)
    """).fetchone()[0] == 0


def test_fact_game_historical_stays_out_of_the_fact(con):
    """Two tables holding the same game_id is how a double count starts."""
    if not con.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = 'core' AND table_name = 'fact_game_historical'"
    ).fetchone()[0]:
        pytest.skip("fact_game_historical not built in this warehouse")
    overlap, span_max = con.execute("""
        SELECT (SELECT count(*) FROM core.fact_game_historical h
                 JOIN core.fact_game f ON f.game_id = h.game_id),
               (SELECT max(season) FROM core.fact_game_historical)
    """).fetchone()
    assert overlap == 0, f"{overlap} games in both fact_game and fact_game_historical"
    assert span_max < con.execute(
        "SELECT min(season) FROM core.dim_week").fetchone()[0]


def test_fact_game_conference_ids_match_the_graphql_fk(con):
    """fact_game resolved a conference by *name*, and 44 dim_conference names are held by
    more than one row -- so the lookup picked arbitrarily among them. 3,714 home and 3,985
    away ids disagreed with GraphQL's FK while naming the same conference."""
    assert con.execute("""
        SELECT count(*) FROM core.fact_game f
        JOIN stg.game g ON g."gameId" = f.game_id
        WHERE (f.home_conference_id IS NOT NULL AND g."homeConferenceId" IS NOT NULL
               AND f.home_conference_id <> g."homeConferenceId")
           OR (f.away_conference_id IS NOT NULL AND g."awayConferenceId" IS NOT NULL
               AND f.away_conference_id <> g."awayConferenceId")
    """).fetchone()[0] == 0


def test_dim_conference_carries_division(con):
    """The one GraphQL column worth taking, and what tells the four 'Big Sky' rows apart.
    srName fills 1 of 256 and is deliberately not carried."""
    cols = {r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'core' AND table_name = 'dim_conference'").fetchall()}
    assert "division" in cols
    assert "sr_name" not in cols and "srName" not in cols


def test_the_line_merge_did_not_lose_a_rest_offer(con):
    """A repoint at stg.game_lines was rejected because it drops 278 REST offers
    game_lines has no row for. The full outer is what keeps them; `_source = 'rest'`
    going to zero means someone turned it back into a left join."""
    if "_source" not in {r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'core' "
        "AND table_name = 'fact_game_line'").fetchall()}:
        pytest.skip("line merge not built in this warehouse")
    sources = {r[0]: r[1] for r in con.execute(
        "SELECT _source, count(*) FROM core.fact_game_line GROUP BY 1").fetchall()}
    assert sources.get("rest", 0) > 0, f"REST-only line rows are gone: {sources}"
    assert sources.get("gql", 0) > 0, f"no ActionNetwork books reached core: {sources}"


def test_no_nan_reached_the_line_table(con):
    """stg.game_lines spells a missing number NaN, not NULL -- 3,414 `overUnder` and
    65 `spread` rows. coalesce carries NaN happily, and a NaN in spread_close compares
    false against everything, so it reads as a value and behaves as a hole. This is the
    check that caught it: the slow agreement suite moved to `assert nan == None`."""
    for col in ("spread_close", "spread_open", "total_close", "total_open"):
        n = con.execute(
            f"SELECT count(*) FROM core.fact_game_line WHERE isnan({col})").fetchone()[0]
        assert n == 0, f"{n} NaN values in core.fact_game_line.{col}"


def test_line_conflicts_are_preserved_not_discarded(con):
    """REST wins a conflict because that is what `core` already held, which makes the
    merge additive -- not because it is right on the merits. The table is where that
    open question lives; an empty one means the evidence was thrown away."""
    if not con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'core' "
        "AND table_name = 'fact_game_line_conflicts'").fetchone()[0]:
        pytest.skip("line merge not built in this warehouse")
    assert con.execute(
        "SELECT count(*) FROM core.fact_game_line_conflicts").fetchone()[0] > 0


def test_source_exists_even_without_the_actionnetwork_tape(con):
    """`_source` is declared by `_build_fact_game_line` with a 'rest' default, not added by
    `_merge_game_lines`. A table whose columns depend on whether an optional source was
    present is a trap: a consumer selects `_source`, finds it on the live warehouse, and
    gets a Binder Error on any build without `stg.game_lines`. That is exactly how it was
    found -- a fixture-built test broke while the live one passed."""
    source = (REPO_ROOT / "cfb_system_maker" / "duckdb_core.py").read_text(encoding="utf-8")
    create = source[source.index("CREATE TABLE core.fact_game_line ("):]
    create = create[:create.index('"""')]
    assert "_source VARCHAR NOT NULL DEFAULT 'rest'" in create
