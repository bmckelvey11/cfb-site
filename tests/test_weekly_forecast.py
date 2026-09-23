"""Weekly total forecasts. In-memory: no CFB_DATA_ROOT, no network."""
import itertools

import pandas as pd

from scripts.weekly_forecast import forecast_week, next_week

T0 = pd.Timestamp("2024-09-21T16:00:00Z")


def _games(extra=()):
    rows = []
    for i, (h, a) in enumerate(itertools.permutations("ABCD", 2)):
        pts_h, pts_a = 24 + 3 * "ABCD".index(a), 20 + 2 * "ABCD".index(h)
        rows.append({"game_id": i, "season": 2024, "week": 1 + i // 6, "kickoff": T0 - pd.Timedelta(days=30 - i),
                     "home": h, "away": a, "neutral": False, "home_reg": pts_h, "away_reg": pts_a,
                     "home_poss": 12, "away_poss": 12, "N": 12.0, "ot": 0.0, "total": pts_h + pts_a,
                     "gated": False})
    return pd.DataFrame(rows + list(extra))


def test_next_week_is_the_earliest_unplayed_fbs_game():
    fbs = {"seasonType": "regular", "homeClassification": "fbs", "awayClassification": "fbs"}
    payload = [{**fbs, "week": 3, "completed": True}, {**fbs, "week": 4, "completed": False},
               {**fbs, "week": 2, "completed": False, "awayClassification": "fcs"}]
    assert next_week(payload) == 4


def test_games_after_the_first_kickoff_cannot_move_the_forecast():
    sched = pd.DataFrame([{"game_id": 99, "kickoff": T0, "home": "A", "away": "B", "neutral": False,
                           "completed": False}])
    before, _, n_before = forecast_week(_games(), sched, 2024, None)
    late = {**_games().iloc[0].to_dict(), "game_id": 98, "kickoff": T0, "home_reg": 90, "total": 120}
    after, _, n_after = forecast_week(_games([late]), sched, 2024, None)
    assert n_before == n_after == 12
    pd.testing.assert_frame_equal(before, after)
    assert before.at[0, "min_games"] == 6
