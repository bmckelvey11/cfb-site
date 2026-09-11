import duckdb
import pytest

from cfb_system_maker.duckdb_load import drop_dead_columns


def _con():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    con.execute("CREATE SCHEMA raw")
    return con


def _columns(con, schema, table):
    return {
        r[0]
        for r in con.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema=? AND table_name=?",
            [schema, table],
        ).fetchall()
    }


def test_drops_all_null_spine_column_and_keeps_payload_twin():
    """The stg.games case: season_type 100% NULL, seasonType carries the value."""
    con = _con()
    con.execute(
        """
        CREATE TABLE stg.games AS SELECT * FROM (VALUES
          (1, 2023, 1, CAST(NULL AS VARCHAR), 'regular'),
          (2, 2023, 2, CAST(NULL AS VARCHAR), 'postseason')
        ) t(gameId, season, week, season_type, seasonType)
        """
    )
    reports = drop_dead_columns(con)

    assert [r.error for r in reports] == [None]
    assert _columns(con, "stg", "games") == {
        "gameId",
        "season",
        "week",
        "seasonType",
    }
    # The trap this closes: the filter now errors instead of returning nothing.
    with pytest.raises(duckdb.Error):
        con.execute("SELECT count(*) FROM stg.games WHERE season_type = 'postseason'")
    assert (
        con.execute(
            "SELECT count(*) FROM stg.games WHERE seasonType = 'postseason'"
        ).fetchone()[0]
        == 1
    )


def test_partially_populated_spine_column_survives():
    con = _con()
    con.execute(
        "CREATE TABLE stg.lines AS SELECT * FROM (VALUES"
        " (2023), (NULL)) t(season)"
    )
    assert drop_dead_columns(con) == []
    assert "season" in _columns(con, "stg", "lines")


def test_raw_spine_columns_are_left_alone():
    """`raw` spine columns are load provenance, not a query surface."""
    con = _con()
    con.execute(
        "CREATE TABLE raw.calendar AS SELECT '{}' AS payload,"
        " CAST(NULL AS INTEGER) AS season"
    )
    assert drop_dead_columns(con) == []
    assert "season" in _columns(con, "raw", "calendar")


def test_every_stg_table_is_covered_and_rerun_is_idempotent():
    con = _con()
    con.execute(
        "CREATE TABLE stg.calendar_gql AS SELECT CAST(NULL AS INTEGER) AS season,"
        " 2002 AS year, 1 AS week"
    )
    assert len(drop_dead_columns(con)) == 1
    assert _columns(con, "stg", "calendar_gql") == {"year", "week"}
    assert drop_dead_columns(con) == []


def test_empty_table_drops_its_spine_columns():
    """count() of an empty table is 0 -- the column is dead either way."""
    con = _con()
    con.execute("CREATE TABLE stg.venues (venueId INTEGER, season INTEGER)")
    assert len(drop_dead_columns(con)) == 1
    assert _columns(con, "stg", "venues") == {"venueId"}


# --------------------------------------------------------- section 5's named drop list
#
# The spine half above is derived: any all-NULL `season`/`week`/`season_type` goes. This
# half is *named*, because a derived sweep would take a column the moment a source stopped
# filling it. What both halves share is the fail-closed guard, and that is what these pin.


def test_drops_a_named_dead_column():
    """`stg.recruit.overallRank` is 0.00 filled across all 93,363 rows -- the payload
    carries the key and the source never fills it, so there is no writer to fix."""
    con = _con()
    con.execute(
        """
        CREATE TABLE stg.recruit AS SELECT * FROM (VALUES
          (1, 'A', CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE)),
          (2, 'B', CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE))
        ) t(recruitId, name, overallRank, positionRank)
        """
    )
    drop_dead_columns(con)
    assert _columns(con, "stg", "recruit") == {"recruitId", "name"}


def test_a_named_dead_column_that_went_live_is_kept():
    """The whole reason the list is safe to re-run after a re-scrape. If CFBD starts
    filling overallRank, the sweep must leave it alone rather than delete live data --
    the same guard the spine half uses, and the reason this is not a one-time migration."""
    con = _con()
    con.execute(
        """
        CREATE TABLE stg.recruit AS SELECT * FROM (VALUES
          (1, 'A', 12.0, CAST(NULL AS DOUBLE)),
          (2, 'B', CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE))
        ) t(recruitId, name, overallRank, positionRank)
        """
    )
    drop_dead_columns(con)
    assert "overallRank" in _columns(con, "stg", "recruit")
    assert "positionRank" not in _columns(con, "stg", "recruit")


def test_the_named_list_is_table_scoped_not_column_scoped():
    """`abbreviation` is dead on stg.poll_type and alive on core-bound tables like
    stg.conferences. A name-only match would take both."""
    con = _con()
    con.execute(
        "CREATE TABLE stg.poll_type AS SELECT 1 AS pollTypeId,"
        " CAST(NULL AS VARCHAR) AS abbreviation"
    )
    con.execute(
        "CREATE TABLE stg.conferences AS SELECT 1 AS conferenceId,"
        " CAST(NULL AS VARCHAR) AS abbreviation"
    )
    drop_dead_columns(con)
    assert _columns(con, "stg", "poll_type") == {"pollTypeId"}
    assert "abbreviation" in _columns(con, "stg", "conferences")


def test_superseded_rest_sources_are_not_staged():
    """Bucket A: GraphQL holds every populated column and at least as many distinct keys.
    Skipped at explode time rather than dropped, because `raw` is out of scope and the
    next explode would rebuild anything dropped from `stg`."""
    from cfb_system_maker.duckdb_load import _SUPERSEDED_REST, explode_payloads

    con = _con()
    for name in sorted(_SUPERSEDED_REST) + ["conferences"]:
        con.execute(
            f"CREATE TABLE raw.{name} AS SELECT "
            "'{\"a\": 1}' AS payload, 'f.json' AS _source_file"
        )
    # Asserted on the reports, not on `stg`: this fixture's payload is too thin for the
    # exploder to finish, and what is under test is which sources it *attempts*.
    attempted = {r.name for r in explode_payloads(con)}
    assert not (attempted & _SUPERSEDED_REST), f"superseded sources were staged: {attempted}"
    assert "conferences" in attempted, "the skip took a source it should not have"


def test_an_team_no_longer_selects_overtime_losses():
    """The seventh dead column was written by name, so the sweep was the wrong tool --
    ActionNetwork emits `standings.overtime_losses` on all 10,868 rows and it is null on
    every one. Fixed at the writer so it is never created, not created then dropped."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "cfb_system_maker"
              / "duckdb_load.py").read_text(encoding="utf-8")
    block = source[source.index("_AN_TEAM_SQL = "):]
    block = block[:block.index('"""', block.index('"""') + 3)]
    assert "overtime_losses" not in block.replace(
        "-- `standings.overtime_losses` is dropped, not missed.", "")
