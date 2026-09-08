import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pull_pff_modeling import fbs_franchises, flatten_team_games, ncaa_weeks, parse_seasons  # noqa: E402


def test_parse_seasons_ranges_and_lists():
    assert parse_seasons("2025") == [2025]
    assert parse_seasons("2019,2021-2023") == [2019, 2021, 2022, 2023]


def test_ncaa_weeks_drops_all_star_weeks():
    leagues = {"leagues": [{"slug": "ncaa", "weeks": [
        {"id": 0, "all_star": False}, {"id": 17, "all_star": False}, {"id": 30, "all_star": True}]}]}
    assert ncaa_weeks(leagues) == [0, 17]


def test_fbs_franchises_reads_group_11():
    directory = {"rows": [{"franchiseId": 5, "groupIds": "11;24"}, {"franchiseId": 9, "groupIds": "12;209"}]}
    assert fbs_franchises(directory) == [5]


def test_flatten_pairs_opponent_grades(tmp_path):
    (tmp_path / "games_2025_wk1.json").write_text(json.dumps({"games": [
        {"id": 1, "season": 2025, "week": 1, "start": "2025-08-30T19:30:00Z", "lock_status": "processed",
         "home_franchise_id": 167, "away_franchise_id": 103, "score": {"home_team": 31, "away_team": 17}}]}))
    (tmp_path / "team_overview_2025_wk1.json").write_text(json.dumps({"team_overview": [
        {"franchise_id": 103, "grades_overall": 66.7}, {"franchise_id": 167, "grades_overall": 80.1},
        {"franchise_id": 999, "grades_overall": 50.0}]}))  # a team with no game this week
    rows = {r["franchise_id"]: r for r in flatten_team_games(tmp_path, [2025], fbs={103})}
    assert set(rows) == {103, 167}
    assert rows[103]["opp_grades_overall"] == 80.1 and rows[103]["home"] == 0 and rows[103]["points_scored"] == 17
    assert rows[167]["opp_grades_overall"] == 66.7 and rows[167]["home"] == 1 and rows[167]["points_allowed"] == 17
    assert rows[103]["fbs"] == 1 and rows[103]["opp_fbs"] == 0 and rows[103]["graded"] == 1
