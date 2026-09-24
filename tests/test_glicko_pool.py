"""glicko_pool_eval.load_pool_games: drops and counts non-D1 and unplayed games. In-memory,
synthetic raw JSON, no CFB_DATA_ROOT."""
import json

from scripts.glicko_pool_eval import load_pool_games


def _game(gid, hc="fbs", ac="fcs", hp=30, ap=10, completed=True):
    return {"id": gid, "week": 1, "seasonType": "regular", "startDate": "2013-09-01T00:00:00Z",
            "homeTeam": "H", "awayTeam": "A", "homeClassification": hc, "awayClassification": ac,
            "homeConference": "X" if hc in ("fbs", "fcs") else None,
            "awayConference": "Y" if ac in ("fbs", "fcs") else None,
            "neutralSite": False, "completed": completed,
            "homePoints": hp if completed else None, "awayPoints": ap if completed else None}


def test_drops_non_d1_and_unplayed_games_and_counts_them(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    games = [
        _game(1, "fbs", "fbs"),                 # kept: D-I
        _game(2, "fbs", "fcs"),                 # kept: D-I
        _game(3, "fcs", "ii"),                  # dropped: non-D1
        _game(4, "iii", "iii"),                 # dropped: non-D1
        _game(5, "fbs", "fbs", completed=False),  # dropped: unplayed
    ]
    (raw / "games_2013.json").write_text(json.dumps(games), encoding="utf-8")

    g, drops = load_pool_games(tmp_path, 2013, [])

    assert sorted(g["game_id"]) == [1, 2]
    assert drops["non_d1_by_season"][2013] == 2
    assert drops["unplayed_by_season"][2013] == 1
    assert set(g["home_div"]) <= {"fbs", "fcs"} and set(g["away_div"]) <= {"fbs", "fcs"}
