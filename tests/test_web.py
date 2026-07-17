import re

from cfb_system_maker.backtest import run_backtest
from cfb_system_maker.models import BacktestResult, BetDetail, SystemFilter
from cfb_system_maker.sample_data import SAMPLE_GAMES_2023, SAMPLE_LINES_2023
from cfb_system_maker.normalize import normalize_games
from cfb_system_maker.storage import save_processed_games
from cfb_system_maker.web import _cumulative_chart, create_app


def _bet_detail(game_id, season, week, profit, result="win"):
    return BetDetail(
        game_id=game_id,
        season=season,
        week=week,
        team="Alpha",
        opponent="Beta",
        side="home",
        spread=-3.0,
        total=None,
        line=-3.0,
        result=result,
        profit=profit,
    )


def _result_with_bets(bet_details):
    return BacktestResult(
        bets=len(bet_details),
        wins=0,
        losses=0,
        pushes=0,
        hit_rate=0.0,
        profit=0.0,
        roi=0.0,
        average_line=None,
        average_stake=1.0,
        bet_details=bet_details,
    )


def _metrics_section(html: str) -> str:
    """Isolate the primary stat-chip header section (not .metrics.stats-panel)."""
    start = html.index('aria-label="Backtest metrics"')
    end = html.index("</section>", start)
    return html[start:end]


def _money_won_text(profit: float) -> str:
    if profit > 0:
        return "+${:,.0f}".format(profit * 100)
    if profit < 0:
        return "-${:,.0f}".format(-profit * 100)
    return "$0"


def _chip_labels(metrics_html: str) -> list[str]:
    return re.findall(r"<span>(.*?)</span>", metrics_html)


def test_cumulative_chart_empty_bet_details_returns_zero_line_only():
    result = _result_with_bets([])

    assert _cumulative_chart(result) == {
        "points": [],
        "polyline": "",
        "zero_y": 75,
        "min_x": None,
        "max_x": None,
    }


def test_cumulative_chart_single_bet_keeps_raw_stake_units():
    bet = _bet_detail(game_id=1, season=2023, week=1, profit=0.9091)
    result = _result_with_bets([bet])

    chart = _cumulative_chart(result)

    assert len(chart["points"]) == 1
    point = chart["points"][0]
    assert set(point.keys()) == {"x", "y", "order", "profit"}
    assert point["order"] == 0
    assert point["profit"] == 0.9091
    assert chart["min_x"] == 0
    assert chart["max_x"] == 0


def test_cumulative_chart_sorts_chronologically_and_computes_running_sum():
    # True chronological order is game_id 1 (week 1), 2 (week 2), 3 (week 3)
    # with profits [0.9091, -1.0, 0.9091]. Pass shuffled to prove sorting.
    bet_1 = _bet_detail(game_id=1, season=2023, week=1, profit=0.9091, result="win")
    bet_2 = _bet_detail(game_id=2, season=2023, week=2, profit=-1.0, result="loss")
    bet_3 = _bet_detail(game_id=3, season=2023, week=3, profit=0.9091, result="win")
    result = _result_with_bets([bet_3, bet_1, bet_2])

    chart = _cumulative_chart(result)

    profits = [point["profit"] for point in chart["points"]]
    assert profits == [0.9091, -0.0909, 0.8182]


def test_cumulative_chart_same_season_week_produces_separate_points_by_game_id():
    bet_high_id = _bet_detail(game_id=5, season=2023, week=1, profit=1.0, result="win")
    bet_low_id = _bet_detail(game_id=2, season=2023, week=1, profit=-1.0, result="loss")
    result = _result_with_bets([bet_high_id, bet_low_id])

    chart = _cumulative_chart(result)

    assert len(chart["points"]) == 2
    profits = [point["profit"] for point in chart["points"]]
    assert profits == [-1.0, 0.0]


def test_web_index_loads_filters_and_default_results(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "CFB System Maker" in html
    assert "Run System" in html
    assert "Michigan" in html

    expected = run_backtest(games, SystemFilter(side="home"))
    metrics_html = _metrics_section(html)
    assert metrics_html.count("<article>") == 5
    assert _chip_labels(metrics_html) == ["Record", "Margin", "Money Won", "ROI", "Grade"]
    assert f"{expected.wins}-{expected.losses}-{expected.pushes}, {expected.hit_rate * 100:.1f}%" in metrics_html
    assert _money_won_text(expected.profit) in metrics_html
    assert '<article><span>Grade</span><strong>&mdash;</strong></article>' in metrics_html


def test_web_filters_apply_to_results(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/?side=away&underdog=on&min_spread=3")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "<td>East Carolina</td>" in html
    assert "<td>Wyoming</td>" in html
    assert "<td>South Florida</td>" not in html

    expected = run_backtest(games, SystemFilter(side="away", underdog=True, min_spread=3))
    assert expected.profit < 0  # sanity: this filter set is a losing sample
    metrics_html = _metrics_section(html)
    assert f"{expected.wins}-{expected.losses}-{expected.pushes}, {expected.hit_rate * 100:.1f}%" in metrics_html
    assert _money_won_text(expected.profit) in metrics_html
    assert '<strong class="negative">' + _money_won_text(expected.profit) + "</strong>" in metrics_html


def test_web_margin_chip_shows_em_dash_for_total_bet_systems(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/?bet_type=total&total_side=over")

    assert response.status_code == 200
    metrics_html = _metrics_section(response.get_data(as_text=True))
    assert '<article><span>Margin</span><strong class="">&mdash;</strong></article>' in metrics_html


def test_web_money_won_chip_renders_unsigned_zero_for_no_matched_bets(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/?season=2099")

    assert response.status_code == 200
    metrics_html = _metrics_section(response.get_data(as_text=True))
    assert '<article><span>Money Won</span><strong class="">$0</strong></article>' in metrics_html
    # zero matched bets also leaves average_margin at None -> em dash, same as total-bet systems
    assert '<article><span>Margin</span><strong class="">&mdash;</strong></article>' in metrics_html


def test_web_has_all_dropdowns_market_choice_and_range_chart(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/?bet_type=total&total_side=over&min_total=45&max_total=55")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<option value="">All Seasons</option>' in html
    assert '<option value="">All Weeks</option>' in html
    assert '<option value="">All Teams</option>' in html
    assert '<option value="">All Conferences</option>' in html
    assert 'name="bet_type"' in html
    assert 'Over/Under' in html
    assert "Money Won" in html
    assert "Line Range" in html


def test_web_missing_data_shows_setup_message(tmp_path):
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "No processed data found" in html
    assert "python -m cfb_system_maker build" in html


def test_web_graceful_without_features_json(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "enrich" in html
    assert "No saved systems yet" in html


def test_web_save_and_load_system(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    client = app.test_client()

    save_response = client.post(
        "/save",
        data={
            "save_name": "away-dogs",
            "bet_type": "spread",
            "side": "away",
            "total_side": "over",
            "underdog": "on",
            "min_spread": "3",
        },
    )
    assert save_response.status_code == 302

    load_response = client.get("/?load_system=away-dogs")
    html = load_response.get_data(as_text=True)
    assert "Loaded:" in html
    assert "away-dogs" in html
    assert 'name="underdog" checked' in html
    assert 'name="min_spread" value="3' in html


def test_web_index_shows_per_season_breakdown_and_permutation_p(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/?side=home&favorite=on")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Per-Season Breakdown" in html
    assert "Permutation p" in html
    assert "Profitable in" in html
