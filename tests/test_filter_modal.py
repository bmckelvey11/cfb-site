"""Wave 0/1 contracts for filter modal: descriptions, summary, API, filter-detail, Season shell."""

from cfb_system_maker.backtest import grade_bet, run_backtest_summary
from cfb_system_maker.enrich import save_features
from cfb_system_maker.features import FEATURE_REGISTRY
from cfb_system_maker.models import FeatureFilter, GameRecord, SystemFilter
from cfb_system_maker.normalize import normalize_games
from cfb_system_maker.sample_data import SAMPLE_GAMES_2023, SAMPLE_LINES_2023
from cfb_system_maker.storage import save_processed_games
from cfb_system_maker.web import (
    aggregate_filter_value_rows,
    create_app,
    remove_candidate_filters,
)

_SUMMARY_KEYS = {"wins", "losses", "pushes", "hit_rate", "profit", "money_won", "roi"}


def _game(
    game_id: int = 1,
    *,
    season: int = 2023,
    week: int = 1,
    home_points: int = 28,
    away_points: int = 21,
    spread: float = -6.5,
    total: float = 49.5,
) -> GameRecord:
    return GameRecord(
        game_id,
        season,
        week,
        "Alpha",
        "Beta",
        "ACC",
        "SEC",
        home_points,
        away_points,
        "consensus",
        spread,
        total,
    )


def test_registry_descriptions_nonempty_and_lookahead_wording():
    for feature in FEATURE_REGISTRY:
        assert isinstance(feature.description, str)
        assert feature.description.strip()
        if feature.group == "result_lookahead":
            lowered = feature.description.lower()
            assert "analysis-only" in lowered or "lookahead" in lowered


def test_run_backtest_summary_returns_chip_keys_only():
    games = [_game()]
    summary = run_backtest_summary(games, SystemFilter(side="home"))
    assert set(summary) == _SUMMARY_KEYS
    assert summary["wins"] == 1
    assert summary["losses"] == 0
    assert summary["pushes"] == 0
    assert summary["money_won"] == summary["profit"] * 100
    # Lightweight: no heavy analysis fields attached
    assert "bet_details" not in summary
    assert "stats" not in summary
    assert "grade" not in summary
    assert "season_breakdown" not in summary


def test_run_backtest_summary_fade_flips_graded_side():
    # Home covers -6.5 (margin +0.5). Fade home → grade away → loss.
    games = [_game(home_points=28, away_points=21, spread=-6.5)]
    plain = run_backtest_summary(games, SystemFilter(side="home", fade=False))
    faded = run_backtest_summary(games, SystemFilter(side="home", fade=True))
    assert plain["wins"] == 1
    assert faded["losses"] == 1
    detail = grade_bet(games[0], SystemFilter(side="home", fade=True))
    assert detail.result == "loss"


def test_run_backtest_summary_zero_matched_bets():
    games = [_game(season=2023)]
    summary = run_backtest_summary(games, SystemFilter(side="home", seasons={2099}))
    assert summary == {
        "wins": 0,
        "losses": 0,
        "pushes": 0,
        "hit_rate": 0.0,
        "profit": 0.0,
        "money_won": 0.0,
        "roi": 0.0,
    }


def test_api_backtest_returns_json_chips(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    response = app.test_client().get("/api/backtest?side=home")
    assert response.status_code == 200
    assert response.is_json
    payload = response.get_json()
    assert set(payload) == _SUMMARY_KEYS
    assert isinstance(payload["wins"], int)
    assert isinstance(payload["roi"], (int, float))


def test_api_backtest_unknown_feature_key_is_400(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    response = app.test_client().get(
        "/api/backtest?side=home&ff_enable=not_a_real_feature&ff_key=not_a_real_feature"
        "&ff_op=eq&ff_value=true&ff_perspective=single"
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload
    assert "message" in payload


def test_api_backtest_missing_data_is_503(tmp_path):
    app = create_app(data_dir=tmp_path)
    response = app.test_client().get("/api/backtest?side=home")
    assert response.status_code == 503


def test_index_has_season_dialog_launcher_markup(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    html = app.test_client().get("/").get_data(as_text=True)
    assert 'id="filter-modal"' in html
    assert 'data-candidate-id="core:season"' in html
    assert "Save Filter" in html
    assert "Cancel" in html
    assert "About Filter" in html
    assert 'aria-labelledby="filter-modal-title"' in html
    assert 'name="filter_seasons"' in html
    assert "filter_modal.js" in html


def test_api_backtest_neutral_no_match_is_200_zeros(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    response = app.test_client().get("/api/backtest?side=home&filter_seasons=2099")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["wins"] == 0
    assert payload["losses"] == 0
    assert payload["pushes"] == 0
    assert payload["profit"] == 0
    assert payload["money_won"] == 0
    assert payload["roi"] == 0


def test_cancel_leaves_form_untouched_contract():
    """Cancel/Escape discard path must not write filter_seasons before close."""
    from pathlib import Path

    source = Path("cfb_system_maker/static/filter_modal.js").read_text(encoding="utf-8")
    assert "discardAndClose" in source
    assert "writeSeasonsToForm" in source
    # Save writes seasons; discard must not call writeSeasonsToForm
    discard_block = source.split("function discardAndClose")[1].split("function ")[0]
    assert "writeSeasonsToForm" not in discard_block
    assert "filtersForm.submit" not in discard_block
    assert "requestSubmit" not in discard_block


def test_save_serializes_seasons_contract():
    from pathlib import Path

    source = Path("cfb_system_maker/static/filter_modal.js").read_text(encoding="utf-8")
    assert "writeSeasonsToForm" in source
    assert 'seasonSelect.value = joined' in source
    assert "filter_seasons" in source
    assert "requestSubmit" in source or "filtersForm.submit" in source


def test_remove_candidate_filters_clears_core_and_feature():
    system = SystemFilter(
        side="home",
        seasons={2023, 2024},
        weeks={1, 2},
        teams={"Alpha"},
        conferences={"ACC"},
        providers={"consensus"},
        min_spread=-14.0,
        max_spread=-3.0,
        min_total=40.0,
        max_total=60.0,
        feature_filters=(
            FeatureFilter("neutralSite", "eq", True),
            FeatureFilter("venue", "in", ["A", "B"]),
            FeatureFilter("weather_temperature", "gte", 50.0),
            FeatureFilter("weather_temperature", "lte", 80.0),
        ),
    )
    cleared = remove_candidate_filters(system, "core:season")
    assert cleared.seasons == set()
    assert cleared.weeks == {1, 2}
    assert cleared.fade == system.fade

    cleared = remove_candidate_filters(system, "core:spread_range")
    assert cleared.min_spread is None and cleared.max_spread is None
    assert cleared.min_total == 40.0

    cleared = remove_candidate_filters(system, "feature:weather_temperature")
    assert all(filt.key != "weather_temperature" for filt in cleared.feature_filters)
    assert any(filt.key == "neutralSite" for filt in cleared.feature_filters)


def test_aggregate_filter_value_rows_boolean_yes_no():
    games = [
        _game(1, home_points=28, away_points=21, spread=-6.5),
        _game(2, home_points=14, away_points=28, spread=-3.0),
    ]
    feature_map = {
        1: {"neutralSite": True},
        2: {"neutralSite": False},
    }
    base = SystemFilter(side="home")
    descriptor = {
        "id": "feature:neutralSite",
        "control": "bool",
        "key": "neutralSite",
        "team_scoped": False,
    }
    rows = aggregate_filter_value_rows(
        games, base, descriptor, feature_map=feature_map, perspective="single"
    )
    labels = [row["description"] for row in rows]
    assert labels == ["No", "Yes"]
    assert {row["value"] for row in rows} == {False, True}
    for row in rows:
        assert "record" in row and "roi" in row and "money" in row
        assert isinstance(row["money"], (int, float))
        assert isinstance(row["record"], str)


def test_aggregate_filter_value_rows_categorical_sorted():
    games = [
        _game(1, season=2023),
        _game(2, season=2024),
        _game(3, season=2022),
    ]
    descriptor = {
        "id": "core:season",
        "control": "categorical",
        "key": "season",
        "team_scoped": False,
    }
    rows = aggregate_filter_value_rows(
        games, SystemFilter(side="home"), descriptor, feature_map={}, perspective="single"
    )
    assert [row["description"] for row in rows] == ["2022", "2023", "2024"]


def test_filter_detail_boolean_and_candidate_removal(tmp_path):
    games = [
        _game(1, season=2023, week=1, home_points=28, away_points=21, spread=-6.5),
        _game(2, season=2024, week=2, home_points=14, away_points=28, spread=-3.0),
        _game(3, season=2025, week=3, home_points=31, away_points=24, spread=-7.0),
    ]
    save_processed_games(tmp_path, games)
    save_features(
        tmp_path,
        {
            "1": {"neutralSite": True, "venue": "Stadium A"},
            "2": {"neutralSite": False, "venue": "Stadium B"},
            "3": {"neutralSite": False, "venue": "Stadium A"},
        },
    )
    app = create_app(data_dir=tmp_path)
    client = app.test_client()

    # Candidate seasons={2023} removed → domain still includes 2024/2025
    response = client.get("/filter-detail?candidate_id=core:season&side=home&filter_seasons=2023")
    assert response.status_code == 200
    assert response.is_json
    payload = response.get_json()
    assert payload["candidate_id"] == "core:season"
    assert payload["control"] == "categorical"
    assert payload["chart_points"] == []
    descriptions = [row["description"] for row in payload["rows"]]
    assert "2023" in descriptions
    assert "2024" in descriptions
    assert "2025" in descriptions
    assert descriptions == sorted(descriptions)

    bool_resp = client.get("/filter-detail?candidate_id=feature:neutralSite&side=home")
    assert bool_resp.status_code == 200
    bool_payload = bool_resp.get_json()
    assert bool_payload["control"] == "bool"
    assert [row["description"] for row in bool_payload["rows"]] == ["No", "Yes"]
    assert bool_payload["lookahead_warning"] in (False, "", None) or bool_payload["lookahead_warning"] is False

    cat_resp = client.get("/filter-detail?candidate_id=feature:venue&side=home")
    assert cat_resp.status_code == 200
    cat_payload = cat_resp.get_json()
    assert cat_payload["control"] == "categorical"
    assert len(cat_payload["rows"]) >= 2
    for row in cat_payload["rows"]:
        assert set(row) >= {"value", "description", "wins", "losses", "pushes", "record", "roi", "money"}


def test_filter_detail_unknown_candidate_is_400(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    response = app.test_client().get("/filter-detail?candidate_id=core:not_real&side=home")
    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload


def test_filter_detail_empty_domain_is_200(tmp_path):
    # Games exist but provider filter candidate with no providers observed after other filters
    games = [_game(1, season=2023)]
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    # Impossible other filter → empty matching set → empty rows for week still 200
    response = app.test_client().get(
        "/filter-detail?candidate_id=core:week&side=home&filter_seasons=2099"
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["rows"] == []
    assert "domain" in payload
