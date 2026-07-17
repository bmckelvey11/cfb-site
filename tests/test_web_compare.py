from cfb_system_maker.models import SystemFilter
from cfb_system_maker.normalize import normalize_games
from cfb_system_maker.sample_data import SAMPLE_GAMES_2023, SAMPLE_LINES_2023
from cfb_system_maker.storage import save_processed_games, save_system
from cfb_system_maker.web import create_app


def _setup(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    save_system("home-favs", SystemFilter(side="home", favorite=True), tmp_path)
    save_system("away-dogs", SystemFilter(side="away", underdog=True), tmp_path)
    return create_app(tmp_path)


def test_compare_picker_lists_saved_systems(tmp_path):
    app = _setup(tmp_path)
    html = app.test_client().get("/compare").get_data(as_text=True)
    assert "home-favs" in html
    assert "away-dogs" in html


def test_compare_renders_metrics_per_selected_system(tmp_path):
    app = _setup(tmp_path)
    html = app.test_client().get("/compare?system=home-favs&system=away-dogs").get_data(as_text=True)
    assert "Hit rate" in html
    assert "ROI" in html
    assert "home-favs" in html
    assert "away-dogs" in html


def test_compare_skips_unknown_system_names(tmp_path):
    app = _setup(tmp_path)
    response = app.test_client().get("/compare?system=home-favs&system=does-not-exist")
    assert response.status_code == 200
    assert "home-favs" in response.get_data(as_text=True)


def test_compare_missing_data_state(tmp_path):
    app = create_app(tmp_path)
    html = app.test_client().get("/compare").get_data(as_text=True)
    assert "No processed data" in html
