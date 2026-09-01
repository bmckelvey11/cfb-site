import duckdb

from scripts.audit_canonical_sources import PAIRS, concept_metrics


def test_pairs_graphql_member_has_no_gql_prefix():
    for concept, gql_name, rest_name in PAIRS:
        assert not gql_name.startswith("gql_"), f"{concept}: {gql_name} still gql_-prefixed"


def test_concept_metrics_reads_graphql_side_from_stg_gql():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    con.execute("CREATE SCHEMA stg_gql")
    con.execute("CREATE TABLE stg.calendar AS SELECT 1 AS id, 2024 AS season")
    con.execute(
        "CREATE TABLE stg_gql.calendar AS"
        " SELECT 1 AS id, 2024 AS season UNION ALL SELECT 2, 2023"
    )
    metrics = concept_metrics(con, "calendar", "calendar")
    assert metrics["gql_rows"] == 2
    assert metrics["rest_rows"] == 1
    assert metrics["gql_seasons"] == (2023, 2024)
