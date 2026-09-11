import duckdb
import pytest

from cfb_system_maker.duckdb_load import explode_stg_lists


@pytest.fixture()
def con():
    con = duckdb.connect()
    con.execute("CREATE SCHEMA stg")
    yield con
    con.close()


def _rows(con, table):
    return con.execute(f'SELECT COUNT(*) FROM stg."{table}"').fetchone()[0]


def test_list_column_becomes_child_at_element_grain(con):
    con.execute(
        """
        CREATE TABLE stg.games AS
        SELECT * FROM (VALUES
          (1, [{'team': 'A', 'points': 7}, {'team': 'B', 'points': 3}]),
          (2, [{'team': 'C', 'points': 10}]),
          (3, NULL)
        ) t(gameId, teams)
        """
    )
    reports = explode_stg_lists(con)
    assert [r.name for r in reports] == ["games__teams"]
    assert _rows(con, "games") == 3, "parent grain must not change"
    assert _rows(con, "games__teams") == 3
    got = con.execute(
        'SELECT "gameId", teams_idx, teams_team, teams_points'
        ' FROM stg.games__teams ORDER BY "gameId", teams_idx'
    ).fetchall()
    assert got == [(1, 1, "A", 7), (1, 2, "B", 3), (2, 1, "C", 10)]


def test_child_count_matches_summed_list_length(con):
    con.execute(
        "CREATE TABLE stg.roster AS SELECT * FROM (VALUES"
        " (1, ['a', 'b', 'c']), (2, []), (3, ['d'])) t(playerId, recruitIds)"
    )
    explode_stg_lists(con)
    expected = con.execute(
        'SELECT sum(coalesce(len("recruitIds"), 0)) FROM stg.roster'
    ).fetchone()[0]
    assert _rows(con, "roster__recruit_ids") == expected


def test_nested_lists_recurse_one_table_per_level(con):
    con.execute(
        """
        CREATE TABLE stg.stats AS
        SELECT 1 AS gameId, [
          {'team': 'A', 'cats': [{'name': 'rush', 'value': 1}, {'name': 'pass', 'value': 2}]}
        ] AS teams
        """
    )
    explode_stg_lists(con)
    assert _rows(con, "stats__teams") == 1
    assert _rows(con, "stats__teams__teams_cats") == 2


def test_sibling_lists_do_not_cross_product(con):
    con.execute(
        "CREATE TABLE stg.t AS SELECT 1 AS id, [1, 2, 3] AS a, [9, 8] AS b"
    )
    explode_stg_lists(con)
    assert _rows(con, "t__a") == 3
    assert _rows(con, "t__b") == 2
    assert "b" not in {
        row[0] for row in con.execute("DESCRIBE stg.t__a").fetchall()
    }


def test_json_array_and_object_and_scalar(con):
    con.execute(
        """
        CREATE TABLE stg.an AS SELECT * FROM (VALUES
          (1, '[{"id": 5}, {"id": 6}]'::JSON, '{"clock": "0:12"}'::JSON, '22.5'::JSON),
          (2, '[{"id": 7}]'::JSON, '{"clock": "1:00"}'::JSON, '3'::JSON)
        ) t(event_id, ranks, last_play, spOffense)
        """
    )
    reports = explode_stg_lists(con)
    errors = {r.name: r.error for r in reports if r.error}
    # `an__sp_offense`, not `an__spOffense`: the child table name is one the loader
    # invents, so it follows repo convention, while the column it was built from keeps
    # CFBD's spelling. Snake-casing the columns too would mean renaming every camelCase
    # field in `stg`.
    assert "an__sp_offense" in errors, "scalar JSON is reported, not exploded"
    assert _rows(con, "an__ranks") == 3
    assert _rows(con, "an__last_play") == 2
    assert con.execute(
        "SELECT last_play_clock FROM stg.an__last_play ORDER BY event_id"
    ).fetchall() == [("0:12",), ("1:00",)]


def test_numeric_json_keys_become_a_column(con):
    con.execute(
        """
        CREATE TABLE stg.sb AS SELECT 1 AS event_id,
          '{"15": {"odds": -110}, "71": {"odds": -105}}'::JSON AS markets
        """
    )
    explode_stg_lists(con)
    assert con.execute(
        "SELECT markets_key, markets_odds FROM stg.sb__markets ORDER BY markets_key"
    ).fetchall() == [("15", -110), ("71", -105)]


def test_rerun_is_idempotent(con):
    con.execute("CREATE TABLE stg.t AS SELECT 1 AS id, [1, 2] AS a")
    first = explode_stg_lists(con)
    second = explode_stg_lists(con)
    assert [(r.name, r.rows) for r in first] == [(r.name, r.rows) for r in second]


def test_only_leaves_other_tables_children_alone(con):
    con.execute("CREATE TABLE stg.keep AS SELECT 1 AS id, [1, 2] AS a")
    con.execute("CREATE TABLE stg.redo AS SELECT 1 AS id, [1, 2, 3] AS a")
    explode_stg_lists(con)
    explode_stg_lists(con, only={"redo"})
    assert _rows(con, "keep__a") == 2
    assert _rows(con, "redo__a") == 3


def test_child_table_names_are_snake_cased(con):
    """The loader invents `<parent>__<column>`, and used to paste the column in verbatim --
    `stg.games__awayLineScores`, `stg.teams__alternateNames`. 13 tables carried camelCase
    that way. The column keeps the vendor spelling; only the invented half changes."""
    con.execute(
        """
        CREATE TABLE stg.parent AS SELECT * FROM (VALUES
          (1, [{'x': 1}], [{'y': 2}])
        ) t(gameId, awayLineScores, teams_cumulativePpa)
        """
    )
    explode_stg_lists(con)
    children = {
        r[0]
        for r in con.execute(
            "SELECT table_name FROM duckdb_tables()"
            " WHERE schema_name = 'stg' AND starts_with(table_name, 'parent__')"
        ).fetchall()
    }
    assert children == {"parent__away_line_scores", "parent__teams_cumulative_ppa"}
    # The parent's own column names are untouched -- `stg` preserves vendor field names.
    parent_cols = {r[0] for r in con.execute("DESCRIBE stg.parent").fetchall()}
    assert "gameId" in parent_cols
