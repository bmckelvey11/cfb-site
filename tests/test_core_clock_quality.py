"""core.fact_game_clock_quality on an in-memory stg.plays fixture: no CFB_DATA_ROOT."""
import duckdb
import pandas as pd
import pytest

from cfb_system_maker.duckdb_core import _build_fact_game_clock_quality


def _play(game, n, ptype, period, mm, ss, wall, drive=1):
    return {"gameId": game, "season": 2025, "week": 1, "driveId": f"{game}-{drive}",
            "playId": f"{game}{n:03d}", "playNumber": n, "offense": "A",
            "playType": ptype, "period": period, "clock_minutes": mm,
            "clock_seconds": ss, "wallclock": wall}


def _t(sec):
    return f"2025-08-30T20:{sec // 60:02d}:{sec % 60:02d}.000Z"


@pytest.fixture
def quality():
    plays = pd.DataFrame([
        # game 1: live clock and wallclock; its OT snaps (no game clock) are ignored
        _play(1, 1, "Rush", 1, 10, 0, _t(0)),
        _play(1, 2, "Rush", 1, 9, 30, _t(35)),
        _play(1, 3, "Pass Incompletion", 1, 9, 0, _t(70)),
        _play(1, 4, "Rush", 5, 0, 0, _t(200), drive=2),
        _play(1, 5, "Rush", 5, 0, 0, _t(230), drive=2),
        # game 2: clock stuck, wallclock missing
        _play(2, 1, "Rush", 1, 12, 0, None),
        _play(2, 2, "Rush", 1, 12, 0, None),
        _play(2, 3, "Punt", 1, 12, 0, None),  # not a scrimmage snap: no pair
    ])
    con = duckdb.connect()
    con.execute("create schema stg")
    con.execute("create schema core")
    con.register("plays_df", plays)
    con.execute("create table stg.plays as select * from plays_df")
    assert _build_fact_game_clock_quality(con)
    return con.execute(
        "select game_id, rush_pairs, clock_stale_share, wallclock_stale_share,"
        " clock_ok, wallclock_ok from core.fact_game_clock_quality order by 1"
    ).fetchall()


def test_a_live_clock_passes_and_a_stuck_one_fails(quality):
    assert quality == [(1, 2, 0.0, 0.0, True, True), (2, 1, 1.0, 1.0, False, False)]


def test_missing_stg_plays_skips_the_table():
    con = duckdb.connect()
    con.execute("create schema stg")
    assert _build_fact_game_clock_quality(con) is False
