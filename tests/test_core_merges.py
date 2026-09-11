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
    """`fact_game` is REST-defined: every in-span game REST carries reaches the fact, and the
    78,030 pre-span GraphQL games belong in `fact_game_historical`. Joining `stg.games` is
    the point -- this asked `stg.game` alone until 2026-09-11 and read 0 only because REST
    happened to be a superset of in-span GraphQL. CFBD falsified that by dropping game
    401866625 from its REST payload, and the assertion failed without `_build_fact_game`
    having done anything. What the builder owes is this number; supersetness was never its
    job, and `test_graphql_only_games_stay_a_handful` covers the gap that leaves."""
    assert con.execute("""
        SELECT count(*) FROM stg.games r
        LEFT JOIN core.fact_game f ON f.game_id = r."gameId"
        WHERE f.game_id IS NULL
          AND r.season >= (SELECT min(season) FROM core.dim_week)
    """).fetchone()[0] == 0


def test_graphql_only_games_stay_a_handful(con):
    """The blind spot the REST join above opens, held shut.

    In-span games GraphQL has and REST does not are a vendor divergence, not a merge defect,
    so they must not fail the builder's test -- but unbounded they would hide a half-loaded
    `stg.games` or a `graphql/game.json` staled by another fortnight. One known member as of
    2026-09-11: 401866625, Campbell vs Western Carolina 2026-09-05, which CFBD removed from
    REST between the 09-10 and 09-11 pulls. The ceiling is deliberately loose, like the sign
    bounds -- it catches a blow-up, not a vendor correcting a game or two."""
    assert con.execute("""
        SELECT count(*) FROM stg.game g
        LEFT JOIN stg.games r ON r."gameId" = g."gameId"
        WHERE r."gameId" IS NULL
          AND g.season >= (SELECT min(season) FROM core.dim_week)
    """).fetchone()[0] <= 25


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


def test_the_two_draftkings_spellings_collapse_to_one_key(con):
    """CFBD emits DraftKings twice in the same `lines` array on 215 games, and
    `stg.lines_provider` carries both spellings under separate ids (CFBD's 100 and the
    synthetic 888888 `_AN_BOOK_PROVIDER` assigned the AN feed). Left split, a consumer
    filtering `provider_key = 'draftkings'` silently misses the other ~235 rows."""
    keys = {r[0] for r in con.execute(
        "SELECT DISTINCT provider_key FROM core.fact_game_line"
        " WHERE provider_key LIKE '%draft%'").fetchall()}
    assert keys == {"draftkings"}, f"the DraftKings key is still split: {keys}"


def test_the_caesars_family_is_left_alone(con):
    """The alias map covers one book on measured evidence, not every name that looks
    similar. `Caesars`, `Caesars (Pennsylvania)` and `Caesars Sportsbook (Colorado)` never
    share a game and hold disjoint season ranges -- consistent with a rename history *or*
    separate state licences, and nothing measured settles which. Merging on a guess
    destroys the distinction irreversibly, so this pins that it has not happened."""
    keys = {r[0] for r in con.execute(
        "SELECT DISTINCT provider_key FROM core.fact_game_line"
        " WHERE provider_key LIKE 'caesars%'").fetchall()}
    assert len(keys) >= 2, f"the Caesars variants were merged without evidence: {keys}"


def test_the_alias_is_one_rule_not_two(con):
    """`duckdb_core._provider_key` delegates to `normalize.provider_key`. Two definitions
    of what a book is called is how `core.fact_game_line` and `games.csv` end up
    disagreeing about whether a game has a DraftKings row at all."""
    from cfb_system_maker.duckdb_core import _provider_key
    from cfb_system_maker.normalize import PROVIDER_ALIASES, provider_key

    assert _provider_key("Draft Kings") == provider_key("Draft Kings") == "draftkings"
    assert PROVIDER_ALIASES == {"draft kings": "draftkings"}


# ------------------------------------------------------------ spread sign convention
#
# `GameRecord.spread` and `core.fact_game.selected_spread` are home-relative: negative when
# the home team is favoured. `_build_fact_game_line` inherits that from CFBD without
# checking, and `_merge_game_lines` carried 8,575 ActionNetwork rows in on top. An inverted
# book raises nothing and moves no row count -- a backtest just reads the favourite as the
# underdog for that book. Measured by scripts/audit_line_sign_convention.py; see
# docs/lines-spread-sign-2026-09-10.md.


@pytest.fixture(scope="module")
def graded(con):
    """(provider_key, rows, cover_pct, mean_resid) per book with enough graded games."""
    return con.execute("""
        SELECT l.provider_key, count(*),
               100.0 * count(*) FILTER (
                 WHERE (f.home_points - f.away_points) + l.spread_close > 0) / count(*),
               avg(l.spread_close + (f.home_points - f.away_points))
        FROM core.fact_game_line l JOIN core.fact_game f USING (game_id)
        WHERE l.spread_close IS NOT NULL
          AND f.home_points IS NOT NULL AND f.away_points IS NOT NULL
        GROUP BY 1 HAVING count(*) >= 20
    """).fetchall()


def test_no_book_quotes_an_inverted_spread(graded):
    """`spread + (home_points - away_points)` cancels to ~0 when the spread is
    home-relative. An inverted book lands at roughly *twice* the mean spread -- around
    -20 -- so the bound is loose on purpose: it is here to catch a sign flip, not to
    police how sharp a book is."""
    assert graded, "no graded line rows at all -- the check has stopped working"
    for key, rows, _cover, resid in graded:
        assert -5.0 < resid < 5.0, (
            f"{key}: mean(spread + margin) = {resid:.2f} over {rows} graded games; "
            f"a home-relative spread cancels to ~0, an inverted one to ~2x the spread"
        )


def test_no_book_covers_at_a_degenerate_rate(graded):
    """The second, independent half. A sign flip sends the cover rate to ~0% or ~100%
    while `mean_resid` could in principle be dragged toward zero by a lopsided sample."""
    for key, rows, cover, _resid in graded:
        assert 25.0 < cover < 75.0, (
            f"{key}: covers {cover:.1f}% of {rows} graded games -- a real book sits near 50%"
        )


def test_the_five_actionnetwork_books_are_graded_at_all(graded):
    """The books the union added are the ones no code had ever checked. If they stop
    arriving, the two tests above pass vacuously for them."""
    have = {key for key, *_ in graded}
    assert {"circa", "fanduel", "betmgm", "bet365", "pinnacle"} <= have, (
        f"ActionNetwork books missing from the graded set: {have}"
    )
