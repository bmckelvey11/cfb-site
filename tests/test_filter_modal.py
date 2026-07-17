"""Wave 0 contracts for filter modal: descriptions, summary seam, API, Season shell."""

from cfb_system_maker.backtest import grade_bet, run_backtest_summary
from cfb_system_maker.features import FEATURE_REGISTRY
from cfb_system_maker.models import GameRecord, SystemFilter
from cfb_system_maker.normalize import normalize_games
from cfb_system_maker.sample_data import SAMPLE_GAMES_2023, SAMPLE_LINES_2023
from cfb_system_maker.storage import save_processed_games
from cfb_system_maker.web import create_app

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
