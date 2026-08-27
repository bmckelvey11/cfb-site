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


def test_api_backtest_rejects_bet_side_perspective_for_total_system(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    for perspective in ("bet_side", "opponent"):
        response = app.test_client().get(
            "/api/backtest?bet_type=total&total_side=over"
            "&ff_enable=running_win_pct&ff_key=running_win_pct"
            f"&ff_op=gte&ff_value=0.8&ff_perspective={perspective}"
        )
        assert response.status_code == 400
        assert response.get_json()["error"] == "invalid_perspective"

    # Spread systems still accept bet_side.
    response = app.test_client().get(
        "/api/backtest?bet_type=spread&side=home"
        "&ff_enable=running_win_pct&ff_key=running_win_pct"
        "&ff_op=gte&ff_value=0.8&ff_perspective=bet_side"
    )
    assert response.status_code == 200


def test_form_parse_normalizes_bet_side_to_either_on_totals():
    from werkzeug.datastructures import MultiDict

    from cfb_system_maker.web import _form_values_from_args, _system_from_form

    args = MultiDict([
        ("bet_type", "total"),
        ("total_side", "over"),
        ("ff_enable", "running_win_pct"),
        ("ff_key", "running_win_pct"),
        ("ff_op", "gte"),
        ("ff_value", "0.8"),
        ("ff_perspective", "bet_side"),
    ])
    system = _system_from_form(_form_values_from_args(args))
    assert system.feature_filters[0].perspective == "either"

    args_spread = MultiDict([("bet_type", "spread"), ("side", "home")] + [
        item for item in args.items(multi=True) if item[0].startswith("ff_")
    ])
    system_spread = _system_from_form(_form_values_from_args(args_spread))
    assert system_spread.feature_filters[0].perspective == "bet_side"


def test_api_backtest_missing_data_is_503(tmp_path):
    app = create_app(data_dir=tmp_path)
    response = app.test_client().get("/api/backtest?side=home")
    assert response.status_code == 503


def test_index_has_season_dialog_launcher_markup(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)
    html = app.test_client().get("/system").get_data(as_text=True)
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
    """Cancel/Escape discard path must not write canonical controls before close."""
    from pathlib import Path

    source = Path("cfb_system_maker/static/filter_modal.js").read_text(encoding="utf-8")
    assert "discardAndClose" in source
    assert "writeCoreListToForm" in source
    discard_block = source.split("function discardAndClose")[1].split("function ")[0]
    assert "writeCoreListToForm" not in discard_block
    assert "writeFeatureToForm" not in discard_block
    assert "filtersForm.submit" not in discard_block
    assert "requestSubmit" not in discard_block


def test_numeric_feature_save_clears_domain_edge_bounds_contract():
    """Full-domain feature bounds are NOT "no filter" (nulls fail closed), so
    Save must clear edge bounds like core ranges do — and the live draft query
    must drop them the same way or the preview chips diverge from the commit."""
    from pathlib import Path

    source = Path("cfb_system_maker/static/filter_modal.js").read_text(encoding="utf-8")

    write_block = source.split("function writeNumericToForm")[1].split("function ")[0]
    assert "atDomainMin" in write_block and "atDomainMax" in write_block
    assert 'atDomainMin ? ""' in write_block
    assert 'atDomainMax ? ""' in write_block
    assert "enable.checked = !(atDomainMin && atDomainMax)" in write_block

    draft_block = source.split("function draftQuery")[1].split("function ")[0]
    assert "atDomainMin" in draft_block and "atDomainMax" in draft_block
    assert "!atDomainMin || !atDomainMax" in draft_block


def test_max_roi_uses_single_bucket_when_rows_overlap_contract():
    """A window SUM across numeric buckets assumes each game contributes to at
    most one bucket. Either-perspective (and total-system team/conference)
    rows can put one game in two buckets, so Max ROI must fall back to a
    single bucket -- never a summed window -- when the server flags
    overlapping_rows, or it silently double-counts games."""
    from pathlib import Path

    source = Path("cfb_system_maker/static/filter_modal.js").read_text(encoding="utf-8")
    assert "function bestSingleNumericBucket" in source

    apply_block = source.split("function applyMaxRoi")[1].split("function ")[0]
    assert "state.overlappingRows" in apply_block
    assert "bestSingleNumericBucket(state.rows)" in apply_block
    assert "bestRoiWindow(state.rows)" in apply_block

    assert "state.overlappingRows = Boolean(payload.overlapping_rows);" in source
    # Disclosed in the About panel (not statusEl -- refreshLive's setUpdating
    # clears statusEl on every keystroke, so a transient status message here
    # would never survive to be read).
    assert "Max ROI picks the single best value" in source


def test_save_serializes_seasons_contract():
    from pathlib import Path

    source = Path("cfb_system_maker/static/filter_modal.js").read_text(encoding="utf-8")
    assert "writeCoreListToForm" in source
    assert "filter_seasons" in source
    assert "select.value = joined" in source
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


def test_aggregate_filter_value_rows_team_on_total_buckets_both_sides():
    games = [_game(1), _game(2)]  # Alpha home, Beta away in both
    descriptor = {
        "id": "core:team",
        "control": "categorical",
        "key": "team",
        "team_scoped": False,
    }
    rows = aggregate_filter_value_rows(
        games,
        SystemFilter(bet_type="total", side="home", total_side="over"),
        descriptor,
        feature_map={},
        perspective="single",
    )
    # Total systems have no bet side: every game buckets under BOTH its teams.
    assert {row["value"] for row in rows} == {"Alpha", "Beta"}
    for row in rows:
        assert row["wins"] + row["losses"] + row["pushes"] == 2

    # Spread systems keep bet-side-only buckets.
    spread_rows = aggregate_filter_value_rows(
        games, SystemFilter(side="home"), descriptor, feature_map={}, perspective="single"
    )
    assert {row["value"] for row in spread_rows} == {"Alpha"}


def test_aggregate_filter_value_rows_matched_game_ids_distinct_count():
    games = [_game(1), _game(2)]  # Alpha home, Beta away in both
    descriptor = {
        "id": "core:team",
        "control": "categorical",
        "key": "team",
        "team_scoped": False,
    }
    ids: set[int] = set()
    rows = aggregate_filter_value_rows(
        games,
        SystemFilter(bet_type="total", side="home", total_side="over"),
        descriptor,
        feature_map={},
        perspective="either",
        matched_game_ids=ids,
    )
    # 2 distinct games, even though each game is counted once per matching
    # team-value (2 rows x 2 games each = 4 total row-level bet counts).
    assert ids == {1, 2}
    assert len(ids) == 2
    assert sum(row["wins"] + row["losses"] + row["pushes"] for row in rows) == 4


def test_filter_detail_overlapping_rows_flag(tmp_path):
    games = [
        _game(1, season=2023, week=1, home_points=28, away_points=21, spread=-6.5),
        _game(2, season=2024, week=2, home_points=14, away_points=28, spread=-3.0),
    ]
    save_processed_games(tmp_path, games)
    save_features(
        tmp_path,
        {
            "1": {"home_running_win_pct": 0.5, "away_running_win_pct": 0.4},
            "2": {"home_running_win_pct": 0.6, "away_running_win_pct": 0.3},
        },
    )
    app = create_app(data_dir=tmp_path)

    # either perspective (only valid on a total system): a game's home/away
    # values can land in different rows, so a summed window would double-count it.
    either_resp = app.test_client().get(
        "/filter-detail?candidate_id=feature:running_win_pct&bet_type=total&perspective=either"
    )
    assert either_resp.status_code == 200
    assert either_resp.get_json()["overlapping_rows"] is True

    # bet_side/opponent on a spread system: no overlap, single value per game.
    bet_side_resp = app.test_client().get(
        "/filter-detail?candidate_id=feature:running_win_pct&perspective=bet_side"
    )
    assert bet_side_resp.status_code == 200
    assert bet_side_resp.get_json()["overlapping_rows"] is False

    # core:team on a total system: Alpha home / Beta away -> overlapping.
    team_resp = app.test_client().get("/filter-detail?candidate_id=core:team&bet_type=total")
    assert team_resp.status_code == 200
    team_payload = team_resp.get_json()
    assert team_payload["overlapping_rows"] is True
    # matched_games is the distinct-game denominator (2 games), which is
    # smaller than the per-value row sum (each game counted once per team).
    assert team_payload["matched_games"] == 2
    assert (
        sum(row["wins"] + row["losses"] + row["pushes"] for row in team_payload["rows"])
        > team_payload["matched_games"]
    )

    # core:team on a spread system: bet-side only, no overlap.
    team_spread_resp = app.test_client().get("/filter-detail?candidate_id=core:team&bet_type=spread")
    assert team_spread_resp.status_code == 200
    assert team_spread_resp.get_json()["overlapping_rows"] is False


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


def test_filter_detail_week_rows_sort_numerically(tmp_path):
    games = [
        _game(1, season=2023, week=1),
        _game(2, season=2023, week=2),
        _game(3, season=2023, week=10),
        _game(4, season=2023, week=11),
    ]
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/filter-detail?candidate_id=core:week&side=home")

    assert response.status_code == 200
    payload = response.get_json()
    values = [row["value"] for row in payload["rows"]]
    assert values == [1, 2, 10, 11]


def test_index_has_grouped_launchers_and_fallback(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    save_features(
        tmp_path,
        {str(game.game_id): {"neutralSite": False, "venue": "Dome"} for game in games},
    )
    html = create_app(data_dir=tmp_path).test_client().get("/system").get_data(as_text=True)
    for candidate in (
        "core:season",
        "core:week",
        "core:team",
        "core:conference",
        "core:provider",
        "core:spread_range",
        "core:total_range",
        "feature:neutralSite",
        "feature:running_win_pct",
        "feature:team_talent",
        "feature:team_state",
        "feature:attendance",
    ):
        assert f'data-candidate-id="{candidate}"' in html
    assert html.count('id="filter-modal"') == 1
    assert 'name="filter_weeks"' in html
    assert 'name="ff_enable"' in html
    assert 'data-fallback-for="core:season"' in html
    assert "lookahead — analysis only" in html
    assert 'class="feature-group lookahead"' in html or "feature-group lookahead" in html


def test_filter_modal_js_has_table_search_sort_and_commit():
    from pathlib import Path

    source = Path("cfb_system_maker/static/filter_modal.js").read_text(encoding="utf-8")
    assert "Search values" in source
    assert "aria-sort" in source
    assert "Description" in source
    assert "filter-modal__table" in source
    assert "writeCoreListToForm" in source
    assert "writeFeatureToForm" in source
    assert "filtersForm.requestSubmit" in source or "filtersForm.submit" in source
    discard_block = source.split("function discardAndClose")[1].split("function ")[0]
    assert "writeCoreListToForm" not in discard_block
    assert "writeFeatureToForm" not in discard_block
    assert "filtersForm.submit" not in discard_block
    assert "requestSubmit" not in discard_block


def test_categorical_boolean_save_commit_serialization_contract():
    """Save writes ff_*/core list into filters-form then submits; Cancel does not."""
    from pathlib import Path

    source = Path("cfb_system_maker/static/filter_modal.js").read_text(encoding="utf-8")
    assert "function saveAndSubmit" in source
    save_block = source.split("function saveAndSubmit")[1].split("function ")[0]
    assert "writeCoreListToForm" in save_block or "writeFeatureToForm" in save_block
    assert "requestSubmit" in save_block or "filtersForm.submit" in save_block
    assert 'opEl.value = "in"' in source
    assert 'opEl.value = "eq"' in source


def test_serialize_numeric_draft_core_and_feature_pairs():
    from cfb_system_maker.web import serialize_numeric_draft

    spread = serialize_numeric_draft("core:spread_range", -14.0, -3.0)
    assert spread == {"min_spread": -14.0, "max_spread": -3.0}

    total = serialize_numeric_draft("core:total_range", 40.0, 55.0)
    assert total == {"min_total": 40.0, "max_total": 55.0}

    feature = serialize_numeric_draft(
        "feature:weather_temperature", 50.0, 80.0, perspective="single"
    )
    assert feature == {
        "feature_filters": [
            {
                "key": "weather_temperature",
                "op": "gte",
                "value": 50.0,
                "perspective": "single",
            },
            {
                "key": "weather_temperature",
                "op": "lte",
                "value": 80.0,
                "perspective": "single",
            },
        ]
    }


def test_downsample_chart_points_caps_at_60_preserves_domain_extremes():
    from cfb_system_maker.web import downsample_chart_points

    rows = [
        {
            "value": float(i),
            "description": str(i),
            "wins": 1,
            "losses": 0,
            "pushes": 0,
            "record": "1-0-0",
            "roi": 0.1,
            "money": float(i) - 50,
        }
        for i in range(120)
    ]
    points = downsample_chart_points(rows, cap=60)
    assert len(points) <= 60
    assert len(points) < len(rows)
    values = [point["value"] for point in points]
    assert min(values) == 0.0
    assert max(values) == 119.0
    for point in points:
        assert "money" in point
        assert "x" in point and "y" in point


def test_filter_detail_numeric_domain_rows_and_chart_points(tmp_path):
    games = [
        _game(i, season=2023, week=i, home_points=28, away_points=21, spread=-float(i), total=40.0 + i)
        for i in range(1, 71)
    ]
    save_processed_games(tmp_path, games)
    temps = {str(i): {"weather_temperature": 30.0 + i} for i in range(1, 71)}
    save_features(tmp_path, temps)
    app = create_app(data_dir=tmp_path)
    client = app.test_client()

    feature_resp = client.get("/filter-detail?candidate_id=feature:weather_temperature&side=home")
    assert feature_resp.status_code == 200
    feature_payload = feature_resp.get_json()
    assert feature_payload["control"] == "numeric"
    assert feature_payload["domain"]["min"] == 31.0
    assert feature_payload["domain"]["max"] == 100.0
    assert len(feature_payload["rows"]) == 70
    assert len(feature_payload["chart_points"]) <= 60
    assert len(feature_payload["chart_points"]) < 70

    spread_resp = client.get("/filter-detail?candidate_id=core:spread_range&side=away")
    assert spread_resp.status_code == 200
    spread_payload = spread_resp.get_json()
    assert spread_payload["control"] == "numeric"
    # Away side: side-relative spread = -home_spread; home spreads were -1..-70 → away +1..+70
    assert spread_payload["domain"]["min"] == 1.0
    assert spread_payload["domain"]["max"] == 70.0
    assert len(spread_payload["rows"]) == 70
    assert len(spread_payload["chart_points"]) <= 60

    total_resp = client.get("/filter-detail?candidate_id=core:total_range&side=home")
    assert total_resp.status_code == 200
    total_payload = total_resp.get_json()
    assert total_payload["domain"]["min"] == 41.0
    assert total_payload["domain"]["max"] == 110.0


def test_serialize_numeric_draft_rejects_reversed_or_nonfinite():
    from cfb_system_maker.web import StrictParseError, serialize_numeric_draft

    try:
        serialize_numeric_draft("core:spread_range", -3.0, -14.0)
        assert False, "expected StrictParseError"
    except StrictParseError as exc:
        assert exc.error == "reversed_bounds"

    try:
        serialize_numeric_draft("core:total_range", float("nan"), 50.0)
        assert False, "expected StrictParseError"
    except StrictParseError as exc:
        assert exc.error == "invalid_bounds"


def test_filter_modal_js_numeric_range_chart_between_and_save():
    from pathlib import Path

    source = Path("cfb_system_maker/static/filter_modal.js").read_text(encoding="utf-8")
    assert source.count('type = "range"') >= 2
    assert "BETWEEN" in source
    assert "AND" in source
    assert 'data-view="chart"' in Path("cfb_system_maker/templates/index.html").read_text(encoding="utf-8")
    html = Path("cfb_system_maker/templates/index.html").read_text(encoding="utf-8")
    assert ">Chart<" in html and ">List<" in html
    assert 'view = "chart"' in source and 'view = "list"' in source
    assert "writeNumericToForm" in source
    assert "boundsAreValid" in source
    assert "Max must be greater than or equal to min." in source
    assert "filter-modal__chart" in source or "createElementNS" in source
    save_block = source.split("function saveAndSubmit")[1].split("function ")[0]
    assert "writeNumericToForm" in save_block
    discard_block = source.split("function discardAndClose")[1].split("function ")[0]
    assert "writeNumericToForm" not in discard_block
    assert "filtersForm.submit" not in discard_block


def test_index_has_chart_list_toggle_markup(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    html = create_app(data_dir=tmp_path).test_client().get("/system").get_data(as_text=True)
    assert 'id="filter-modal-view-toggle"' in html
    assert ">Chart<" in html
    assert ">List<" in html
    assert 'name="min_spread"' in html
    assert 'name="max_spread"' in html


def test_numeric_save_commit_serialization_contract():
    """Numeric Save writes paired/canonical bounds into filters-form; Cancel does not."""
    from pathlib import Path

    source = Path("cfb_system_maker/static/filter_modal.js").read_text(encoding="utf-8")
    assert "function writeNumericToForm" in source
    write_block = source.split("function writeNumericToForm")[1].split("function ")[0]
    assert "min_spread" in write_block or "CORE_RANGE_FIELDS" in source
    assert 'data-bound="min"' in source or "data-bound" in write_block
    assert 'op", "gte"' in source or 'op\', \'gte\'' in source or '"gte"' in write_block
    save_block = source.split("function saveAndSubmit")[1].split("function ")[0]
    assert "writeNumericToForm" in save_block
    assert "requestSubmit" in save_block or "filtersForm.submit" in save_block
    discard_block = source.split("function discardAndClose")[1].split("function ")[0]
    assert "writeNumericToForm" not in discard_block
    assert "writeCoreListToForm" not in discard_block
    assert "writeFeatureToForm" not in discard_block


def test_numeric_feature_fallback_has_paired_gte_lte_slots(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    save_features(
        tmp_path,
        {str(game.game_id): {"weather_temperature": 55.0} for game in games},
    )
    html = create_app(data_dir=tmp_path).test_client().get("/system").get_data(as_text=True)
    assert 'data-fallback-for="feature:weather_temperature"' in html
    assert 'data-bound="min"' in html
    assert 'data-bound="max"' in html
    assert 'name="ff_op" value="gte"' in html or 'value="gte"' in html
    assert 'name="ff_op" value="lte"' in html or 'value="lte"' in html


def test_default_perspective_spread_bet_side_total_either():
    from cfb_system_maker.web import default_perspective

    assert default_perspective(SystemFilter(bet_type="spread")) == "bet_side"
    assert default_perspective(SystemFilter(bet_type="total")) == "either"


def test_allowed_perspectives_excludes_bet_side_opponent_for_totals():
    from cfb_system_maker.web import _allowed_perspectives_for_system

    spread_allowed = _allowed_perspectives_for_system(SystemFilter(bet_type="spread"))
    assert "bet_side" in spread_allowed
    assert "opponent" in spread_allowed

    total_allowed = _allowed_perspectives_for_system(SystemFilter(bet_type="total"))
    assert "bet_side" not in total_allowed
    assert "opponent" not in total_allowed
    assert "either" in total_allowed


def test_filter_detail_rejects_bet_side_perspective_for_total_system(tmp_path):
    games = [
        _game(1, season=2023, week=1, home_points=28, away_points=21, spread=-6.5),
        _game(2, season=2024, week=2, home_points=14, away_points=28, spread=-3.0),
    ]
    save_processed_games(tmp_path, games)
    save_features(
        tmp_path,
        {
            "1": {"home_running_win_pct": 0.5, "away_running_win_pct": 0.4},
            "2": {"home_running_win_pct": 0.6, "away_running_win_pct": 0.3},
        },
    )
    app = create_app(data_dir=tmp_path)
    response = app.test_client().get(
        "/filter-detail?candidate_id=feature:running_win_pct&bet_type=total&perspective=bet_side"
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "invalid_perspective"


def test_edit_metadata_for_core_and_feature_sentences():
    from cfb_system_maker.web import edit_metadata_for_sentence

    seasons = edit_metadata_for_sentence(
        SystemFilter(seasons={2023, 2024}),
        {"text": "the season is 2023, 2024", "key": "seasons"},
    )
    assert seasons is not None
    assert seasons["candidate_id"] == "core:season"
    assert seasons["values"] == [2023, 2024]

    spread = edit_metadata_for_sentence(
        SystemFilter(bet_type="spread", min_spread=-14.0, max_spread=-3.0),
        {"text": "the spread is between -14 and -3", "key": "spread_range"},
    )
    assert spread is not None
    assert spread["candidate_id"] == "core:spread_range"
    assert spread["min"] == -14.0
    assert spread["max"] == -3.0

    feature = edit_metadata_for_sentence(
        SystemFilter(
            feature_filters=(
                FeatureFilter("running_win_pct", "gte", 0.4, perspective="opponent"),
                FeatureFilter("running_win_pct", "lte", 0.7, perspective="opponent"),
            )
        ),
        {"text": "Opponent Win % (to date) is between 0.4 and 0.7", "key": "ff:running_win_pct"},
    )
    assert feature is not None
    assert feature["candidate_id"] == "feature:running_win_pct"
    assert feature["perspective"] == "opponent"
    assert feature["min"] == 0.4
    assert feature["max"] == 0.7

    assert (
        edit_metadata_for_sentence(
            SystemFilter(favorite=True),
            {"text": "the team is a favorite", "key": "favorite"},
        )
        is None
    )


def test_index_active_filters_have_edit_beside_remove(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    save_features(
        tmp_path,
        {str(game.game_id): {"neutralSite": True, "running_win_pct_home": 0.5} for game in games},
    )
    app = create_app(data_dir=tmp_path)
    html = app.test_client().get(
        "/system?side=home&filter_seasons=2023"
        "&ff_enable=neutralSite&ff_key=neutralSite&ff_op=eq&ff_value=true&ff_perspective=single"
    ).get_data(as_text=True)

    assert ">Edit<" in html
    assert 'aria-label="Edit filter: the season is 2023"' in html
    assert 'data-candidate-id="core:season"' in html
    assert 'class="edit-filter"' in html
    assert 'class="remove-filter"' in html
    assert 'aria-label="Remove filter: the season is 2023"' in html
    assert 'aria-label="Edit filter:' in html
    # Feature sentence also editable
    assert "data-candidate-id=\"feature:neutralSite\"" in html
    # Global toggles are not Edit-modal filters
    fav_html = app.test_client().get("/system?side=home&favorite=on").get_data(as_text=True)
    assert "the team is a favorite" in fav_html
    assert 'aria-label="Edit filter: the team is a favorite"' not in fav_html
    assert 'aria-label="Remove filter: the team is a favorite"' in fav_html


def test_filter_modal_js_edit_prefill_and_perspective_contract():
    from pathlib import Path

    source = Path("cfb_system_maker/static/filter_modal.js").read_text(encoding="utf-8")
    assert "edit-filter" in source or "openCandidate" in source
    assert "Bet-side" in source
    assert "Opponent" in source
    assert "Either" in source
    assert "defaultPerspective" in source or "bet_side" in source
    assert "team_scoped" in source or "team-scoped" in source or "data-team-scoped" in source
    assert "perspective" in source


def test_filter_modal_js_debounce_stale_retry_and_focus_contract():
    from pathlib import Path

    source = Path("cfb_system_maker/static/filter_modal.js").read_text(encoding="utf-8")
    assert "250" in source
    assert "AbortController" in source
    assert "liveGeneration" in source or "generation" in source
    assert "Updating…" in source
    assert "Couldn’t update live stats." in source
    assert "Retry" in source
    assert "discardAndClose" in source
    # Backdrop click must not close/commit
    assert "event.target === dialog" in source
    css = Path("cfb_system_maker/static/styles.css").read_text(encoding="utf-8")
    assert "900px" in css
    assert "focus-visible" in css
    html = Path("cfb_system_maker/templates/index.html").read_text(encoding="utf-8")
    assert 'aria-labelledby="filter-modal-title"' in html
