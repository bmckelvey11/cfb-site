import math

import pytest

from cfb_system_maker.wind import WIND_FIELDS, axis_angle, cardinal8, derive, orientation_is_usable


def test_axis_angle_is_undirected():
    # A field running N-S: wind from due N and from due S are both straight up the axis.
    assert axis_angle(0.0, 0.0) == 0.0
    assert axis_angle(180.0, 0.0) == 0.0
    assert axis_angle(90.0, 0.0) == 90.0
    assert axis_angle(270.0, 0.0) == 90.0
    assert axis_angle(45.0, 0.0) == 45.0


def test_cardinal8_wraps():
    assert cardinal8(0.0) == "N"
    assert cardinal8(359.0) == "N"
    assert cardinal8(45.0) == "NE"
    assert cardinal8(315.0) == "NW"
    assert cardinal8(180.0) == "S"


def test_headwind_on_axis():
    out = derive(wind_direction_deg=180.0, wind_speed_mph=12.0, azimuth_deg=0.0)
    assert out["wind_relative"] == "Headwind"
    assert out["wind_relative_cardinal"] == "Headwind (S)"
    assert out["wind_axis_angle"] == 0.0
    assert out["wind_along_mph"] == 12.0
    assert out["wind_cross_mph"] == 0.0


def test_crosswind_across_axis():
    out = derive(wind_direction_deg=270.0, wind_speed_mph=10.0, azimuth_deg=0.0)
    assert out["wind_relative_cardinal"] == "Crosswind (W)"
    assert out["wind_axis_angle"] == 90.0
    assert out["wind_along_mph"] == 0.0
    assert out["wind_cross_mph"] == 10.0


def test_quartering_splits_the_speed():
    out = derive(wind_direction_deg=45.0, wind_speed_mph=10.0, azimuth_deg=0.0)
    assert out["wind_relative"] == "Quartering"
    assert out["wind_along_mph"] == pytest.approx(10.0 / math.sqrt(2), abs=0.01)
    assert out["wind_cross_mph"] == pytest.approx(10.0 / math.sqrt(2), abs=0.01)


def test_calm_wind_has_no_direction_class():
    out = derive(wind_direction_deg=270.0, wind_speed_mph=1.0, azimuth_deg=0.0)
    assert out["wind_relative"] == "Calm"
    assert out["wind_relative_cardinal"] == "Calm"
    assert out["wind_cross_mph"] == 1.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"wind_direction_deg": None, "wind_speed_mph": 10.0, "azimuth_deg": 0.0},
        {"wind_direction_deg": 10.0, "wind_speed_mph": None, "azimuth_deg": 0.0},
        {"wind_direction_deg": 10.0, "wind_speed_mph": 10.0, "azimuth_deg": None},
        {"wind_direction_deg": 10.0, "wind_speed_mph": 10.0, "azimuth_deg": 0.0, "indoors": True},
    ],
)
def test_missing_inputs_and_indoors_fail_closed(kwargs):
    assert derive(**kwargs) == dict.fromkeys(WIND_FIELDS)


def test_orientation_gate_rejects_bad_osm_matches():
    good = {"azimuth_deg": 90.0, "osm_sport": "american_football;soccer", "pitch_dist_m": 9.0}
    assert orientation_is_usable(good)
    assert not orientation_is_usable(None)
    assert not orientation_is_usable({**good, "azimuth_deg": None})
    assert not orientation_is_usable({**good, "osm_sport": "tennis"})
    assert not orientation_is_usable({**good, "pitch_dist_m": 300.0})
    assert not orientation_is_usable({**good, "pitch_dist_m": None})
