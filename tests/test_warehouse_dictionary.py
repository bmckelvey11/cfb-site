"""The discovery layer has to stay honest about two things.

1. `source_system_of` is the only place the warehouse records which pipeline wrote a
   table, now that the `graphql` schema is gone (ADR-0003) and the `stg` collapse put
   REST and GraphQL tables side by side under bare names. If it silently reclassifies,
   `meta.table_dictionary` starts lying about provenance and nothing else notices.

2. `meta.relationship` exists *because* the lossy edges are real and intended -- it stands
   in for foreign keys DuckDB cannot add. Its whole value is that `is_lossy` is derived
   from a measurement, so a test that pinned a hand-set flag would defeat the point. What
   is pinned here instead is the distinction the measurement has to preserve: an orphan
   (key present, no parent) is not a NULL key (unjoinable, but not broken). A foreign key
   would blur those two; if `_measure_edge` blurs them too, the table is no better.

Fixture-built, never against `DATA_ROOT/cfb.duckdb`.
"""

import sys
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from cfb_system_maker.graphql_client import GQL_ENTITY_TO_STG  # noqa: E402
from cfb_system_maker.warehouse_dictionary import (  # noqa: E402
    TABLE_NOTES,
    _EDGES,
    _measure_edge,
    build_dictionary,
    source_system_of,
)


@pytest.mark.parametrize(
    "schema, name, expected",
    [
        ("stg", "games", "rest"),  # the collider pair this whole module exists for
        ("stg", "game", "gql"),
        ("stg", "calendar", "rest"),
        ("stg", "calendar_gql", "gql"),
        ("stg", "pff_passing", "pff"),  # a vendor, NOT rest -- never touched CFBD
        ("stg", "an_history_tick", "actionnetwork"),
        ("stg", "oa_odds_tick", "oddsapi"),
        ("stg", "massey_ranks", "massey"),
        ("stg", "plays", "rest"),
        ("core", "fact_game", "core"),
        ("meta", "load_report", "meta"),
    ],
)
def test_source_system_separates_the_pipelines(schema, name, expected):
    assert source_system_of(schema, name) == expected


def test_every_graphql_destination_classifies_as_gql():
    """The stg collapse means a GraphQL table's name no longer marks it. This map is
    the only remaining record, so drifting off it is how provenance gets lost."""
    for name in set(GQL_ENTITY_TO_STG.values()):
        assert source_system_of("stg", name) == "gql", name


def test_notes_are_written_for_both_halves_of_every_collider_pair():
    """A note on only one of `game`/`games` is worse than none: it implies the
    unannotated one is the plain choice."""
    for a, b in [
        ("game", "games"),
        ("calendar", "calendar_gql"),
        ("conference", "conferences"),
        ("recruit", "recruits"),
        ("coach", "coaches"),
        ("coach_season", "coach_seasons"),
        ("draft_picks", "draft_picks_gql"),
        ("predicted_points", "predicted_points_gql"),
    ]:
        assert ("stg", a) in TABLE_NOTES, a
        assert ("stg", b) in TABLE_NOTES, b


def test_postgame_suffix_is_reserved_for_wholly_result_informed_tables():
    """`fact_game` is mixed -- schedule and teams are pre-game, points are not --
    and correctly has no suffix. The suffix has to mean something narrower than
    "contains a result", or it stops carrying information."""
    suffixed = {n for (s, n) in TABLE_NOTES if s == "core" and n.endswith("_postgame")}
    assert suffixed == {
        "fact_team_season_rating_postgame",
        "fact_team_season_record_postgame",
        "fact_team_ats_postgame",
        "fact_drive_postgame",
    }
    for name in suffixed:
        note = TABLE_NOTES[("core", name)]
        assert "RESULT-INFORMED" in note, name
    # The pre-game twins must say so, or the distinction lives only in the suffix.
    for name in ("fact_team_recruiting", "fact_team_returning_production"):
        assert "pre-game feature" in TABLE_NOTES[("core", name)], name
    # And the converse: an unsuffixed fact must not quietly claim to be wholly
    # result-informed. `fact_game_weather` is the case that tempts it.
    for (schema, name), note in TABLE_NOTES.items():
        if schema == "core" and name.startswith("fact_") and name not in suffixed:
            assert "RESULT-INFORMED throughout" not in note, name


def test_the_rating_merge_does_not_anchor_on_one_source():
    """GraphQL `ratings` is the widest source but stops at 2025, so building off it
    would drop the season currently being bet. The spine is a union for that
    reason; a refactor back to a single anchor is the regression to catch."""
    from cfb_system_maker.duckdb_core import _RATING_SOURCES

    tables = {t for _, t, _, _, _ in _RATING_SOURCES}
    assert {"sp", "fpi", "core_ratings"} <= tables, "the 2026-carrying sources"
    assert "ratings" in tables, "the wide GraphQL source"
    prefixes = [p for p, _, _, _, _ in _RATING_SOURCES]
    assert len(prefixes) == len(set(prefixes)), "prefixes must keep sources apart"


def test_every_edge_names_a_core_table_that_has_a_note():
    """An edge pointing at an undocumented table sends the reader nowhere."""
    for child, _, parent, _, _ in _EDGES:
        assert ("core", child) in TABLE_NOTES, child
        assert ("core", parent) in TABLE_NOTES, parent


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute("CREATE SCHEMA core")
    c.execute("CREATE TABLE core.dim_team (team_id INTEGER, school VARCHAR)")
    c.execute("INSERT INTO core.dim_team VALUES (1, 'Iowa'), (2, 'Iowa State')")
    c.execute("CREATE TABLE core.fact_game (game_id INTEGER, home_team_id INTEGER)")
    c.execute(
        "INSERT INTO core.fact_game VALUES (10, 1), (11, 2), (12, 99), (13, NULL)"
    )
    yield c
    c.close()


def test_an_orphan_is_not_a_null_key(con):
    """game 12 points at a team that does not exist; game 13 points at nothing at all.
    A FOREIGN KEY would reject the first and accept the second without distinguishing
    them. The point of the table is that it distinguishes them."""
    orphans, nulls = _measure_edge(con, "fact_game", "home_team_id", "dim_team", "team_id")
    assert (orphans, nulls) == (1, 1)


def test_a_clean_edge_measures_zero(con):
    con.execute("DELETE FROM core.fact_game WHERE game_id IN (12, 13)")
    assert _measure_edge(con, "fact_game", "home_team_id", "dim_team", "team_id") == (0, 0)


def test_a_missing_table_is_skipped_not_raised(con):
    """`build_core` skips merges whose stg source is absent, so `core` can be partial.
    The dictionary must survive that, or it turns a degraded build into a failed one."""
    assert _measure_edge(con, "fact_game", "home_team_id", "dim_nope", "team_id") is None


def test_build_dictionary_survives_a_partial_core(con):
    build_dictionary(con)
    rows = con.execute(
        "SELECT table_name, source_system FROM meta.table_dictionary ORDER BY table_name"
    ).fetchall()
    assert ("dim_team", "core") in rows
    # Only the two edges whose tables both exist here made it in.
    edges = con.execute(
        "SELECT child_table, parent_table, orphan_rows, is_lossy FROM meta.relationship"
    ).fetchall()
    assert edges == [("fact_game", "dim_team", 1, True)]


def test_the_dictionary_catalogues_itself_on_a_first_build(con):
    """Populate-then-create would list the two `meta` tables only when a *previous*
    build left them behind -- a census that depends on history rather than on the
    warehouse in front of you, and silently wrong on a fresh file."""
    build_dictionary(con)
    listed = {
        r[0]
        for r in con.execute(
            "SELECT table_name FROM meta.table_dictionary WHERE schema_name = 'meta'"
        ).fetchall()
    }
    assert {"table_dictionary", "relationship"} <= listed

    # Idempotent: a second build must not change the census.
    build_dictionary(con)
    again = {
        r[0]
        for r in con.execute(
            "SELECT table_name FROM meta.table_dictionary WHERE schema_name = 'meta'"
        ).fetchall()
    }
    assert again == listed


def test_views_are_listed_and_commented_like_tables(con):
    """`core.v_game` is the one object built purely to be queried directly. A table
    of contents that omits it sends people back to the facts it exists to spare
    them -- and the generated HTML catalog already does omit it, reading
    `duckdb_tables()` only."""
    con.execute("CREATE VIEW core.v_game AS SELECT * FROM core.fact_game")
    build_dictionary(con)
    row = con.execute(
        "SELECT object_type, source_system, note FROM meta.table_dictionary"
        " WHERE schema_name = 'core' AND table_name = 'v_game'"
    ).fetchone()
    assert row is not None, "the view is missing from the dictionary"
    assert row[0] == "view"
    assert row[1] == "core"
    assert row[2] == TABLE_NOTES[("core", "v_game")]

    # COMMENT ON TABLE would be wrong here; the comment must still land.
    comment = con.execute(
        "SELECT comment FROM duckdb_views()"
        " WHERE schema_name = 'core' AND view_name = 'v_game'"
    ).fetchone()[0]
    assert comment == TABLE_NOTES[("core", "v_game")]


def test_is_lossy_follows_the_measurement(con):
    """Not a pinned flag: drop the bad row and the same edge must flip to clean."""
    con.execute("DELETE FROM core.fact_game WHERE game_id = 12")
    build_dictionary(con)
    assert con.execute("SELECT is_lossy FROM meta.relationship").fetchall() == [(False,)]


def test_notes_reach_the_tables_as_comments(con):
    """`duckdb_tables().comment` is what a SQL client's object browser reads, so the
    dictionary being right is not enough on its own."""
    build_dictionary(con)
    comment = con.execute(
        "SELECT comment FROM duckdb_tables()"
        " WHERE schema_name = 'core' AND table_name = 'dim_team'"
    ).fetchone()[0]
    assert comment == TABLE_NOTES[("core", "dim_team")]
    assert "LEFT JOIN" in comment


def test_a_note_with_an_apostrophe_survives_inlining(con):
    """`COMMENT ON` takes no bind parameter, so the note is inlined. Several real notes
    contain `CFBD's` / `app's`; a naive f-string would truncate the statement there."""
    build_dictionary(con)
    for (schema, name), note in TABLE_NOTES.items():
        if "'" in note and schema == "core":
            stored = con.execute(
                "SELECT comment FROM duckdb_tables()"
                " WHERE schema_name = ? AND table_name = ?",
                [schema, name],
            ).fetchone()
            if stored:
                assert stored[0] == note, name
