import duckdb
import pytest

from cfb_system_maker.duckdb_load import drop_dead_spine_columns


def _con():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    con.execute("CREATE SCHEMA stg_gql")
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
    reports = drop_dead_spine_columns(con)

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
    assert drop_dead_spine_columns(con) == []
    assert "season" in _columns(con, "stg", "lines")


def test_raw_spine_columns_are_left_alone():
    """`raw` spine columns are load provenance, not a query surface."""
    con = _con()
    con.execute(
        "CREATE TABLE raw.calendar AS SELECT '{}' AS payload,"
        " CAST(NULL AS INTEGER) AS season"
    )
    assert drop_dead_spine_columns(con) == []
    assert "season" in _columns(con, "raw", "calendar")


def test_stg_gql_is_covered_and_rerun_is_idempotent():
    con = _con()
    con.execute(
        "CREATE TABLE stg_gql.calendar AS SELECT CAST(NULL AS INTEGER) AS season,"
        " 2002 AS year, 1 AS week"
    )
    assert len(drop_dead_spine_columns(con)) == 1
    assert _columns(con, "stg_gql", "calendar") == {"year", "week"}
    assert drop_dead_spine_columns(con) == []


def test_empty_table_drops_its_spine_columns():
    """count() of an empty table is 0 -- the column is dead either way."""
    con = _con()
    con.execute("CREATE TABLE stg.venues (venueId INTEGER, season INTEGER)")
    assert len(drop_dead_spine_columns(con)) == 1
    assert _columns(con, "stg", "venues") == {"venueId"}
