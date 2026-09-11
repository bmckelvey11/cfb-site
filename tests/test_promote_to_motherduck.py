from scripts.promote_to_motherduck import DEFAULT_SCHEMAS


def test_default_schemas_has_no_second_staging_schema():
    """`stg_gql` was collapsed into `stg` (ADR-0003). Promoting a schema that no
    longer exists is silent -- MotherDuck would just keep the last mirror of it."""
    assert "stg_gql" not in DEFAULT_SCHEMAS
    assert DEFAULT_SCHEMAS == ["raw", "stg", "core", "meta"]
