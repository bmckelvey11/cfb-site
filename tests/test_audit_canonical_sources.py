import duckdb

from cfb_system_maker.graphql_client import GQL_ENTITY_TO_STG
from scripts.audit_canonical_sources import PAIRS, concept_metrics


def test_pairs_graphql_member_has_no_gql_prefix():
    for concept, gql_name, rest_name in PAIRS:
        assert not gql_name.startswith("gql_"), f"{concept}: {gql_name} still gql_-prefixed"


def test_pairs_graphql_member_is_a_real_stg_destination():
    # PAIRS is hand-maintained, not derived from GQL_ENTITY_TO_STG. Without this, a
    # future mapping edit could silently make a row report MISSING instead of failing
    # a test.
    gql_stg_names = set(GQL_ENTITY_TO_STG.values())
    for concept, gql_name, rest_name in PAIRS:
        assert gql_name in gql_stg_names, f"{concept}: {gql_name} not in GQL_ENTITY_TO_STG.values()"


def test_concept_metrics_reads_graphql_side_from_its_suffixed_name():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    con.execute("CREATE TABLE stg.calendar AS SELECT 1 AS id, 2024 AS season")
    con.execute(
        "CREATE TABLE stg.calendar_gql AS"
        " SELECT 1 AS id, 2024 AS season UNION ALL SELECT 2, 2023"
    )
    metrics = concept_metrics(con, "calendar_gql", "calendar")
    assert metrics["gql_rows"] == 2
    assert metrics["rest_rows"] == 1
    assert metrics["gql_seasons"] == (2023, 2024)
