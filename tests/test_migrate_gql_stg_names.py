import duckdb
import pytest

from scripts.migrate_gql_stg_names import migrate, plan_renames


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA stg")
    c.execute("CREATE SCHEMA meta")
    c.execute("CREATE TABLE stg.gameLines (id INTEGER)")
    c.execute("INSERT INTO stg.gameLines VALUES (1)")
    c.execute('CREATE TABLE stg."gameTeam__lineScores" (id INTEGER)')
    c.execute("CREATE TABLE stg.calendar_gql (id INTEGER)")
    c.execute("CREATE TABLE stg.calendar (id INTEGER)")
    c.execute("CREATE TABLE stg.games (id INTEGER)")
    c.execute(
        "CREATE TABLE meta.load_report "
        "(schema VARCHAR, name VARCHAR, files INTEGER, rows BIGINT, "
        " error VARCHAR, loaded_at TIMESTAMP)"
    )
    c.execute(
        "INSERT INTO meta.load_report VALUES "
        "('stg','gameLines',1,63293,NULL,NOW()), ('stg','games',1,54264,NULL,NOW())"
    )
    return c


def test_plan_renames_covers_parents_and_children(con):
    pairs = dict(plan_renames(con))
    assert pairs["gameLines"] == "gql_game_lines"
    assert pairs["gameTeam__lineScores"] == "gql_game_team__line_scores"


def test_plan_renames_maps_legacy_gql_suffix(con):
    # stg.calendar_gql is GraphQL calendar that lost order-dependent clash.
    pairs = dict(plan_renames(con))
    assert pairs["calendar_gql"] == "gql_calendar"


def test_plan_renames_leaves_rest_tables_alone(con):
    pairs = dict(plan_renames(con))
    assert "games" not in pairs
    assert "calendar" not in pairs


def test_migrate_renames_tables_and_preserves_rows(con):
    migrate(con, dry_run=False)
    assert con.execute("SELECT id FROM stg.gql_game_lines").fetchall() == [(1,)]
    names = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='stg'"
    ).fetchall()}
    assert "gameLines" not in names
    assert "games" in names


def test_migrate_repairs_load_report(con):
    migrate(con, dry_run=False)
    rows = dict(con.execute("SELECT name, rows FROM meta.load_report").fetchall())
    assert rows["gql_game_lines"] == 63293
    assert "gameLines" not in rows
    assert rows["games"] == 54264


def test_migrate_is_idempotent(con):
    migrate(con, dry_run=False)
    second = migrate(con, dry_run=False)
    assert second == []


def test_dry_run_changes_nothing(con):
    planned = migrate(con, dry_run=True)
    assert planned
    names = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='stg'"
    ).fetchall()}
    assert "gameLines" in names
