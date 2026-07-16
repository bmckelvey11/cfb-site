import json
from types import SimpleNamespace

import pytest

from cfb_system_maker.scrapers import ENDPOINTS, scrape
from cfb_system_maker.storage import save_raw_json


class _Config:
    def __init__(self, access_token=None):
        self.access_token = access_token


class _Client:
    def __init__(self, configuration):
        self.configuration = configuration

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _ConferencesApi:
    def __init__(self, client):
        pass

    def get_conferences(self):
        return [{"id": 1, "name": "SEC"}, {"id": 2, "name": "Big Ten"}]


class _GamesApi:
    def __init__(self, client):
        self.calls = []

    def get_games(self, year=None, week=None, season_type=None, classification=None,
                  team=None, home=None, away=None, conference=None, id=None):
        return [{"id": 400 + year, "season": year, "week": 1, "season_type": season_type}]

    def get_advanced_box_score(self, id=None):
        return {"gameId": id, "teams": [{"team": "A"}]}


class _MetricsApi:
    def __init__(self, client):
        pass

    def get_predicted_points(self, down=None, distance=None):
        return [{"down": down, "distance": distance, "predictedPoints": 1.0}]

    def get_win_probability(self, game_id=None):
        return [{"gameId": game_id, "homeWinProbability": 0.5}]


class _PlaysApi:
    def __init__(self, client):
        pass

    def get_plays(self, year=None, week=None, team=None, season_type=None, **rest):
        if week > 2:
            return []
        return [{"id": f"{year}-{week}", "year": year, "week": week}]


class _BoomApi:
    def __init__(self, client):
        pass

    def get_records(self, year=None, team=None, conference=None):
        raise RuntimeError("boom")


def _fake_cfbd():
    return SimpleNamespace(
        Configuration=_Config,
        ApiClient=_Client,
        ConferencesApi=_ConferencesApi,
        GamesApi=_GamesApi,
        MetricsApi=_MetricsApi,
        PlaysApi=_PlaysApi,
    )


def _run(only, tmp_path, **kwargs):
    return scrape(
        [2022, 2023],
        data_dir=tmp_path,
        token="test",
        cfbd_module=kwargs.pop("cfbd_module", _fake_cfbd()),
        only=set(only),
        delay=0.0,
        **kwargs,
    )


def test_registry_is_complete_and_unique():
    names = [e.name for e in ENDPOINTS]
    assert len(names) == 61
    assert len(set(names)) == 61


def test_once_writes_single_file(tmp_path):
    reports = _run({"conferences"}, tmp_path)

    assert (tmp_path / "raw" / "conferences.json").exists()
    assert [r.name for r in reports] == ["conferences"]
    assert reports[0].rows == 2 and reports[0].files == 1


def test_season_loops_each_season_and_filters_kwargs(tmp_path):
    reports = _run({"games"}, tmp_path, season_type="postseason")

    g2022 = json.loads((tmp_path / "raw" / "games_2022.json").read_text())
    assert (tmp_path / "raw" / "games_2023.json").exists()
    assert g2022[0]["season_type"] == "postseason"  # season_type passed through
    assert reports[0].files == 2


def test_season_week_skips_empty_weeks(tmp_path):
    reports = _run({"plays"}, tmp_path)

    assert (tmp_path / "raw" / "plays_2022_wk1.json").exists()
    assert (tmp_path / "raw" / "plays_2022_wk2.json").exists()
    assert not (tmp_path / "raw" / "plays_2022_wk3.json").exists()  # empty -> not written
    assert reports[0].files == 4  # 2 seasons x 2 non-empty weeks


def test_grid_writes_down_distance_matrix(tmp_path):
    reports = _run({"predicted_points"}, tmp_path)

    rows = json.loads((tmp_path / "raw" / "predicted_points.json").read_text())
    assert len(rows) == 4 * 30
    assert reports[0].rows == 120


def test_per_game_is_opt_in(tmp_path):
    save_raw_json(tmp_path, "games", 2023, [{"id": 999}])

    skipped = _run({"advanced_box_score"}, tmp_path)
    assert skipped == []  # not run without the flag

    reports = _run({"advanced_box_score"}, tmp_path, include_per_game=True)
    rows = json.loads((tmp_path / "raw" / "advanced_box_score_2023.json").read_text())
    assert rows[0]["gameId"] == 999
    assert reports[0].rows == 1


def test_per_game_id_param_alias(tmp_path):
    save_raw_json(tmp_path, "games", 2023, [{"id": 55}])
    _run({"win_probability"}, tmp_path, include_per_game=True)

    rows = json.loads((tmp_path / "raw" / "win_probability_2023.json").read_text())
    assert rows[0]["gameId"] == 55  # game_id alias resolved by signature filtering


def test_resume_skips_existing_files(tmp_path):
    first = _run({"games"}, tmp_path)
    assert first[0].files == 2 and first[0].skipped == 0

    # second run: both season files exist -> all skipped, no writes
    second = _run({"games"}, tmp_path)
    assert second[0].files == 0
    assert second[0].skipped == 2

    # force re-scrapes
    forced = _run({"games"}, tmp_path, resume=False)
    assert forced[0].files == 2 and forced[0].skipped == 0


def test_on_demand_endpoints_are_skipped(tmp_path):
    assert _run({"scoreboard"}, tmp_path) == []


def test_endpoint_error_is_captured_not_raised(tmp_path):
    module = _fake_cfbd()
    module.GamesApi = _BoomApi
    reports = scrape(
        [2023], data_dir=tmp_path, token="test", cfbd_module=module, only={"records"}, delay=0.0
    )

    assert reports[0].error is not None
    assert "boom" in reports[0].error
    assert reports[0].files == 0
