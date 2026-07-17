import json

from cfb_system_maker.models import FeatureFilter, SystemFilter
from cfb_system_maker.storage import list_systems, load_saved_system, load_system, save_system


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
