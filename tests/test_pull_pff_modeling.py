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
        {"id": 1, "season": 2025, "start": "2025-08-30T19:30:00Z"}]}))
    (tmp_path / "team_summary_2025_103.json").write_text(json.dumps({"team_summary": [
        {"game_id": 1, "week": 1, "franchise_id": 103, "opponent_franchise_id": 167, "home": False,
         "points_scored": 17, "points_allowed": 31, "grades_overall": 66.7, "lock_status": "processed"}]}))
    (tmp_path / "team_summary_2025_167.json").write_text(json.dumps({"team_summary": [
        {"game_id": 1, "week": 1, "franchise_id": 167, "opponent_franchise_id": 103, "home": True,
         "points_scored": 31, "points_allowed": 17, "grades_overall": 80.1, "lock_status": "processed"}]}))
    rows = {r["franchise_id"]: r for r in flatten_team_games(tmp_path, [2025])}
    assert rows[103]["opp_grades_overall"] == 80.1 and rows[103]["home"] == 0
    assert rows[167]["opp_grades_overall"] == 66.7 and rows[167]["home"] == 1
    assert rows[103]["season"] == 2025 and rows[103]["start"] == "2025-08-30T19:30:00Z"
