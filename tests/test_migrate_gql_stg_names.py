import duckdb

from scripts.migrate_gql_stg_names import migrate, plan_moves


def _seeded_con():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    con.execute("CREATE SCHEMA meta")
    con.execute("CREATE TABLE stg.gql_game AS SELECT 1 AS gameId, 2024 AS season")
    con.execute("CREATE TABLE stg.gql_game__away_line_scores AS SELECT 1 AS gameId, 10 AS score")
    con.execute("CREATE TABLE stg.games AS SELECT 1 AS gameId, 2024 AS season")
    con.execute(
        """
        CREATE TABLE meta.load_report (
          schema VARCHAR, name VARCHAR, files INTEGER, rows BIGINT,
          error VARCHAR, loaded_at TIMESTAMP
        )
        """
    )
    con.execute(
        "INSERT INTO meta.load_report VALUES"
        " ('stg', 'gql_game', 1, 1, NULL, now()),"
        " ('stg', 'gql_game__away_line_scores', 1, 1, NULL, now()),"
        " ('stg', 'games', 1, 1, NULL, now())"
    )
    return con


def test_plan_moves_covers_parent_and_child_tables_not_rest():
    con = _seeded_con()
    moves = plan_moves(con)
    by_src = {(s, n): (ds, dn) for s, n, ds, dn in moves}
    assert by_src[("stg", "gql_game")] == ("stg_gql", "game")
    assert by_src[("stg", "gql_game__away_line_scores")] == ("stg_gql", "game__away_line_scores")
    assert ("stg", "games") not in by_src


def test_migrate_moves_tables_and_updates_meta():
    con = _seeded_con()
    migrate(con)
    assert con.execute(
        "SELECT COUNT(*) FROM information_schema.tables"
        " WHERE table_schema = 'stg' AND table_name = 'gql_game'"
    ).fetchone()[0] == 0
    assert con.execute("SELECT gameId FROM stg_gql.game").fetchone()[0] == 1
    assert con.execute("SELECT gameId FROM stg.games").fetchone()[0] == 1
    row = con.execute(
        "SELECT schema, name FROM meta.load_report WHERE name = 'game' AND schema = 'stg_gql'"
    ).fetchone()
    assert row == ("stg_gql", "game")


def test_migrate_is_idempotent_and_resumable():
    con = _seeded_con()
    migrate(con)
    con.execute("DROP TABLE stg_gql.game__away_line_scores")  # simulate destination lost after a prior run
    second = migrate(con)  # must not error re-processing already-moved tables
    assert all(report.error is None for report in second)
    assert con.execute("SELECT gameId FROM stg_gql.game").fetchone()[0] == 1
