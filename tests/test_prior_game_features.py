import copy
import json
import random

from cfb_system_maker.enrich import enrich_games, load_features_from, _load_prior_coach_style
from cfb_system_maker.features import FEATURE_BY_KEY
from cfb_system_maker.models import GameRecord
from cfb_system_maker.prior_game_stats import build_prior_game_stats


def game(gid, week=2, season=2023):
    return GameRecord(gid, season, week, "Alpha", "Beta", None, None, 21, 14, "consensus", -3.5, None)


def raw_game(gid, start, **extra):
    return {"id": gid, "season": 2023, "startDate": start, "homeTeam": "Alpha", "awayTeam": "Beta", "homePoints": 21, "awayPoints": 14, "completed": True, **extra}


def test_prior_averages_ignore_current_future_and_input_order():
    # Game 1 need not be in the processed betting dataset; raw schedule is enough.
    raw = {1: raw_game(1, "2023-09-01T17:00:00Z"), 2: raw_game(2, "2023-09-08T17:00:00Z"), 3: raw_game(3, "2023-09-15T17:00:00Z")}
    ngt = {(i, "Alpha"): {"defense": {"ppa": i / 10, "explosiveness": i}} for i in raw}
    havoc = {(i, "Alpha"): {"offense": {"havocRate": i / 10}} for i in raw}
    result = build_prior_game_stats([game(2)], raw, havoc, ngt)
    assert result[(2, "Alpha")]["defense_ppa"] == 0.1
    assert result[(2, "Alpha")]["havoc_offense_rate"] == 0.1
    assert result[(2, "Beta")]["defense_ppa"] is None
    changed = copy.deepcopy(ngt)
    for i in (2, 3):
        changed[(i, "Alpha")]["defense"]["ppa"] = 9999
    assert build_prior_game_stats([game(2)], dict(reversed(list(raw.items()))), havoc, changed) == result
    assert build_prior_game_stats([game(3)], raw, havoc, ngt)[(3, "Alpha")]["defense_ppa"] == 0.15


def test_unknown_dates_incomplete_same_day_other_season_and_nan_excluded():
    raw = {1: raw_game(1, "2023-09-08T16:00:00Z"), 2: raw_game(2, "2023-09-08T17:00:00Z"),
           3: raw_game(3, "2023-09-01T17:00:00Z", completed=False),
           4: raw_game(4, "2023-08-01T17:00:00Z", season=2022),
           5: raw_game(5, "unknown"), 6: raw_game(6, "2023-09-01T17:00:00Z")}
    ngt = {(i, "Alpha"): {"defense": {"ppa": float("nan") if i == 6 else 5}} for i in raw}
    assert build_prior_game_stats([game(2)], raw, {}, ngt)[(2, "Alpha")]["defense_ppa"] is None
    assert build_prior_game_stats([game(5)], raw, {}, ngt)[(5, "Alpha")]["defense_ppa"] is None


def test_pregame_probability_uses_forecast_not_outcome(tmp_path):
    (tmp_path / "raw").mkdir()
    path = tmp_path / "raw" / "pregame_win_prob_2023.json"
    path.write_text(json.dumps([{"gameId": 2, "homeWinProbability": 0.7}]))
    row = enrich_games(tmp_path, [game(2)])["2"]
    assert row["home_pregame_win_prob"] == 0.7
    assert abs(row["away_pregame_win_prob"] - 0.3) < 1e-12
    path.write_text(json.dumps([{"gameId": 2, "homeWinProbability": 1.7}]))
    assert enrich_games(tmp_path, [game(2)])["2"]["home_pregame_win_prob"] is None
    assert "attendance" not in FEATURE_BY_KEY
    assert not any(f.group == "result_lookahead" for f in FEATURE_BY_KEY.values())


def test_stale_sidecar_cannot_reintroduce_postgame_values(tmp_path):
    path = tmp_path / "features.json"
    path.write_text(json.dumps({"_meta": {"registry_version": "old"}, "games": {"1": {"home_defense_ppa": 99, "home_pregame_win_prob": 1, "attendance": 50000, "neutralSite": True}}}))
    assert load_features_from(path)[1] == {"neutralSite": True}


def test_coach_loader_rejects_future_training(tmp_path):
    (tmp_path / "processed").mkdir()
    path = tmp_path / "processed" / "pregame_coach_styles.json"
    payload = {"method": "expanding-prior-seasons-v1", "seasons": {"2023": {"training_seasons": [2023], "coach_assignment_season": 2022, "teams": {"Alpha": "option_ground"}}}}
    path.write_text(json.dumps(payload))
    assert _load_prior_coach_style(tmp_path) == {}
    payload["seasons"]["2023"]["training_seasons"] = [2020, 2021, 2022]
    path.write_text(json.dumps(payload))
    assert _load_prior_coach_style(tmp_path) == {("Alpha", 2023): "option_ground"}


def test_coach_refit_unchanged_when_future_seasons_change(tmp_path):
    from scripts.build_coach_style_clusters import pregame_snapshot
    rng = random.Random(71)
    for year in range(2016, 2021):
        stats, coaches = [], []
        for i in range(12):
            offense = {"plays": 800 + rng.random() * 100, "explosiveness": rng.random(), "successRate": rng.random(), "lineYards": rng.random(), "pointsPerOpportunity": rng.random(), "havoc": {"total": rng.random()}, "passingPlays": {"rate": rng.random()}, "passingDowns": {"rate": rng.random()}}
            defense = {"havoc": {"total": rng.random()}, "successRate": rng.random(), "explosiveness": rng.random(), "stuffRate": rng.random(), "lineYards": rng.random()}
            stats.append({"team": f"Team{i}", "offense": offense, "defense": defense})
            coaches.append({"firstName": "Coach", "lastName": str(i), "seasons": [{"year": year, "school": f"Team{i}", "games": 12, "spOverall": rng.random() * 30}]})
        (tmp_path / f"advanced_season_stats_{year}.json").write_text(json.dumps(stats))
        (tmp_path / f"coaches_{year}.json").write_text(json.dumps(coaches))
    before = pregame_snapshot(tmp_path, 2019)
    assert len(before["teams"]) == 12
    assert before["training_seasons"] == [2016, 2017, 2018]
    for year in (2019, 2020):
        (tmp_path / f"advanced_season_stats_{year}.json").write_text("[]")
        (tmp_path / f"coaches_{year}.json").write_text("[]")
    assert pregame_snapshot(tmp_path, 2019) == before
