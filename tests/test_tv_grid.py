import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "tv_grid", Path(__file__).resolve().parents[1] / "scripts" / "tv_grid.py")
tv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tv)


def test_normalize_network_maps_cfbd_outlets_to_row_labels():
    assert tv.normalize_network("SEC Network") == "SECN"
    assert tv.normalize_network("USA Net") == "USA"
    assert tv.normalize_network("The CW Network") == "CW"
    assert tv.normalize_network("ESPN2") == "ESPN2"


def test_row_order_is_broadcast_then_espn_then_cable_then_unknown_then_streaming():
    labels = {"STREAMING", "BTN", "ESPN", "NBC", "ABC", "MNMT", "ESPNU", "KMCI-TV"}
    assert tv.row_order(labels) == ["ABC", "NBC", "ESPN", "ESPNU", "BTN", "KMCI-TV", "MNMT", "STREAMING"]


def test_pick_network_prefers_tv_row_and_keeps_streamer_as_badge():
    assert tv.pick_network([("NBC", "tv"), ("Peacock", "web")]) == ("NBC", ["Peacock"])
    assert tv.pick_network([("ESPN+", "web")]) == ("STREAMING", ["ESPN+"])
    assert tv.pick_network([("The CW Network", "tv"), ("CW", "tv")]) == ("CW", [])
    assert tv.pick_network([]) == ("STREAMING", [])


def test_format_matchup_puts_spread_on_favourite_only():
    # CFBD home spread: +24.5 means the away side is favoured by 24.5.
    assert tv.format_matchup(24.5) == {"away": "-24.5", "home": ""}
    assert tv.format_matchup(-3.5) == {"away": "", "home": "-3.5"}
    assert tv.format_matchup(0) == {"away": "", "home": "PK"}
    assert tv.format_matchup(None) == {"away": "", "home": ""}


def test_total_text_goes_in_the_footer():
    assert tv.total_text(54.5) == "O/U 54.5"
    assert tv.total_text(50.0) == "O/U 50"
    assert tv.total_text(None) == ""


def test_rank_label_ap_then_massey_and_fcs_poll():
    assert tv.rank_label(7, 5, "fbs", None) == "#7 · M5"
    assert tv.rank_label(None, 41, "fbs", None) == "M41"
    assert tv.rank_label(None, None, "fbs", None) == ""
    assert tv.rank_label(None, None, "fcs", 6) == "FCS #6"
    assert tv.rank_label(None, None, "fcs", None) == ""


def test_pack_rows_stacks_only_overlapping_cards():
    # two 12:00 games overlap; a 4:00 game reuses row 0 after the first ends.
    assert tv.pack_rows([(0, 14), (0, 14), (16, 30)]) == [0, 1, 0]
    assert tv.pack_rows([(16, 30), (0, 14)]) == [0, 0]


def test_wind_arrow_points_where_the_wind_blows_to():
    assert tv.wind_arrow_deg(180) == 0      # from the south -> arrow points north (up)
    assert tv.wind_arrow_deg(270) == 90     # from the west -> points east (right)


def test_weather_text_formats_forecast_and_dome():
    w = {"temperature": 76.6, "precipitation": 0.15, "windSpeed": 6.2, "windDirection": 180}
    text = tv.weather_text(w, azimuth=90.0, indoors=False)
    assert text.startswith('77°F · 0.15" · S 6 mph ')
    assert "rotate(0deg)" in text and text.endswith("· Crosswind")
    assert tv.weather_text(w, azimuth=None, indoors=False).endswith("</span>")
    assert tv.weather_text(w, azimuth=None, indoors=True) == "DOME"
    assert tv.weather_text(None, None, False) == ""
