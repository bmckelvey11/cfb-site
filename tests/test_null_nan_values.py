"""`null_nan_values`: the GraphQL "NaN" string and the NaN double it casts to both
become NULL in `stg`, and nothing else is touched."""

import json

import duckdb

from cfb_system_maker.duckdb_load import (
    build_duckdb,
    explode_payloads,
    null_nan_values,
)


def _con():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    return con


def _type(con, table, column):
    return con.execute(
        "SELECT data_type FROM information_schema.columns"
        " WHERE table_schema='stg' AND table_name=? AND column_name=?",
        [table, column],
    ).fetchone()[0]


def test_json_column_of_numbers_and_nan_strings_becomes_double_with_nulls():
    """The stg.game_lines case: `json_group_structure` typed `spread` JSON because a
    few rows carry the string "NaN"."""
    con = _con()
    con.execute(
        """
        CREATE TABLE stg.game_lines AS SELECT * FROM (VALUES
          (1, '"NaN"'::JSON), (2, '-3.5'::JSON), (3, '7'::JSON), (4, NULL::JSON)
        ) t(gameId, spread)
        """
    )
    reports = null_nan_values(con)

    assert [(r.name, r.files, r.rows, r.error) for r in reports] == [
        ("game_lines.spread", 1, 1, None)
    ]
    assert _type(con, "game_lines", "spread") == "DOUBLE"
    assert con.execute(
        "SELECT gameId, spread FROM stg.game_lines ORDER BY gameId"
    ).fetchall() == [(1, None), (2, -3.5), (3, 7.0), (4, None)]
    # The trap this closes: coalesce no longer carries the hole as a value.
    assert con.execute(
        "SELECT coalesce(spread, 99) FROM stg.game_lines WHERE gameId = 1"
    ).fetchone()[0] == 99


def test_double_column_has_its_nans_nulled():
    """What a downstream TRY_CAST of the string leaves behind."""
    con = _con()
    con.execute(
        "CREATE TABLE stg.t AS SELECT * FROM (VALUES"
        " ('NaN'::DOUBLE), (1.5::DOUBLE), (NULL::DOUBLE)) v(x)"
    )
    reports = null_nan_values(con)

    assert [(r.name, r.rows, r.error) for r in reports] == [("t.x", 1, None)]
    assert con.execute("SELECT count(*) FILTER (WHERE isnan(x)) FROM stg.t").fetchone()[0] == 0
    assert con.execute("SELECT count(x) FROM stg.t").fetchone()[0] == 1


def test_a_genuinely_mixed_json_column_is_left_alone():
    """An object next to numbers is a real mixed payload, not a spelled-out hole."""
    con = _con()
    con.execute(
        """
        CREATE TABLE stg.t AS SELECT * FROM (VALUES
          ('"NaN"'::JSON), ('1.5'::JSON), ('{"a": 1}'::JSON)
        ) v(x)
        """
    )
    assert null_nan_values(con) == []
    assert _type(con, "t", "x") == "JSON"


def test_json_column_without_nan_and_clean_doubles_are_not_reported():
    con = _con()
    con.execute("CREATE TABLE stg.t AS SELECT * FROM (VALUES ('\"x\"'::JSON, 1.5::DOUBLE)) v(j, d)")
    assert null_nan_values(con) == []
    assert _type(con, "t", "j") == "JSON"


def test_rerun_is_idempotent():
    con = _con()
    con.execute(
        "CREATE TABLE stg.t AS SELECT * FROM (VALUES ('\"NaN\"'::JSON), ('2'::JSON)) v(x)"
    )
    assert len(null_nan_values(con)) == 1
    assert null_nan_values(con) == []
    assert _type(con, "t", "x") == "DOUBLE"


def test_explode_payloads_runs_the_pass_on_a_graphql_dump(tmp_path):
    """End to end: a gameLines dump with a "NaN" spread lands in stg as DOUBLE/NULL."""
    gql = tmp_path / "graphql"
    gql.mkdir()
    (gql / "gameLines.json").write_text(
        json.dumps([
            {"gameId": 1, "linesProviderId": 1, "spread": "NaN", "overUnder": 41.5},
            {"gameId": 2, "linesProviderId": 1, "spread": -6.5, "overUnder": "NaN"},
            {"gameId": 3, "linesProviderId": 1, "spread": 3, "overUnder": 55},
        ]),
        encoding="utf-8",
    )
    db_path, _ = build_duckdb(tmp_path, include_actionnetwork=False)
    reports = explode_payloads(db_path)

    fixed = {r.name: r.rows for r in reports
             if r.name in ("game_lines.spread", "game_lines.overUnder")}
    assert fixed == {"game_lines.overUnder": 1, "game_lines.spread": 1}
    con = duckdb.connect(str(db_path), read_only=True)
    assert _type(con, "game_lines", "spread") == "DOUBLE"
    assert _type(con, "game_lines", "overUnder") == "DOUBLE"
    assert con.execute(
        'SELECT gameId, spread, "overUnder" FROM stg.game_lines ORDER BY gameId'
    ).fetchall() == [(1, None, 41.5), (2, -6.5, None), (3, 3.0, 55.0)]
