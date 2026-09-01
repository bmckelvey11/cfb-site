import duckdb

from cfb_system_maker.duckdb_load import promote_timestamp_columns


def _con():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    return con


def test_promotes_all_three_source_formats():
    con = _con()
    con.execute(
        """
        CREATE TABLE stg.games AS SELECT * FROM (VALUES
          ('2023-09-02 16:00:00+00:00'),
          ('2023-09-02T16:00:00'),
          ('2023-09-02T16:00:00.000Z')
        ) t(startDate)
        """
    )
    reports = promote_timestamp_columns(con)

    assert [r.error for r in reports] == [None]
    typ = con.execute(
        "SELECT data_type FROM information_schema.columns"
        " WHERE table_schema='stg' AND column_name='startDate'"
    ).fetchone()[0]
    assert typ == "TIMESTAMP WITH TIME ZONE"
    # All three spellings denote the same UTC instant.
    assert con.execute("SELECT count(DISTINCT startDate) FROM stg.games").fetchone()[0] == 1


def test_naive_strings_are_read_as_utc_not_session_time():
    con = _con()
    con.execute("SET TimeZone = 'America/New_York'")
    con.execute("CREATE TABLE stg.games AS SELECT '2023-09-02T16:00:00' AS startDate")
    promote_timestamp_columns(con)
    assert con.execute(
        "SELECT startDate = TIMESTAMPTZ '2023-09-02 16:00:00+00:00' FROM stg.games"
    ).fetchone()[0]


def test_leaves_unparseable_lookalikes_alone():
    con = _con()
    con.execute("CREATE TABLE stg.venues AS SELECT 'America/New_York' AS timezone")
    assert promote_timestamp_columns(con) == []
    typ = con.execute(
        "SELECT data_type FROM information_schema.columns"
        " WHERE table_schema='stg' AND column_name='timezone'"
    ).fetchone()[0]
    assert typ == "VARCHAR"


def test_nulls_survive_and_rerun_is_idempotent():
    con = _con()
    con.execute(
        "CREATE TABLE stg.coaches AS SELECT * FROM (VALUES"
        " ('2020-01-05 00:00:00+00:00'), (NULL)) t(hireDate)"
    )
    assert len(promote_timestamp_columns(con)) == 1
    assert con.execute(
        "SELECT count(*) FILTER (WHERE hireDate IS NULL) FROM stg.coaches"
    ).fetchone()[0] == 1
    assert promote_timestamp_columns(con) == []


def test_partially_unparseable_column_is_left_untouched():
    con = _con()
    con.execute(
        "CREATE TABLE stg.games AS SELECT * FROM (VALUES"
        " ('2023-09-02 16:00:00+00:00'), ('TBD')) t(startDate)"
    )
    assert promote_timestamp_columns(con) == []
