import duckdb

from cfb_system_maker.duckdb_core import _build_core_views


def _con():
    con = duckdb.connect()
    con.execute("CREATE SCHEMA core")
    con.execute("CREATE TABLE core.dim_venue (venue_id INT, name VARCHAR, city VARCHAR,"
                " state VARCHAR, dome BOOL, grass BOOL, capacity INT, elevation DOUBLE)")
    con.execute("CREATE TABLE core.dim_week (season INT, week INT, season_type VARCHAR,"
                " start_date DATE, end_date DATE)")
    con.execute("CREATE TABLE core.fact_game AS SELECT * FROM (VALUES"
                " (1, 2025, 1, 'regular', NULL::INT, 'consensus', 'consensus'),"
                " (2, 2025, 1, 'regular', NULL::INT, NULL, NULL),"
                " (3, 2025, 1, 'regular', NULL::INT, 'consensus', 'consensus'))"
                " t(game_id, season, week, season_type, venue_id,"
                "   selected_spread_provider_key, selected_total_provider_key)")
    con.execute("CREATE TABLE core.fact_game_line (game_id INT, provider_key VARCHAR,"
                " spread_open DOUBLE, spread_close DOUBLE, total_open DOUBLE, total_close DOUBLE)")
    con.execute("INSERT INTO core.fact_game_line VALUES"
                " (1, 'consensus', -10.0, -10.0, 50.0, 50.0),"
                " (1, 'bovada',    -3.0,  -3.0,  44.0, NULL),"
                " (1, 'draftkings', -3.5, -3.0,  45.0, 46.0),"
                " (3, 'consensus', -7.0, -6.5, 55.0, 54.0),"
                " (3, 'bovada',    -6.0, NULL, NULL, NULL)")
    _build_core_views(con)
    return con


def test_book_median_excludes_consensus_and_counts_each_column():
    row = _con().execute(
        "SELECT median_spread_open, n_books_spread_open, median_total_close,"
        " n_books_total_close FROM core.v_game_book_median WHERE game_id = 1"
    ).fetchone()
    # Even count interpolates; consensus's -10 / 50 never enter.
    assert row == (-3.25, 2, 46.0, 1)


def test_book_median_falls_back_to_consensus_per_column():
    row = _con().execute(
        "SELECT median_spread_open, n_books_spread_open, median_spread_close,"
        " n_books_spread_close FROM core.v_game_book_median WHERE game_id = 3"
    ).fetchone()
    # A book posted the open, so consensus stays out; no book posted the close.
    assert row == (-6.0, 1, -6.5, 0)


def test_book_median_keeps_games_without_lines():
    row = _con().execute(
        "SELECT median_spread_close, n_books_spread_close"
        " FROM core.v_game_book_median WHERE game_id = 2"
    ).fetchone()
    assert row == (None, None)
