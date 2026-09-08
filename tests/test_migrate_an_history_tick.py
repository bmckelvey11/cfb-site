import duckdb

from cfb_system_maker.duckdb_load import _AN_TICK_COLUMNS
from scripts.actionnetwork_flatten import COLUMNS as FLATTEN_COLUMNS
from scripts.migrate_an_history_tick import live_types, plan


def _sniffed_con():
    """The table as `read_csv_auto` used to leave it: ids sniffed as BIGINT."""
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    con.execute(
        """
        CREATE TABLE stg.an_history_tick AS SELECT
          500::BIGINT AS event_id, 15::BIGINT AS book_id, 'event' AS period,
          'spread' AS market_type, 'home' AS side, 256::BIGINT AS team_id,
          164::BIGINT AS market_id, 284::BIGINT AS outcome_id,
          false AS is_alt_market, false AS is_live,
          now() AS updated_at, -6.5::DOUBLE AS line, -110::BIGINT AS odds,
          'opener' AS line_status, 'history_event_500.json' AS _source_file
        """
    )
    return con


def test_plan_names_only_the_ids_that_drifted():
    """book_id/market_id/outcome_id are the three the sniffer got wrong; the
    rest of the table already matches and must not be rewritten."""
    con = _sniffed_con()
    assert plan(live_types(con)) == [
        ("book_id", "BIGINT", "INTEGER"),
        ("market_id", "BIGINT", "VARCHAR"),
        ("outcome_id", "BIGINT", "VARCHAR"),
    ]


def test_applying_the_plan_is_idempotent_and_keeps_the_values():
    con = _sniffed_con()
    for name, _, want in plan(live_types(con)):
        con.execute(f'ALTER TABLE stg.an_history_tick ALTER "{name}" TYPE {want}')
    assert plan(live_types(con)) == []
    # The ids survive as their string selves -- what `_AN_OFFERING_COLS` extracts
    # for stg.an_history, so the two join without a cast on either side.
    assert con.execute(
        "SELECT market_id, outcome_id, book_id FROM stg.an_history_tick"
    ).fetchone() == ("164", "284", 15)


def test_flatten_column_order_matches_the_pinned_schema():
    """`read_csv(columns=...)` maps positionally: a reordered CSV would land
    every value in the wrong column. The two lists are one contract."""
    assert FLATTEN_COLUMNS == list(_AN_TICK_COLUMNS)
