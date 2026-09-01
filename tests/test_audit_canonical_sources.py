import duckdb
import pytest

from scripts.audit_canonical_sources import concept_metrics


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA stg")
    c.execute("CREATE TABLE stg.gql_game (id INTEGER, season INTEGER, venue VARCHAR)")
    c.execute("INSERT INTO stg.gql_game VALUES (1,2020,'A'),(2,2021,'B'),(3,2022,NULL)")
    c.execute("CREATE TABLE stg.games (id INTEGER, season INTEGER)")
    c.execute("INSERT INTO stg.games VALUES (1,2021),(2,2022)")
    return c


def test_concept_metrics_reports_season_span(con):
    m = concept_metrics(con, "gql_game", "games")
    assert m["gql_seasons"] == (2020, 2022)
    assert m["rest_seasons"] == (2021, 2022)


def test_concept_metrics_reports_row_and_column_counts(con):
    m = concept_metrics(con, "gql_game", "games")
    assert m["gql_rows"] == 3
    assert m["rest_rows"] == 2
    assert m["gql_cols"] == 3
    assert m["rest_cols"] == 2


def test_concept_metrics_handles_table_without_season(con):
    con.execute("CREATE TABLE stg.gql_hometown (id INTEGER)")
    con.execute("CREATE TABLE stg.hometowns (id INTEGER)")
    m = concept_metrics(con, "gql_hometown", "hometowns")
    assert m["gql_seasons"] is None
