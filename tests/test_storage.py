import json
from datetime import datetime

import pytest

from cfb_system_maker.features import FEATURE_REGISTRY
from cfb_system_maker.models import GameRecord
from cfb_system_maker.storage import (
    _safe_system_name,
    list_examples,
    load_example_system,
    load_processed_games,
    load_raw_json,
    save_processed_games,
    save_raw_json,
)


def test_raw_json_round_trip(tmp_path):
    rows = [{"id": 1, "homeTeam": "A"}, {"id": 2, "homeTeam": "B"}]

    path = save_raw_json(tmp_path, "games", 2023, rows)

    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == rows
    assert load_raw_json(tmp_path, "games", 2023) == rows


def test_raw_json_serializes_api_datetimes(tmp_path):
    rows = [{"id": 1, "startDate": datetime(2023, 9, 2, 12, 0, 0)}]

    path = save_raw_json(tmp_path, "games", 2023, rows)

    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": 1, "startDate": "2023-09-02 12:00:00"}]


def test_processed_games_csv_round_trip(tmp_path):
    games = [
        GameRecord(
            game_id=1,
            season=2023,
            week=1,
            home_team="A",
            away_team="B",
            home_conference="ACC",
            away_conference="SEC",
            home_points=28,
            away_points=21,
            provider="consensus",
            spread=-6.5,
            total=49.5,
        )
    ]

    path = save_processed_games(tmp_path, games)
    loaded = load_processed_games(tmp_path)

    assert path.name == "games.csv"
    assert loaded == games


# --- Bundled example systems (Phase 5, Plan 05) -------------------------------

EXPECTED_EXAMPLE_NAMES = [
    "nonconference-away-dogs",
    "spread-home-favorites",
    "total-unders-high-lines",
]

SEASON_TO_DATE_KEYS = {
    feature.key for feature in FEATURE_REGISTRY if feature.group == "season_to_date"
}
WEATHER_KEYS = {feature.key for feature in FEATURE_REGISTRY if feature.group == "weather"}


def test_list_examples_returns_the_three_bundled_names(tmp_path):
    # Independent of any data directory: examples live in the package (D-14).
    assert list_examples() == EXPECTED_EXAMPLE_NAMES


def test_every_example_name_passes_the_safe_name_gate():
    for name in list_examples():
        assert _safe_system_name(name) == name


def test_every_example_round_trips_with_a_written_theory():
    for name in list_examples():
        saved = load_example_system(name)
        assert saved.name == name
        assert saved.theory.strip(), f"{name} has no theory (D-17)"
        assert saved.system.bet_type in {"spread", "total"}


def test_no_example_filters_on_provider_weather_or_season_to_date():
    # D-21: these would guarantee zero matches on upcoming games. Written as a
    # loop so a fourth example added later cannot quietly violate it.
    for name in list_examples():
        system = load_example_system(name).system
        assert not system.providers, f"{name} declares a provider filter"
        for filt in system.feature_filters:
            assert filt.key not in WEATHER_KEYS, f"{name} filters on weather {filt.key}"
            assert filt.key not in SEASON_TO_DATE_KEYS, (
                f"{name} filters on season-to-date {filt.key}"
            )


def test_at_least_one_example_exercises_a_registry_feature():
    # D-16: one example per capability — spread, total, and a registry feature.
    kinds = {load_example_system(name).system.bet_type for name in list_examples()}
    assert {"spread", "total"} <= kinds
    assert any(load_example_system(name).system.feature_filters for name in list_examples())


def test_load_example_system_rejects_path_traversal_name():
    with pytest.raises(ValueError):
        load_example_system("../../outside_secret")


def test_load_example_system_reads_from_an_override_directory(tmp_path):
    (tmp_path / "custom-example.json").write_text(
        json.dumps({"name": "custom-example", "theory": "why", "system": {"bet_type": "total"}}),
        encoding="utf-8",
    )

    assert list_examples(tmp_path) == ["custom-example"]
    assert load_example_system("custom-example", tmp_path).theory == "why"


def test_save_and_load_search_run_round_trips(tmp_path):
    from cfb_system_maker.models import SearchRun, SearchRunFinalist, SystemFilter
    from cfb_system_maker.storage import save_search_run, load_search_run, list_search_runs

    finalist = SearchRunFinalist(
        system=SystemFilter(bet_type="spread", side="home", favorite=True),
        wins=12,
        losses=8,
        pushes=1,
        roi=0.0524,
        raw_p=0.031,
        corrected_p=0.062,
        bh_significant=False,
    )
    run = SearchRun(
        name="my-run",
        saved_at="2026-07-31T00:00:00+00:00",
        candidates_tested=482,
        finalists_graded=1,
        effective_params={"beam_width": 100, "top_k": 20, "min_decided_bets": 100, "alpha": 0.05},
        finalists=(finalist,),
    )

    save_search_run("my-run", run, tmp_path)
    loaded = load_search_run("my-run", tmp_path)

    assert loaded.name == "my-run"
    assert loaded.candidates_tested == 482
    assert loaded.finalists_graded == 1
    assert loaded.effective_params["beam_width"] == 100
    assert len(loaded.finalists) == 1
    assert loaded.finalists[0].wins == 12
    assert loaded.finalists[0].corrected_p == 0.062
    assert loaded.finalists[0].system.bet_type == "spread"
    assert loaded.finalists[0].system.favorite is True
    assert list_search_runs(tmp_path) == ["my-run"]


def test_system_from_non_dict_payload_raises_value_error(tmp_path):
    from cfb_system_maker.storage import load_saved_system

    systems_dir = tmp_path / "systems"
    systems_dir.mkdir()
    (systems_dir / "weird.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError):
        load_saved_system("weird", tmp_path)


def test_load_search_run_missing_file_raises(tmp_path):
    from cfb_system_maker.storage import load_search_run

    with pytest.raises(FileNotFoundError):
        load_search_run("nope", tmp_path)


def test_save_search_run_rejects_unsafe_name(tmp_path):
    from cfb_system_maker.models import SearchRun
    from cfb_system_maker.storage import save_search_run

    run = SearchRun(
        name="x", saved_at="2026-07-31T00:00:00+00:00", candidates_tested=1,
        finalists_graded=0, effective_params={}, finalists=(),
    )
    with pytest.raises(ValueError):
        save_search_run("../escape", run, tmp_path)
