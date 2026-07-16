from cfb_system_maker.models import FeatureFilter, SystemFilter
from cfb_system_maker.storage import list_systems, load_system, save_system


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
