from scripts.promote_to_motherduck import DEFAULT_SCHEMAS


def test_default_schemas_includes_stg_gql():
    assert "stg_gql" in DEFAULT_SCHEMAS
    assert DEFAULT_SCHEMAS == ["raw", "stg", "stg_gql", "core", "meta"]
