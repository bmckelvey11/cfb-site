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
    """build_core runs on every refresh. A builder that raises on a missing stg_gql table
    takes the whole rebuild down with it."""
    source = (REPO_ROOT / "cfb_system_maker" / "duckdb_core.py").read_text(encoding="utf-8")
    for fn in ("_build_dim_coach", "_build_dim_draft_pick", "_build_dim_recruit",
               "_build_fact_team_talent", "_build_fact_coach_season"):
        block = source[source.index(f"def {fn}("):]
        block = block[:block.index("\ndef ", 1)]
        assert "_has(con," in block and "return False" in block, f"{fn} is unguarded"
