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


def test_migrate_reports_error_when_source_and_destination_both_present():
    # This is NOT the ordinary resumed-run case (plan_moves only lists a table when its
    # source is still in `stg`, so a real resumed run never sees a destination that
    # already exists -- the source was already dropped when it moved). Seeding both here
    # simulates something going wrong, e.g. a rebuild regenerating `stg.gql_game` while
    # an earlier partial migration already created `stg_gql.game` from an older copy.
    con = _seeded_con()
    con.execute("CREATE SCHEMA stg_gql")
    con.execute("CREATE TABLE stg_gql.game AS SELECT 999 AS gameId, 2020 AS season")

    reports = migrate(con)

    game_report = next(r for r in reports if r.src_name == "gql_game")
    assert game_report.error is not None
    # Source must be left untouched, not silently dropped or overwritten.
    assert con.execute(
        "SELECT gameId FROM stg.gql_game"
    ).fetchone()[0] == 1
    # Destination must also be left untouched (not overwritten by the stranded source).
    assert con.execute(
        "SELECT gameId FROM stg_gql.game"
    ).fetchone()[0] == 999


def test_migrate_resumes_child_after_parent_only_partial_run():
    con = _seeded_con()
    # Simulate a prior run that crashed between the parent's move and its child's:
    # the parent already sits at its destination and is gone from `stg`, but the
    # child is still un-migrated in `stg`.
    con.execute("CREATE SCHEMA stg_gql")
    con.execute("CREATE TABLE stg_gql.game AS SELECT * FROM stg.gql_game")
    con.execute("DROP TABLE stg.gql_game")

    reports = migrate(con)

    assert all(report.error is None for report in reports)
    assert con.execute(
        "SELECT COUNT(*) FROM information_schema.tables"
        " WHERE table_schema = 'stg' AND table_name = 'gql_game__away_line_scores'"
    ).fetchone()[0] == 0
    assert con.execute(
        "SELECT gameId FROM stg_gql.game__away_line_scores"
    ).fetchone()[0] == 1
