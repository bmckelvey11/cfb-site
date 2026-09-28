"""Pace stats pair filter. In-memory warehouse fixture: no CFB_DATA_ROOT."""
import duckdb
import pandas as pd

from cfb_system_maker.duckdb_core import _build_fact_game_clock_quality
from scripts.pace_stats import load_pairs


def _play(game, drive, n, off, ptype, period, mm, ss, gained=3, dist=10):
    return {"gameId": game, "season": 2025, "week": 1, "driveId": f"{game}-{drive}",
            "playId": f"{game}{drive}{n:02d}", "wallclock": None,
            "playNumber": n, "offense": off, "defense": "Z", "playType": ptype,
            "period": period, "clock_minutes": mm, "clock_seconds": ss,
            "yardsGained": gained, "distance": dist, "offenseScore": 0, "defenseScore": 0}


def test_load_pairs_keeps_only_clock_running_rush_pairs_in_clean_fbs_games():
    plays = pd.DataFrame([
        _play(1, 1, 1, "A", "Rush", 1, 10, 0),               # kept: next snap 30 s later
        _play(1, 1, 2, "A", "Pass Reception", 1, 9, 30),      # not a rush: starts no pair
        _play(1, 1, 3, "A", "Rush", 1, 9, 0, gained=12),     # first down: clock stopped
        _play(1, 1, 4, "A", "Rush", 1, 8, 20),                # next is a timeout
        _play(1, 1, 5, "A", "Timeout", 1, 7, 50),
        _play(1, 1, 6, "A", "Rush", 1, 0, 10),                # next snap is in Q2
        _play(1, 1, 7, "A", "Rush", 2, 15, 0),                # last play of its drive
        _play(1, 2, 1, "B", "Pass Incompletion", 2, 14, 30),
        _play(2, 1, 1, "A", "Rush", 1, 12, 0),                # stale clock: every delta 0
        _play(2, 1, 2, "A", "Rush", 1, 12, 0),
        _play(2, 1, 3, "A", "Rush", 1, 12, 0),
        _play(3, 1, 1, "A", "Rush", 1, 12, 0),                # FCS opponent
        _play(3, 1, 2, "A", "Rush", 1, 11, 30),
    ])
    games = pd.DataFrame({"gameId": [1, 2, 3], "seasonType": "regular",
                          "homeClassification": "fbs",
                          "awayClassification": ["fbs", "fbs", "fcs"]})
    con = duckdb.connect()
    con.execute("create schema stg")
    con.execute("create schema core")
    con.register("plays_df", plays)
    con.register("games_df", games)
    con.execute("create table stg.plays as select * from plays_df")
    con.execute("create table stg.games as select * from games_df")
    _build_fact_game_clock_quality(con)

    p = load_pairs(con)

    assert p[["game_id", "secs_left", "dclk"]].values.tolist() == [[1, 600, 30]]
