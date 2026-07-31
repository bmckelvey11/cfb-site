import json
import re
from urllib.parse import parse_qs

from markupsafe import escape

from cfb_system_maker import web
from cfb_system_maker.backtest import compute_grade, run_backtest
from cfb_system_maker.enrich import save_features_to, upcoming_features_path
from cfb_system_maker.models import BacktestResult, BetDetail, GameRecord, SystemFilter
from cfb_system_maker.sample_data import SAMPLE_GAMES_2023, SAMPLE_LINES_2023
from cfb_system_maker.normalize import normalize_games
from cfb_system_maker.storage import (
    EXAMPLES_DIR,
    list_examples,
    list_systems,
    load_example_system,
    load_saved_system,
    save_processed_games,
    save_system,
    save_upcoming_games,
    save_upcoming_meta,
)
from cfb_system_maker.web import _cumulative_chart, _sparkline, create_app


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

    response = app.test_client().get("/system")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "CFB System Maker" in html
    assert "Run System" in html
    assert "Michigan" in html

    expected = run_backtest(games, SystemFilter(side="home"))
    expected_grade = compute_grade(expected, SystemFilter(side="home"))
    metrics_html = _metrics_section(html)
    assert metrics_html.count("<article>") == 5
    assert _chip_labels(metrics_html) == ["Record", "Margin", "Money Won", "ROI", "Grade"]
    assert f"{expected.wins}-{expected.losses}-{expected.pushes}, {expected.hit_rate * 100:.1f}%" in metrics_html
    assert _money_won_text(expected.profit) in metrics_html
    assert f"<span>Grade</span><strong>{expected_grade}</strong>" in metrics_html


def test_web_filters_apply_to_results(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system?side=away&underdog=on&min_spread=3&tab=matches")

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


def test_web_malformed_choice_params_fall_back_to_defaults_instead_of_500(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system?bet_type=nonsense&side=sideways&total_side=whenever")

    assert response.status_code == 200
    expected = run_backtest(games, SystemFilter(side="home"))
    metrics_html = _metrics_section(response.get_data(as_text=True))
    assert f"{expected.wins}-{expected.losses}-{expected.pushes}, {expected.hit_rate * 100:.1f}%" in metrics_html


def test_web_margin_chip_shows_em_dash_for_total_bet_systems(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system?bet_type=total&total_side=over")

    assert response.status_code == 200
    metrics_html = _metrics_section(response.get_data(as_text=True))
    assert '<article><span>Margin</span><strong class="">&mdash;</strong></article>' in metrics_html


def test_web_money_won_chip_renders_unsigned_zero_for_no_matched_bets(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system?season=2099")

    assert response.status_code == 200
    metrics_html = _metrics_section(response.get_data(as_text=True))
    assert '<article><span>Money Won</span><strong class="">$0</strong></article>' in metrics_html
    # zero matched bets also leaves average_margin at None -> em dash, same as total-bet systems
    assert '<article><span>Margin</span><strong class="">&mdash;</strong></article>' in metrics_html


def test_web_grade_chip_renders_computed_letter_for_default_system(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system")

    assert response.status_code == 200
    metrics_html = _metrics_section(response.get_data(as_text=True))
    expected = run_backtest(games, SystemFilter(side="home"))
    expected_grade = compute_grade(expected, SystemFilter(side="home"))
    assert f"<span>Grade</span><strong>{expected_grade}</strong>" in metrics_html


def test_web_grade_chip_renders_em_dash_for_zero_matched_bets(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system?season=2099")
    metrics_html = _metrics_section(response.get_data(as_text=True))
    assert "<span>Grade</span><strong>&mdash;</strong>" in metrics_html

    faded_response = app.test_client().get("/system?season=2099&fade=on")
    faded_metrics_html = _metrics_section(faded_response.get_data(as_text=True))
    assert "<span>Grade</span><strong>&mdash;</strong>" in faded_metrics_html


def test_web_has_all_dropdowns_market_choice_and_range_chart(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system?bet_type=total&total_side=over&min_total=45&max_total=55")

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

    response = app.test_client().get("/system")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "No processed data found" in html
    assert "python -m cfb_system_maker build" in html


def test_web_graceful_without_features_json(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system")

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

    load_response = client.get("/system?load_system=away-dogs")
    html = load_response.get_data(as_text=True)
    assert "Loaded:" in html
    assert "away-dogs" in html
    assert 'name="underdog" checked' in html
    assert 'name="min_spread" value="3' in html


def test_web_save_rejects_path_traversal_name_without_writing_outside_data_dir(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    client = app.test_client()

    save_response = client.post(
        "/save",
        data={"save_name": "../../outside_secret", "bet_type": "spread", "side": "home", "total_side": "over"},
    )
    assert save_response.status_code == 302
    assert not (tmp_path.parent.parent / "outside_secret.json").exists()


def test_web_load_system_path_traversal_name_treated_as_not_found(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system?load_system=../../secret_system")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "not found" in html
    assert "Loaded:" not in html


def test_web_compare_ignores_path_traversal_system_name(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/compare?system=../../secret_system")

    assert response.status_code == 200


def test_web_index_shows_per_season_breakdown_and_permutation_p(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system?side=home&favorite=on")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Per-Season Breakdown" in html
    assert "Permutation p" in html
    assert "Profitable in" in html


def test_web_default_tab_shows_results_graph_view(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Money Won Over Time" in html
    assert 'class="range-chart"' in html
    assert '<section class="table-wrap">' not in html


def test_web_invalid_tab_value_normalizes_to_results_graph(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system?tab=garbage")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'aria-current="page">Results Graph</a>' in html
    assert '<section class="table-wrap">' not in html


def test_web_cumulative_chart_svg_title_shows_dollar_scaled_value(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Bet 1: +$90.91" in html


def test_web_tab_switch_preserves_load_system_and_round_trips(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    client = app.test_client()

    client.post(
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

    response = client.get("/system?load_system=away-dogs&tab=matches")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    match = re.search(r'<a href="([^"]*)"[^>]*>Results Graph</a>', html)
    assert match is not None
    graph_href = match.group(1).replace("&amp;", "&")
    assert "tab=graph" in graph_href
    assert "load_system=away-dogs" in graph_href

    assert "Money Won Over Time" not in html
    assert '<section class="table-wrap">' in html

    second_response = client.get("/system" + graph_href)
    assert second_response.status_code == 200
    second_html = second_response.get_data(as_text=True)
    assert "load_system=away-dogs" in second_html
    assert "Money Won Over Time" in second_html


def test_web_tab_switch_preserves_load_system_and_round_trips_fade(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    client = app.test_client()

    client.post(
        "/save",
        data={
            "save_name": "away-dogs-fade",
            "bet_type": "spread",
            "side": "away",
            "total_side": "over",
            "underdog": "on",
            "min_spread": "3",
            "fade": "on",
        },
    )

    response = client.get("/system?load_system=away-dogs-fade&tab=matches")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="fade" form="filters-form" checked' in html

    match = re.search(r'<a href="([^"]*)"[^>]*>Results Graph</a>', html)
    assert match is not None
    graph_href = match.group(1).replace("&amp;", "&")
    assert "tab=graph" in graph_href
    assert "load_system=away-dogs-fade" in graph_href

    second_response = client.get("/system" + graph_href)
    assert second_response.status_code == 200
    second_html = second_response.get_data(as_text=True)
    assert "load_system=away-dogs-fade" in second_html
    assert 'name="fade" form="filters-form" checked' in second_html


def _remove_href_for(html: str, aria_label: str) -> str:
    match = re.search(
        r'<a class="remove-filter" href="([^"]*)" aria-label="' + re.escape(aria_label) + r'">',
        html,
    )
    assert match is not None, f"remove-filter link with aria-label {aria_label!r} not found"
    return match.group(1).replace("&amp;", "&")


def test_web_spread_range_remove_href_omits_both_bounds_and_preserves_other_params(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system?side=away&underdog=on&min_spread=3")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    href = _remove_href_for(html, "Remove filter: the spread is at least 3")

    assert "min_spread" not in href
    assert "max_spread" not in href
    assert "side=away" in href
    assert "underdog=on" in href


def test_web_feature_filter_remove_href_keeps_five_arrays_aligned(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get(
        "/system?side=home"
        "&ff_enable=weather_temperature&ff_enable=weather_windSpeed"
        "&ff_key=weather_temperature&ff_key=weather_windSpeed"
        "&ff_op=gte&ff_op=lte"
        "&ff_value=40&ff_value=20"
        "&ff_perspective=single&ff_perspective=single"
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    href = _remove_href_for(html, "Remove filter: Temperature (F) is at least 40")

    parsed = parse_qs(href.lstrip("?"))
    assert parsed["ff_key"] == ["weather_windSpeed"]
    assert parsed["ff_op"] == ["lte"]
    assert parsed["ff_value"] == ["20"]
    assert parsed["ff_perspective"] == ["single"]
    assert parsed["ff_enable"] == ["weather_windSpeed"]


def test_web_loaded_system_remove_link_materializes_and_drops_load_system(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    client = app.test_client()

    client.post(
        "/save",
        data={
            "save_name": "two-filters",
            "bet_type": "spread",
            "side": "away",
            "total_side": "over",
            "underdog": "on",
            "min_spread": "3",
            "theory": "Fade home dogs late season.",
        },
    )

    response = client.get("/system?load_system=two-filters&tab=matches")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "the team is an underdog" in html
    assert "the spread is at least 3" in html
    assert "Fade home dogs late season." in html

    href = _remove_href_for(html, "Remove filter: the team is an underdog")
    assert "load_system" not in href
    assert "save_name=two-filters" in href
    assert "tab=matches" in href
    assert "theory=" in href

    second_response = client.get("/system" + href)
    assert second_response.status_code == 200
    second_html = second_response.get_data(as_text=True)

    assert "the team is an underdog" not in second_html
    assert "the spread is at least 3" in second_html
    assert 'name="underdog" checked' not in second_html
    assert "Fade home dogs late season." in second_html
    # save_name survives as URL state (carried in the tab-nav href, which preserves the full query string)
    graph_link_match = re.search(r'<a href="([^"]*)"[^>]*>Results Graph</a>', second_html)
    assert graph_link_match is not None
    assert "save_name=two-filters" in graph_link_match.group(1).replace("&amp;", "&")
    assert 'aria-current="page">Past Matches</a>' in second_html


def test_web_loaded_system_remove_link_preserves_fade(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    client = app.test_client()

    client.post(
        "/save",
        data={
            "save_name": "two-filters-fade",
            "bet_type": "spread",
            "side": "away",
            "total_side": "over",
            "underdog": "on",
            "min_spread": "3",
            "fade": "on",
        },
    )

    response = client.get("/system?load_system=two-filters-fade&tab=matches")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="fade" form="filters-form" checked' in html

    href = _remove_href_for(html, "Remove filter: the team is an underdog")
    assert "fade=on" in href

    second_response = client.get("/system" + href)
    assert second_response.status_code == 200
    second_html = second_response.get_data(as_text=True)
    assert 'name="fade" form="filters-form" checked' in second_html


def test_web_no_active_filters_shows_empty_state_copy(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "No filters applied yet — every game in the dataset is included." in html


def test_web_active_filter_sentence_renders_with_remove_control(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system?side=home&favorite=on")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "the team is a favorite" in html
    assert 'aria-label="Remove filter: the team is a favorite"' in html


def test_web_save_and_load_system_preserves_theory(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    client = app.test_client()

    save_response = client.post(
        "/save",
        data={
            "save_name": "theory-system",
            "bet_type": "spread",
            "side": "home",
            "total_side": "over",
            "theory": "Fade the public.",
        },
    )
    assert save_response.status_code == 302

    load_response = client.get("/system?load_system=theory-system")
    html = load_response.get_data(as_text=True)
    assert 'name="theory"' in html
    assert "Fade the public." in html


def test_web_save_and_load_system_preserves_fade(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    client = app.test_client()

    save_response = client.post(
        "/save",
        data={
            "save_name": "faded-system",
            "bet_type": "spread",
            "side": "home",
            "total_side": "over",
            "fade": "on",
        },
    )
    assert save_response.status_code == 302

    load_response = client.get("/system?load_system=faded-system")
    html = load_response.get_data(as_text=True)
    assert 'name="fade" form="filters-form" checked' in html


def test_web_fresh_index_does_not_render_theory_panel(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "theory-panel" not in html


def test_web_theory_round_trips_through_get_form_submission(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/system?theory=Unsaved+hypothesis&save_name=draft")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="theory"' in html
    assert "Unsaved hypothesis" in html
    assert 'class="theory-panel"' in html
    assert 'value="draft"' in html


def test_web_theory_is_escaped_and_never_rendered_via_safe_filter(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    client = app.test_client()

    client.post(
        "/save",
        data={
            "save_name": "xss-theory",
            "bet_type": "spread",
            "side": "home",
            "total_side": "over",
            "theory": '<script>alert(1)</script> "quoted"',
        },
    )

    response = client.get("/system?load_system=xss-theory")
    html = response.get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


# --- Dashboard (Phase 5, Plan 03) ---------------------------------------------


def _dashboard_app(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    return create_app(data_dir=tmp_path), games


def _save_a_system(client, name, **extra):
    data = {
        "save_name": name,
        "bet_type": "spread",
        "side": "home",
        "total_side": "over",
    }
    data.update(extra)
    return client.post("/save", data=data)


def test_dashboard_is_served_at_root(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    response = app.test_client().get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "My Systems" in html
    # The editor's filter form must not be on the dashboard.
    assert 'id="filters-form"' not in html


def test_editor_is_served_at_system(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    response = app.test_client().get("/system")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="filters-form"' in html
    assert "Run System" in html


def test_dashboard_loads_no_javascript(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    html = app.test_client().get("/").get_data(as_text=True)

    assert "<script" not in html
    assert "filter_modal.js" not in html


def test_root_with_editor_filter_params_redirects_to_system_preserving_query(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    response = app.test_client().get("/?side=home&favorite=on")

    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("/system?")
    assert "side=home" in location
    assert "favorite=on" in location


def test_root_redirect_preserves_repeated_multi_value_params(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    response = app.test_client().get("/?filter_seasons=2022&filter_seasons=2023")

    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.count("filter_seasons=") == 2


def test_root_with_load_system_redirects_to_editor(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    response = app.test_client().get("/?load_system=away-dogs")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/system?")
    assert "load_system=away-dogs" in response.headers["Location"]


def test_root_with_feature_filter_param_redirects_to_editor(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    response = app.test_client().get("/?ff_enabled=core%3Aseason")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/system?")


def test_root_with_dashboard_tab_param_does_not_redirect(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    response = app.test_client().get("/?tab=examples")

    assert response.status_code == 200


def test_root_with_timeframe_param_does_not_redirect(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    response = app.test_client().get("/?timeframe=2023")

    assert response.status_code == 200


def test_dashboard_unknown_tab_falls_back_to_default_scope(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    response = app.test_client().get("/?tab=garbage")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'aria-current="page"' in html
    assert "My Systems" in html


def test_dashboard_missing_games_file_renders_missing_data_state(tmp_path):
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert "No processed data found" in response.get_data(as_text=True)


def test_save_redirects_to_editor_with_system_loaded(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    client = app.test_client()

    response = _save_a_system(client, "dash-save")

    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("/system")
    assert "load_system=dash-save" in location


def test_save_without_name_redirects_to_editor_not_dashboard(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    response = app.test_client().post("/save", data={"save_name": "  "})

    assert response.status_code == 302
    assert response.headers["Location"].rstrip("?") == "/system"


def test_dashboard_lists_saved_system_with_record_money_and_roi(tmp_path):
    app, games = _dashboard_app(tmp_path)
    client = app.test_client()
    _save_a_system(client, "dash-home")

    html = client.get("/").get_data(as_text=True)

    expected = run_backtest(games, SystemFilter(side="home"))
    assert "dash-home" in html
    assert _money_won_text(expected.profit) in html
    assert "{:.2f}%".format(expected.roi * 100) in html
    assert "{}-{}-{}".format(expected.wins, expected.losses, expected.pushes) in html


def test_dashboard_escapes_system_name_and_theory(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    client = app.test_client()
    _save_a_system(client, "xss-dash", theory='<script>alert(1)</script> "quoted"')

    html = client.get("/").get_data(as_text=True)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_dashboard_shows_fade_suffix_on_type_column(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    client = app.test_client()
    _save_a_system(client, "faded-dash", fade="on")

    html = client.get("/").get_data(as_text=True)

    assert "Fade" in html


# --- Sparkline & timeframe tabs (Phase 5, Plan 03) ----------------------------


def test_sparkline_empty_series_reports_empty_and_emits_no_polyline():
    spark = _sparkline([])

    assert spark["empty"] is True
    assert spark["polyline"] == ""


def test_sparkline_single_bet_is_horizontal_segment_at_mid_height():
    spark = _sparkline([_bet_detail(game_id=1, season=2023, week=1, profit=0.9091)])

    coords = [pair.split(",") for pair in spark["polyline"].split()]
    assert len(coords) == 2
    ys = {float(y) for _x, y in coords}
    assert ys == {12.0}
    assert spark["empty"] is False


def test_sparkline_sign_class_follows_final_cumulative_value():
    up = _sparkline([
        _bet_detail(game_id=1, season=2023, week=1, profit=-1.0),
        _bet_detail(game_id=2, season=2023, week=2, profit=2.0),
    ])
    down = _sparkline([
        _bet_detail(game_id=1, season=2023, week=1, profit=1.0),
        _bet_detail(game_id=2, season=2023, week=2, profit=-2.0),
    ])

    assert up["sign_class"] == "positive"
    assert down["sign_class"] == "negative"


def test_sparkline_zero_final_value_is_positive_class():
    spark = _sparkline([
        _bet_detail(game_id=1, season=2023, week=1, profit=1.0),
        _bet_detail(game_id=2, season=2023, week=2, profit=-1.0),
    ])

    assert spark["sign_class"] == "positive"


def test_sparkline_downsamples_to_at_most_48_points():
    bets = [_bet_detail(game_id=i, season=2023, week=i, profit=1.0) for i in range(200)]

    spark = _sparkline(bets)

    assert len(spark["polyline"].split()) == 48


def test_sparkline_flat_series_renders_centered_horizontal_line():
    bets = [_bet_detail(game_id=i, season=2023, week=i, profit=0.0) for i in range(5)]

    spark = _sparkline(bets)

    ys = {float(pair.split(",")[1]) for pair in spark["polyline"].split()}
    assert ys == {12.0}


def test_sparkline_sorts_chronologically_regardless_of_input_order():
    early = _bet_detail(game_id=1, season=2023, week=1, profit=5.0)
    late = _bet_detail(game_id=2, season=2023, week=9, profit=-5.0)

    shuffled = _sparkline([late, early])
    ordered = _sparkline([early, late])

    assert shuffled["polyline"] == ordered["polyline"]


def test_dashboard_zero_bet_system_shows_em_dash_not_a_flat_line(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    client = app.test_client()
    _save_a_system(client, "no-bets", filter_seasons="1999")

    html = client.get("/").get_data(as_text=True)

    row = html[html.index("no-bets"):]
    row = row[: row.index("</tr>")]
    assert "&mdash;" in row
    assert "<polyline" not in row


def test_dashboard_renders_sparkline_for_system_with_bets(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    client = app.test_client()
    _save_a_system(client, "has-bets")

    html = client.get("/").get_data(as_text=True)

    assert "<polyline" in html
    assert 'class="sparkline"' in html
    assert "Cumulative profit trend" in html


def test_dashboard_timeframe_tabs_list_all_time_plus_each_season_newest_first(tmp_path):
    app, games = _dashboard_app(tmp_path)
    client = app.test_client()
    _save_a_system(client, "tf-system")

    html = client.get("/").get_data(as_text=True)

    assert "All Time" in html
    seasons = sorted({game.season for game in games}, reverse=True)
    positions = [html.index("timeframe={}".format(season)) for season in seasons]
    assert positions == sorted(positions)


def test_dashboard_timeframe_selection_changes_table_figures(tmp_path):
    app, games = _dashboard_app(tmp_path)
    client = app.test_client()
    _save_a_system(client, "tf-figures")
    season = sorted({game.season for game in games})[0]

    html = client.get("/?timeframe={}".format(season)).get_data(as_text=True)

    result = run_backtest(games, SystemFilter(side="home"))
    record = next(row for row in result.season_breakdown if row.season == season)
    assert _money_won_text(record.profit) in html


def test_dashboard_unknown_timeframe_falls_back_to_all_time(tmp_path):
    app, games = _dashboard_app(tmp_path)
    client = app.test_client()
    _save_a_system(client, "tf-fallback")

    html = client.get("/?timeframe=../../etc/passwd").get_data(as_text=True)

    expected = run_backtest(games, SystemFilter(side="home"))
    assert _money_won_text(expected.profit) in html


def test_dashboard_timeframe_not_in_data_falls_back_to_all_time(tmp_path):
    app, games = _dashboard_app(tmp_path)
    client = app.test_client()
    _save_a_system(client, "tf-absent")

    html = client.get("/?timeframe=1999").get_data(as_text=True)

    expected = run_backtest(games, SystemFilter(side="home"))
    assert _money_won_text(expected.profit) in html


# --- P1-002: search-provenance badge + candidate count -------------------------


def test_dashboard_shows_badge_and_candidate_count_for_search_sourced_system(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    save_system(
        "found-it",
        SystemFilter(side="home"),
        tmp_path,
        source="search",
        search_candidates_tested=500,
    )

    html = app.test_client().get("/").get_data(as_text=True)

    assert 'class="badge-search"' in html
    assert "500 candidates tested" in html


def test_dashboard_omits_badge_and_candidate_count_for_manual_system(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    client = app.test_client()
    _save_a_system(client, "manual-sys")

    html = client.get("/").get_data(as_text=True)

    assert 'class="badge-search"' not in html
    assert "candidates tested" not in html


def test_dashboard_shows_badge_but_omits_count_when_search_candidates_tested_is_none(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    save_system(
        "found-no-count",
        SystemFilter(side="home"),
        tmp_path,
        source="search",
    )

    html = app.test_client().get("/").get_data(as_text=True)

    assert 'class="badge-search"' in html
    assert "candidates tested" not in html


# --- Example Systems tab (Phase 5, Plan 05) -----------------------------------


def test_example_systems_tab_lists_all_three_examples(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    response = app.test_client().get("/?tab=examples")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for name in list_examples():
        assert name in html
    assert "not betting recommendations" in html


def test_example_systems_tab_shows_figures_and_trend_column(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    html = app.test_client().get("/?tab=examples").get_data(as_text=True)

    # Same table shape as My Systems, from the same backtest path.
    assert "Money Won" in html
    assert "Trend" in html
    assert html.count("Copy to My Systems") == len(list_examples())
    # The left column must not fall back to its empty state (examples render).
    # The Current Matches panel legitimately shows its own no-systems copy
    # (UI-SPEC: both columns show the no-systems state), so scope to dash-main.
    main = html[html.index('class="dash-main"'):html.index('aria-label="Current Matches"')]
    assert "No saved systems yet" not in main


def test_example_systems_tab_shows_each_written_theory(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    html = app.test_client().get("/?tab=examples").get_data(as_text=True)

    for name in list_examples():
        theory = load_example_system(name).theory
        assert theory.strip()
        assert escape(theory.strip()) in html


def test_my_systems_tab_never_lists_an_example(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    client = app.test_client()
    _save_a_system(client, "my-own-system")

    html = client.get("/").get_data(as_text=True)

    assert "my-own-system" in html
    for name in list_examples():
        assert name not in html


def test_example_systems_tab_never_lists_a_user_system(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    client = app.test_client()
    _save_a_system(client, "my-own-system")

    html = client.get("/?tab=examples").get_data(as_text=True)

    assert "my-own-system" not in html


def test_copy_example_creates_an_ordinary_saved_system(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    client = app.test_client()

    response = client.post("/copy-example", data={"name": "nonconference-away-dogs"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/?tab=examples")
    assert "nonconference-away-dogs" in list_systems(tmp_path)
    copied = load_saved_system("nonconference-away-dogs", tmp_path)
    original = load_example_system("nonconference-away-dogs")
    assert copied.system == original.system
    assert copied.theory == original.theory


def test_copy_example_leaves_the_bundled_file_untouched(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    bundled = EXAMPLES_DIR / "nonconference-away-dogs.json"
    before = bundled.read_bytes()

    app.test_client().post("/copy-example", data={"name": "nonconference-away-dogs"})

    assert bundled.read_bytes() == before


def test_copy_example_rejects_a_traversal_name(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    response = app.test_client().post("/copy-example", data={"name": "../../outside_secret"})

    assert response.status_code == 302
    assert not (tmp_path.parent.parent / "outside_secret.json").exists()
    assert list_systems(tmp_path) == []


def test_copy_example_rejects_an_unknown_name(tmp_path):
    app, _ = _dashboard_app(tmp_path)

    response = app.test_client().post("/copy-example", data={"name": "not-an-example"})

    assert response.status_code == 302
    assert list_systems(tmp_path) == []


def test_example_systems_tab_escapes_name_and_theory(tmp_path, monkeypatch):
    app, _ = _dashboard_app(tmp_path)
    hostile = tmp_path / "hostile-examples"
    hostile.mkdir()
    (hostile / "xss-example.json").write_text(
        json.dumps(
            {
                "name": "<script>alert(1)</script>",
                "theory": '<img src=x onerror=alert(2)> "quoted"',
                "system": {"bet_type": "spread", "side": "home"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(web, "EXAMPLES_DIR", hostile)

    html = app.test_client().get("/?tab=examples").get_data(as_text=True)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img src=x onerror=alert(2)>" not in html
    assert "&lt;img src=x onerror=alert(2)&gt;" in html


# --- Current Matches panel (Phase 5, Plan 06) --------------------------------


def _upcoming_game(
    game_id,
    home,
    away,
    *,
    spread=-7.0,
    total=52.5,
    season=2025,
    week=1,
    provider="DraftKings",
    home_conf="SEC",
    away_conf="ACC",
):
    return GameRecord(
        game_id=game_id,
        season=season,
        week=week,
        home_team=home,
        away_team=away,
        home_conference=home_conf,
        away_conference=away_conf,
        home_points=None,
        away_points=None,
        provider=provider,
        spread=spread,
        total=total,
    )


def _write_upcoming(
    tmp_path,
    games,
    kickoffs,
    *,
    is_fallback=False,
    season=2025,
    week=1,
    fetched_at="2025-09-05T13:14:00+00:00",
    features=None,
):
    save_upcoming_games(tmp_path, games, kickoffs)
    save_upcoming_meta(
        tmp_path,
        {
            "fetched_at": fetched_at,
            "season": season,
            "week": week,
            "season_type": "regular",
            "is_fallback": is_fallback,
            "row_count": len(games),
        },
    )
    save_features_to(upcoming_features_path(tmp_path), features or {})


def _panel(html: str) -> str:
    """Slice the Current Matches panel out of the rendered dashboard."""
    start = html.index('aria-label="Current Matches"')
    return html[start:]


def _kick(game_id, start_date, *, tbd=False):
    return {game_id: {"start_date": start_date, "start_time_tbd": tbd}}


def test_current_matches_lists_a_row_for_a_matched_system(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    game = _upcoming_game(9001, "Georgia", "Clemson")
    _write_upcoming(tmp_path, [game], _kick(9001, "2025-09-06T19:30:00+00:00"))
    save_system("home-spreads", SystemFilter(bet_type="spread", side="home"), tmp_path)

    html = app.test_client().get("/").get_data(as_text=True)
    panel = _panel(html)

    assert "Play Georgia -7" in panel
    assert "Clemson @ Georgia" in panel
    assert "home-spreads" in panel


def test_current_matches_omits_a_system_that_does_not_match(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    game = _upcoming_game(9001, "Georgia", "Clemson")
    _write_upcoming(tmp_path, [game], _kick(9001, "2025-09-06T19:30:00+00:00"))
    save_system(
        "nowhere",
        SystemFilter(bet_type="spread", side="home", teams={"Nowhere State"}),
        tmp_path,
    )

    panel = _panel(app.test_client().get("/").get_data(as_text=True))

    assert "Play" not in panel
    assert "No saved system matches a game this week." in panel


def test_current_matches_spread_play_text_home_and_away(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    game = _upcoming_game(9001, "Georgia", "Clemson", spread=-7.0)
    _write_upcoming(tmp_path, [game], _kick(9001, "2025-09-06T19:30:00+00:00"))
    save_system("home-side", SystemFilter(bet_type="spread", side="home"), tmp_path)
    save_system("away-side", SystemFilter(bet_type="spread", side="away"), tmp_path)

    panel = _panel(app.test_client().get("/").get_data(as_text=True))

    assert "Play Georgia -7" in panel
    assert "Play Clemson +7" in panel


def test_current_matches_fade_home_side_names_the_away_team(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    game = _upcoming_game(9001, "Georgia", "Clemson", spread=-7.0)
    _write_upcoming(tmp_path, [game], _kick(9001, "2025-09-06T19:30:00+00:00"))
    save_system(
        "fade-home", SystemFilter(bet_type="spread", side="home", fade=True), tmp_path
    )

    panel = _panel(app.test_client().get("/").get_data(as_text=True))

    # A fade of a home-favorite is a bet on the away team; the play must say so.
    assert "Play Clemson +7" in panel
    assert "Play Georgia" not in panel


def test_current_matches_total_play_text_and_fade(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    game = _upcoming_game(9001, "Georgia", "Clemson", total=52.5)
    _write_upcoming(tmp_path, [game], _kick(9001, "2025-09-06T19:30:00+00:00"))
    save_system("overs", SystemFilter(bet_type="total", total_side="over"), tmp_path)
    save_system(
        "fade-overs",
        SystemFilter(bet_type="total", total_side="over", fade=True),
        tmp_path,
    )

    panel = _panel(app.test_client().get("/").get_data(as_text=True))

    assert "Play Over 52.5" in panel
    assert "Play Under 52.5" in panel


def test_current_matches_details_reuse_describe_undecorated(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    game = _upcoming_game(9001, "Georgia", "Clemson", spread=-7.0)
    _write_upcoming(tmp_path, [game], _kick(9001, "2025-09-06T19:30:00+00:00"))
    save_system(
        "fav", SystemFilter(bet_type="spread", side="home", favorite=True), tmp_path
    )

    panel = _panel(app.test_client().get("/").get_data(as_text=True))

    assert "the team is a favorite" in panel
    # No editor remove/edit affordances on the dashboard details.
    assert "Remove" not in panel
    assert "remove_href" not in panel


def test_current_matches_bare_system_omits_the_matched_on_label(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    game = _upcoming_game(9001, "Georgia", "Clemson")
    _write_upcoming(tmp_path, [game], _kick(9001, "2025-09-06T19:30:00+00:00"))
    # A default side=home system produces no describe() sentences.
    save_system("bare", SystemFilter(bet_type="spread", side="home"), tmp_path)

    panel = _panel(app.test_client().get("/").get_data(as_text=True))

    assert "Play Georgia -7" in panel  # row still renders
    assert "Matched on" not in panel  # but no dangling empty label


def test_current_matches_sorts_by_kickoff_ascending(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    early = _upcoming_game(9001, "Georgia", "Clemson")
    late = _upcoming_game(9002, "Oregon", "Washington")
    kicks = {}
    kicks.update(_kick(9001, "2025-09-06T16:00:00+00:00"))
    kicks.update(_kick(9002, "2025-09-06T23:30:00+00:00"))
    _write_upcoming(tmp_path, [late, early], kicks)
    save_system("home-spreads", SystemFilter(bet_type="spread", side="home"), tmp_path)

    panel = _panel(app.test_client().get("/").get_data(as_text=True))

    assert panel.index("Clemson @ Georgia") < panel.index("Washington @ Oregon")


def test_current_matches_sorts_by_system_name_within_a_kickoff(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    game = _upcoming_game(9001, "Georgia", "Clemson")
    _write_upcoming(tmp_path, [game], _kick(9001, "2025-09-06T19:30:00+00:00"))
    save_system("zzz-system", SystemFilter(bet_type="spread", side="home"), tmp_path)
    save_system("aaa-system", SystemFilter(bet_type="spread", side="home"), tmp_path)

    panel = _panel(app.test_client().get("/").get_data(as_text=True))

    assert panel.index("aaa-system") < panel.index("zzz-system")


def test_current_matches_tbd_kickoff_renders_date_without_a_clock_time(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    game = _upcoming_game(9001, "Georgia", "Clemson")
    _write_upcoming(
        tmp_path, [game], _kick(9001, "2025-09-06T15:45:00+00:00", tbd=True)
    )
    save_system("home-spreads", SystemFilter(bet_type="spread", side="home"), tmp_path)

    panel = _panel(app.test_client().get("/").get_data(as_text=True))

    cells = re.findall(r'class="cm-kickoff"[^>]*>([^<]*)<', panel)
    assert cells, "expected a kickoff cell in the panel"
    kickoff = cells[0]
    assert kickoff.strip(), "kickoff date should still render"
    # A TBD kickoff must not fabricate a clock time.
    assert ":" not in kickoff


def test_current_matches_offseason_shows_notice_and_labelled_fallback_rows(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    game = _upcoming_game(9001, "Georgia", "Clemson", season=2025, week=16)
    _write_upcoming(
        tmp_path,
        [game],
        _kick(9001, "2025-12-06T19:30:00+00:00"),
        is_fallback=True,
        season=2025,
        week=16,
    )
    save_system("home-spreads", SystemFilter(bet_type="spread", side="home"), tmp_path)

    panel = _panel(app.test_client().get("/").get_data(as_text=True))

    # All three parts, not one instead of another.
    assert "stale-warning" in panel
    assert "Most recent week with data: Week 16, 2025" in panel
    assert "Play Georgia -7" in panel


def test_current_matches_week_present_but_no_match_is_neutral_not_amber(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    game = _upcoming_game(9001, "Georgia", "Clemson")
    _write_upcoming(tmp_path, [game], _kick(9001, "2025-09-06T19:30:00+00:00"))
    save_system(
        "nowhere",
        SystemFilter(bet_type="spread", side="home", teams={"Nowhere State"}),
        tmp_path,
    )

    response = app.test_client().get("/")
    panel = _panel(response.get_data(as_text=True))

    assert response.status_code == 200
    assert "No saved system matches a game this week." in panel
    assert "stale-warning" not in panel


def test_current_matches_missing_upcoming_file_names_the_cli_command(tmp_path):
    app, _ = _dashboard_app(tmp_path)  # games.csv present, no upcoming.csv
    save_system("home-spreads", SystemFilter(bet_type="spread", side="home"), tmp_path)

    response = app.test_client().get("/")

    assert response.status_code == 200
    panel = _panel(response.get_data(as_text=True))
    assert "python -m cfb_system_maker upcoming --data-dir data" in panel


def test_current_matches_no_saved_systems_points_at_examples(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    game = _upcoming_game(9001, "Georgia", "Clemson")
    _write_upcoming(tmp_path, [game], _kick(9001, "2025-09-06T19:30:00+00:00"))
    # No saved systems.

    panel = _panel(app.test_client().get("/").get_data(as_text=True))

    assert "Example Systems" in panel
    assert "Play Georgia" not in panel


def test_current_matches_escapes_team_and_system_names(tmp_path):
    app, _ = _dashboard_app(tmp_path)
    game = _upcoming_game(9001, "<script>Georgia</script>", "Clemson")
    _write_upcoming(tmp_path, [game], _kick(9001, "2025-09-06T19:30:00+00:00"))
    # Hand-written system JSON: safe stem, metacharacter display name.
    (tmp_path / "systems").mkdir(parents=True, exist_ok=True)
    (tmp_path / "systems" / "evil.json").write_text(
        json.dumps(
            {
                "name": "<b>evil</b>",
                "saved_at": "2025-01-01T00:00:00+00:00",
                "theory": "",
                "system": {"bet_type": "spread", "side": "home"},
            }
        ),
        encoding="utf-8",
    )

    html = app.test_client().get("/").get_data(as_text=True)
    panel = _panel(html)

    assert "<script>Georgia</script>" not in panel
    assert "&lt;script&gt;Georgia&lt;/script&gt;" in panel
    assert "<b>evil</b>" not in panel
    assert "&lt;b&gt;evil&lt;/b&gt;" in panel


def test_search_run_view_renders_finalist_stats(tmp_path):
    from cfb_system_maker.models import SearchRun, SearchRunFinalist, SystemFilter
    from cfb_system_maker.storage import save_search_run
    from cfb_system_maker.web import create_app

    finalist = SearchRunFinalist(
        system=SystemFilter(bet_type="spread", side="home", favorite=True),
        wins=12, losses=8, pushes=1, roi=0.0524,
        raw_p=0.031, corrected_p=0.062, bh_significant=False,
    )
    run = SearchRun(
        name="my-run", saved_at="2026-07-31T00:00:00+00:00",
        candidates_tested=482, finalists_graded=1,
        effective_params={"beam_width": 100, "top_k": 20, "min_decided_bets": 100, "alpha": 0.05},
        finalists=(finalist,),
    )
    save_search_run("my-run", run, tmp_path)

    app = create_app(str(tmp_path))
    client = app.test_client()
    response = client.get("/search-runs/my-run")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "482" in body
    assert "12-8-1" in body or ("12" in body and "8" in body)
    assert "Narrate results" in body


def test_search_run_view_missing_run_returns_404(tmp_path):
    from cfb_system_maker.web import create_app

    app = create_app(str(tmp_path))
    client = app.test_client()
    response = client.get("/search-runs/does-not-exist")

    assert response.status_code == 404


def test_search_run_view_rejects_unsafe_name(tmp_path):
    from cfb_system_maker.web import create_app

    app = create_app(str(tmp_path))
    client = app.test_client()
    response = client.get("/search-runs/..%2F..%2Fescape")

    assert response.status_code == 404
