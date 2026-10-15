import json

import pytest

from cfb_system_maker.models import FeatureFilter, SystemFilter
from cfb_system_maker.storage import (
    duplicate_name,
    duplicate_system,
    list_systems,
    load_saved_system,
    load_system,
    rename_system,
    save_system,
)


def test_save_load_list_system_round_trip(tmp_path):
    system = SystemFilter(
        side="away",
        underdog=True,
        min_spread=3,
        feature_filters=(
            FeatureFilter(key="weather_temperature", op="gte", value=40.0, perspective="single"),
            FeatureFilter(key="returning_ppa", op="gte", value=0.5, perspective="bet_side"),
        ),
    )
    save_system("home-dogs", system, tmp_path)
    assert list_systems(tmp_path) == ["home-dogs"]

    loaded = load_system("home-dogs", tmp_path)
    assert loaded.side == "away"
    assert loaded.underdog is True
    assert loaded.min_spread == 3
    assert len(loaded.feature_filters) == 2
    assert loaded.feature_filters[0].key == "weather_temperature"
    assert loaded.feature_filters[1].perspective == "bet_side"


def test_save_load_system_round_trips_theory(tmp_path):
    save_system("with-theory", SystemFilter(side="away"), tmp_path, theory="Fade elite teams late season.")

    loaded = load_saved_system("with-theory", tmp_path)
    assert loaded.theory == "Fade elite teams late season."


def test_save_system_defaults_theory_to_empty_string(tmp_path):
    save_system("no-theory", SystemFilter(), tmp_path)

    loaded = load_saved_system("no-theory", tmp_path)
    assert loaded.theory == ""


def test_load_saved_system_backward_compatible_with_missing_theory_key(tmp_path):
    systems_dir = tmp_path / "systems"
    systems_dir.mkdir(parents=True)
    payload = {
        "name": "legacy",
        "saved_at": "2020-01-01T00:00:00+00:00",
        "system": {
            "bet_type": "spread",
            "side": "home",
            "total_side": "over",
            "seasons": [],
            "weeks": [],
            "teams": [],
            "conferences": [],
            "favorite": False,
            "underdog": False,
            "home": False,
            "away": False,
            "providers": [],
            "min_spread": None,
            "max_spread": None,
            "min_total": None,
            "max_total": None,
            "feature_filters": [],
        },
    }
    (systems_dir / "legacy.json").write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_saved_system("legacy", tmp_path)
    assert loaded.theory == ""


def test_save_load_system_round_trips_fade(tmp_path):
    save_system("faded", SystemFilter(side="home", fade=True), tmp_path)

    loaded = load_saved_system("faded", tmp_path)
    assert loaded.system.fade is True


def test_save_system_rejects_path_traversal_name(tmp_path):
    with pytest.raises(ValueError):
        save_system("../../outside_secret", SystemFilter(), tmp_path)
    assert not (tmp_path.parent.parent / "outside_secret.json").exists()


def test_load_system_rejects_path_traversal_name(tmp_path):
    with pytest.raises(ValueError):
        load_system("../../outside_secret", tmp_path)


def test_load_saved_system_rejects_path_traversal_name(tmp_path):
    with pytest.raises(ValueError):
        load_saved_system("../../outside_secret", tmp_path)


def test_load_saved_system_backward_compatible_with_missing_fade_key(tmp_path):
    systems_dir = tmp_path / "systems"
    systems_dir.mkdir(parents=True)
    payload = {
        "name": "legacy",
        "saved_at": "2020-01-01T00:00:00+00:00",
        "system": {
            "bet_type": "spread",
            "side": "home",
            "total_side": "over",
            "seasons": [],
            "weeks": [],
            "teams": [],
            "conferences": [],
            "favorite": False,
            "underdog": False,
            "home": False,
            "away": False,
            "providers": [],
            "min_spread": None,
            "max_spread": None,
            "min_total": None,
            "max_total": None,
            "feature_filters": [],
        },
    }
    (systems_dir / "legacy.json").write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_saved_system("legacy", tmp_path)
    assert loaded.system.fade is False


# --- P1-001: provenance schema (source, search_candidates_tested) ------------------


def test_load_saved_system_backward_compatible_with_missing_provenance_keys(tmp_path):
    systems_dir = tmp_path / "systems"
    systems_dir.mkdir(parents=True)
    payload = {
        "name": "legacy",
        "saved_at": "2020-01-01T00:00:00+00:00",
        "system": {
            "bet_type": "spread",
            "side": "home",
            "total_side": "over",
            "seasons": [],
            "weeks": [],
            "teams": [],
            "conferences": [],
            "favorite": False,
            "underdog": False,
            "home": False,
            "away": False,
            "providers": [],
            "min_spread": None,
            "max_spread": None,
            "min_total": None,
            "max_total": None,
            "feature_filters": [],
        },
    }
    (systems_dir / "legacy.json").write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_saved_system("legacy", tmp_path)
    assert loaded.source == "manual"
    assert loaded.search_candidates_tested is None


def test_save_load_system_round_trips_search_provenance(tmp_path):
    save_system(
        "found-by-search",
        SystemFilter(side="home", favorite=True),
        tmp_path,
        source="search",
        search_candidates_tested=1234,
    )

    loaded = load_saved_system("found-by-search", tmp_path)
    assert loaded.source == "search"
    assert loaded.search_candidates_tested == 1234


def test_save_system_manual_flow_unaffected_by_new_provenance_kwargs(tmp_path):
    # Existing callers (CLI backtest --save, web /system save flow) call save_system
    # without the new kwargs at all -- must keep producing manual systems.
    save_system("plain-manual", SystemFilter(side="home"), tmp_path)

    loaded = load_saved_system("plain-manual", tmp_path)
    assert loaded.source == "manual"
    assert loaded.search_candidates_tested is None


def test_duplicate_name_skips_taken_copies_and_does_not_stack_suffixes():
    assert duplicate_name("dogs", ["dogs"]) == "dogs-copy"
    assert duplicate_name("dogs", ["dogs", "dogs-copy"]) == "dogs-copy-2"
    assert duplicate_name("dogs-copy", ["dogs", "dogs-copy"]) == "dogs-copy-2"
    assert duplicate_name("dogs-copy-2", ["dogs", "dogs-copy", "dogs-copy-2"]) == "dogs-copy-3"


def test_duplicate_system_keeps_filters_and_theory(tmp_path):
    save_system("dogs", SystemFilter(side="away", underdog=True), tmp_path, theory="Road dogs.")

    new_name = duplicate_system("dogs", tmp_path)

    assert new_name == "dogs-copy"
    assert list_systems(tmp_path) == ["dogs", "dogs-copy"]
    copy = load_saved_system("dogs-copy", tmp_path)
    assert copy.name == "dogs-copy"
    assert copy.system == load_system("dogs", tmp_path)
    assert copy.theory == "Road dogs."


def test_duplicate_system_rejects_missing_and_unsafe_names(tmp_path):
    with pytest.raises(FileNotFoundError):
        duplicate_system("nope", tmp_path)
    with pytest.raises(ValueError):
        duplicate_system("../escape", tmp_path)


def test_rename_system_refuses_to_overwrite(tmp_path):
    save_system("keeper", SystemFilter(side="home"), tmp_path)
    save_system("other", SystemFilter(side="away"), tmp_path)

    with pytest.raises(FileExistsError):
        rename_system("other", "keeper", tmp_path)

    assert load_system("keeper", tmp_path).side == "home"
    assert load_system("other", tmp_path).side == "away"


def test_rename_system_rejects_unsafe_source_name(tmp_path):
    with pytest.raises(ValueError):
        rename_system("../escape", "fine", tmp_path)
