from cfb_system_maker.enrich import save_features
from cfb_system_maker.models import FeatureFilter, GameRecord, SystemFilter
from cfb_system_maker.backtest import run_backtest
from cfb_system_maker.sample_data import SAMPLE_GAMES_2023, SAMPLE_LINES_2023
from cfb_system_maker.normalize import normalize_games
from cfb_system_maker.web import create_app


def test_unenabled_feature_filters_do_not_zero_out_matches(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    # Minimal features sidecar
    save_features(
        tmp_path,
        {
            str(game.game_id): {"weather_temperature": 50.0, "neutralSite": False}
            for game in games
        },
    )
    from cfb_system_maker.storage import save_processed_games

    save_processed_games(tmp_path, games)
    app = create_app(tmp_path)

    # Submit all ff_key fields but none enabled — should match default home system bets
    response = app.test_client().get("/?side=home")
    html = response.get_data(as_text=True)
    assert "No bets matched" not in html or "Bets" in html

    # Enabled filter with impossible value should drop matches
    response = app.test_client().get(
        "/?side=home&ff_enable=weather_temperature&ff_key=weather_temperature&ff_op=gte&ff_value=999&ff_perspective=single"
    )
    html = response.get_data(as_text=True)
    assert "No bets matched these filters" in html
