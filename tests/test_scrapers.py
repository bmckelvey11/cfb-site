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

    def get_predicted_points_added_by_player_game(self, year=None, week=None, season_type=None,
                                                  team=None, position=None, player_id=None,
                                                  threshold=None, exclude_garbage_time=None):
        return [{"year": year, "week": week, "excludeGarbageTime": exclude_garbage_time}]


class _PlaysApi:
    def __init__(self, client):
        pass

    def get_plays(self, year=None, week=None, team=None, season_type=None, **rest):
        if season_type == "postseason":
            return [{"id": f"{year}-post-{week}", "year": year, "week": week,
                     "season_type": "postseason"}]
        if week > 2:
            return []
        return [{"id": f"{year}-{week}", "year": year, "week": week, "season_type": season_type}]


class _BoomApi:
    def __init__(self, client):
        pass

    def get_records(self, year=None, team=None, conference=None):
        raise RuntimeError("boom")


class _PlayoffsApi:
    def __init__(self, client):
        pass

    def get_cfp_playoff(self, year=None):
        if year < 2014:  # matches the live API: pre-CFP seasons raise, they don't return []
            raise ValueError(f"no playoff in {year}")
        return [{"season": year, "teamCount": 4}]


def _fake_cfbd():
    return SimpleNamespace(
        Configuration=_Config,
        ApiClient=_Client,
        ConferencesApi=_ConferencesApi,
        GamesApi=_GamesApi,
        MetricsApi=_MetricsApi,
        PlaysApi=_PlaysApi,
        PlayoffsApi=_PlayoffsApi,
    )


def _run(only, tmp_path, **kwargs):
    return scrape(
        kwargs.pop("seasons", [2022, 2023]),
        data_dir=tmp_path,
        token="test",
        cfbd_module=kwargs.pop("cfbd_module", _fake_cfbd()),
        only=set(only),
        delay=0.0,
        **kwargs,
    )


def test_registry_is_complete_and_unique():
    names = [e.name for e in ENDPOINTS]
    assert len(set(names)) == len(names)

    # 76 base entries, plus 9 `_ngt` variants that reuse a base endpoint's method with
    # `excludeGarbageTime` on. Counting them together would hide a real duplicate spec
    # path behind the variants.
    #
    # It was 78 and one per CFBD spec path. `draft_positions` and `draft_teams` are the
    # two paths deliberately not registered: GraphQL supersedes them under R6 and the
    # REST pulls were duplicates (docs/warehouse-drop-superseded-2026-09-10.md). If this
    # count rises to 78 again, check it is a new spec path and not those two coming back.
    base = [e for e in ENDPOINTS if not e.name.endswith("_ngt")]
    variants = [e for e in ENDPOINTS if e.name.endswith("_ngt")]
    assert len(base) == 76
    assert not {"draft_positions", "draft_teams"} & set(names)
    assert len(variants) == 9

    # Every variant shadows a registered base endpoint and differs only by the flag.
    by_method = {(e.api, e.method) for e in base}
    for variant in variants:
        assert (variant.api, variant.method) in by_method, variant.name
        assert variant.fixed == {"exclude_garbage_time": True}, variant.name


def test_season_skips_years_before_min_season(tmp_path):
    """CFP endpoints error (not empty) before 2014, and one error kills the whole endpoint."""
    reports = _run({"cfp_playoff"}, tmp_path, seasons=[2013, 2014])

    assert not (tmp_path / "raw" / "cfp_playoff_2013.json").exists()
    assert (tmp_path / "raw" / "cfp_playoff_2014.json").exists()
    assert reports[0].files == 1 and reports[0].skipped == 1
    assert reports[0].error is None


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


def test_season_week_keeps_the_two_season_types_in_separate_files(tmp_path):
    """Postseason weeks restart at 1, so the two types must never share a file.

    A single `season_type="both"` call would merge regular week 1 with postseason
    week 1 (live: game_team_stats 2024 wk1 gave regular=137, postseason=50, both=187).
    Each pass therefore asks for one type and postseason gets its own `_post_wk` name.
    """
    save_raw_json(tmp_path, "games", 2022, [
        {"id": 1, "week": 1, "seasonType": "regular"},
        {"id": 2, "week": 1, "seasonType": "postseason"},
    ])
    save_raw_json(tmp_path, "games", 2023, [{"id": 3, "week": 1, "seasonType": "postseason"}])

    _run({"plays"}, tmp_path, season_type="both")

    regular = json.loads((tmp_path / "raw" / "plays_2022_wk1.json").read_text())
    assert [r["season_type"] for r in regular] == ["regular"]

    post = json.loads((tmp_path / "raw" / "plays_2022_post_wk1.json").read_text())
    assert [r["season_type"] for r in post] == ["postseason"]
    assert {r["id"] for r in regular}.isdisjoint({r["id"] for r in post})


def test_season_week_postseason_weeks_come_from_the_games_seed(tmp_path):
    """2025 has postseason in weeks 1, 13 and 14 — week 1 cannot be assumed."""
    save_raw_json(tmp_path, "games", 2022, [
        {"id": 1, "week": 1, "seasonType": "postseason"},
        {"id": 2, "week": 13, "seasonType": "postseason"},
        {"id": 3, "week": 7, "seasonType": "regular"},  # must not become a postseason pass
    ])

    _run({"plays"}, tmp_path, seasons=[2022], season_type="postseason")

    raw = tmp_path / "raw"
    assert (raw / "plays_2022_post_wk1.json").exists()
    assert (raw / "plays_2022_post_wk13.json").exists()
    assert not (raw / "plays_2022_post_wk7.json").exists()
    assert not (raw / "plays_2022_wk1.json").exists()  # postseason only: no regular pass


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


def test_per_game_skips_permanently_failing_game(tmp_path):
    """One game that 500s after retries must not discard the whole season."""
    save_raw_json(tmp_path, "games", 2023, [{"id": 1}, {"id": 2}, {"id": 3}])

    module = _fake_cfbd()
    games_api = module.GamesApi(None)

    def flaky(id=None):
        if id == 2:
            raise RuntimeError("Internal Server Error (500)")
        return {"gameId": id, "teams": [{"team": "A"}]}

    games_api.get_advanced_box_score = flaky
    module.GamesApi = lambda client: games_api

    reports = _run({"advanced_box_score"}, tmp_path, include_per_game=True, cfbd_module=module)

    rows = json.loads((tmp_path / "raw" / "advanced_box_score_2023.json").read_text())
    assert [r["gameId"] for r in rows] == [1, 3]  # game 2 skipped, others kept
    assert reports[0].rows == 2
    assert reports[0].error is None  # a skipped game is not an endpoint failure


def test_per_game_id_param_alias(tmp_path):
    save_raw_json(tmp_path, "games", 2023, [{"id": 55}])
    _run({"win_probability"}, tmp_path, include_per_game=True)

    rows = json.loads((tmp_path / "raw" / "win_probability_2023.json").read_text())
    assert rows[0]["gameId"] == 55  # game_id alias resolved by signature filtering


def test_call_retries_network_errors(monkeypatch):
    """DNS/connection failures are transient — retry them like 5xx, not raise."""
    import urllib3.exceptions

    from cfb_system_maker import scrapers

    monkeypatch.setattr(scrapers.time, "sleep", lambda _s: None)  # no real backoff

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib3.exceptions.MaxRetryError(pool=None, url="/metrics/wp", reason=None)
        return [{"ok": True}]

    rows = scrapers._call(lambda: flaky(), {}, 0.0)
    assert rows == [{"ok": True}]
    assert calls["n"] == 3  # failed twice, succeeded on the third


def test_call_gives_up_on_persistent_network_error(monkeypatch):
    import urllib3.exceptions

    from cfb_system_maker import scrapers

    monkeypatch.setattr(scrapers.time, "sleep", lambda _s: None)

    def always_dead():
        raise urllib3.exceptions.NameResolutionError("api.collegefootballdata.com", None, None)

    with pytest.raises(urllib3.exceptions.HTTPError):
        scrapers._call(lambda: always_dead(), {}, 0.0)


def test_call_does_not_retry_client_errors(monkeypatch):
    """A 404 is not transient — raise immediately rather than burning backoff."""
    from cfb_system_maker import scrapers

    monkeypatch.setattr(scrapers.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def not_found():
        calls["n"] += 1
        raise RuntimeError("(404) Reason: Not Found")

    with pytest.raises(RuntimeError):
        scrapers._call(lambda: not_found(), {}, 0.0)
    assert calls["n"] == 1  # no retries


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


def test_season_week_applies_endpoint_fixed_kwargs(tmp_path):
    """`_ngt` variants are SEASON_WEEK too, and that path once dropped `fixed`.

    Without `| endpoint.fixed` the call goes out *without* `excludeGarbageTime` and the
    unfiltered rows land under the `_ngt` name — same row count, wrong content, and
    `resume` protects the bad file on every later run.
    """
    _run({"ppa_players_games_ngt"}, tmp_path, seasons=[2024], weeks=range(1, 2),
         season_type="regular")

    rows = json.loads((tmp_path / "raw" / "ppa_players_games_ngt_2024_wk1.json").read_text())
    assert rows == [{"year": 2024, "week": 1, "excludeGarbageTime": True}]
