import pytest

from cfb_system_maker.betting_stats import betting_stats_by_season, summarize
from cfb_system_maker.models import GameRecord
from cfb_system_maker.normalize import normalize_games
from cfb_system_maker.sample_data import SAMPLE_GAMES_2023, SAMPLE_LINES_2023
from cfb_system_maker.storage import save_processed_games
from cfb_system_maker.web import create_app


def _game(game_id, season, home_points, away_points, spread, total):
    return GameRecord(
        game_id=game_id,
        season=season,
        week=1,
        home_team=f"Home{game_id}",
        away_team=f"Away{game_id}",
        home_conference=None,
        away_conference=None,
        home_points=home_points,
        away_points=away_points,
        provider="consensus",
        spread=spread,
        total=total,
    )


# Hand-graded: spread is the home spread, a side covers on points + spread > opp.
FIXTURE = [
    _game(1, 2023, 30, 20, -7.0, 45.0),  # home fav covers by 3; 50 > 45 over
    _game(2, 2023, 20, 24, 3.0, 50.0),   # home dog loses ATS, away fav covers; 44 under
    _game(3, 2023, 24, 21, -3.0, 45.0),  # ATS push; 45 total push
    _game(4, 2023, 17, 14, 0.0, None),   # pick'em: home covers, no favorite, no total
    _game(5, 2023, None, None, -10.0, 50.0),  # not played -- excluded everywhere
    _game(6, 2024, 21, 24, 7.0, 41.0),   # home dog covers by 4; 45 over
]


def test_season_row_matches_hand_grading():
    row = summarize([g for g in FIXTURE if g.season == 2023], label="2023", season=2023)

    assert row.spread_games == 4
    assert row.home_cover_rate == pytest.approx(2 / 3)
    assert row.ats_push_rate == pytest.approx(1 / 4)
    assert row.favorite_games == 3
    assert row.favorite_cover_rate == pytest.approx(1.0)
    assert row.home_dog_games == 1
    assert row.home_dog_cover_rate == pytest.approx(0.0)
    assert row.total_games == 3
    assert row.over_rate == pytest.approx(0.5)
    assert row.ou_push_rate == pytest.approx(1 / 3)
    assert row.avg_total == pytest.approx(140 / 3)
    assert row.avg_points == pytest.approx(139 / 3)
    assert row.avg_home_spread == pytest.approx(-1.75)


def test_all_seasons_row_comes_last_and_pools_every_completed_game():
    rows = betting_stats_by_season(FIXTURE)

    assert [r.label for r in rows] == ["2024", "2023", "All seasons"]
    pooled = rows[-1]
    assert pooled.season is None
    assert pooled.spread_games == 5
    assert pooled.home_cover_rate == pytest.approx(3 / 4)
    assert pooled.favorite_cover_rate == pytest.approx(2 / 3)
    assert pooled.home_dog_cover_rate == pytest.approx(1 / 2)
    assert pooled.ats_push_rate == pytest.approx(1 / 5)
    assert pooled.over_rate == pytest.approx(2 / 3)
    assert pooled.avg_home_spread == pytest.approx(0.0)


def test_season_filter_returns_only_that_season():
    rows = betting_stats_by_season(FIXTURE, season=2024)

    assert len(rows) == 1
    assert rows[0].season == 2024
    assert rows[0].home_cover_rate == pytest.approx(1.0)
    assert rows[0].favorite_cover_rate == pytest.approx(0.0)


def test_empty_season_has_no_rates_rather_than_dividing_by_zero():
    row = summarize([], label="none")

    assert row.spread_games == 0
    assert row.home_cover_rate is None
    assert row.over_rate is None
    assert row.avg_total is None


def test_betting_stats_page_renders_fixture_numbers(tmp_path):
    save_processed_games(tmp_path, FIXTURE)
    client = create_app(data_dir=tmp_path).test_client()

    html = client.get("/betting-stats").get_data(as_text=True)

    assert "All seasons" in html
    assert "75.0%" in html  # pooled home cover
    assert "66.7%" in html  # 2023 home cover / pooled favorite cover
    assert "-1.8" in html   # 2023 avg home spread


def test_betting_stats_page_filters_by_season(tmp_path):
    save_processed_games(tmp_path, FIXTURE)
    client = create_app(data_dir=tmp_path).test_client()

    response = client.get("/betting-stats?season=2024")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "All seasons" not in html
    assert "+7.0" in html


def test_betting_stats_page_ignores_an_unknown_season(tmp_path):
    save_processed_games(tmp_path, FIXTURE)
    client = create_app(data_dir=tmp_path).test_client()

    response = client.get("/betting-stats?season=1900")

    assert response.status_code == 200
    assert "All seasons" in response.get_data(as_text=True)


def test_betting_stats_page_on_sample_data(tmp_path):
    save_processed_games(tmp_path, normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus"))
    client = create_app(data_dir=tmp_path).test_client()

    response = client.get("/betting-stats")

    assert response.status_code == 200
    assert "Betting Stats" in response.get_data(as_text=True)


def test_betting_stats_page_without_data_does_not_500(tmp_path):
    response = create_app(data_dir=tmp_path).test_client().get("/betting-stats")

    assert response.status_code == 200
    assert "No processed data found" in response.get_data(as_text=True)


def test_dashboard_links_to_betting_stats(tmp_path):
    save_processed_games(tmp_path, FIXTURE)
    html = create_app(data_dir=tmp_path).test_client().get("/").get_data(as_text=True)

    assert 'href="/betting-stats"' in html
