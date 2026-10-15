"""weather.football feed parsing and its overlay on the upcoming week.

The fixture is a two-game cut of the live feed fetched 2026-10-15: Georgia
Southern at Old Dominion (outdoors) and Louisville at Syracuse (dome).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cfb_system_maker.enrich import load_features_from, upcoming_features_path
from cfb_system_maker.upcoming import build_upcoming, load_weather_override
from cfb_system_maker.weather_football import BASE_URL, fetch_college, to_weather_rows
from tests.test_upcoming import default_data, make_module

FIXTURES = Path(__file__).parent / "fixtures" / "weather_football"
NOW = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _rows_by_id():
    rows = to_weather_rows(_fixture("cfb_this_week.json"), _fixture("cfb_stadium_forecast.json"))
    return {row["id"]: row for row in rows}


def test_rows_use_cfbd_weather_field_names_and_espn_ids():
    odu = _rows_by_id()[401869950]

    assert odu["venueId"] == 3918
    assert odu["gameIndoors"] is False
    assert odu["temperature"] == 68.4
    assert odu["windSpeed"] == 8.0
    assert odu["windGust"] == 12.8
    assert odu["humidity"] == 92.0
    assert odu["precipitation"] == 0.0
    assert odu["wfi"] == 7
    assert odu["rainChance"] == 4
    assert odu["weatherSource"] == "weather.football"


def test_wind_direction_is_the_reading_nearest_kickoff():
    stadiums = _fixture("cfb_stadium_forecast.json")
    wdir = stadiums["venues"]["3918"]["wdir"]
    # Kickoff 23:30 UTC sits between the 23:00 and 00:00 readings; 23:00 comes first and ties win.
    expected = wdir["from_deg"][wdir["times"].index("2026-10-15T23:00:00")]

    assert _rows_by_id()[401869950]["windDirection"] == expected


def test_wind_direction_is_null_when_no_reading_is_near_kickoff():
    this_week = _fixture("cfb_this_week.json")
    stadiums = {"venues": {"3918": {"wdir": {"times": ["2026-10-14T00:00:00"], "from_deg": [90]}}}}

    rows = {row["id"]: row for row in to_weather_rows(this_week, stadiums)}

    assert rows[401869950]["windDirection"] is None


def test_dome_games_are_indoors():
    assert _rows_by_id()[401858265]["gameIndoors"] is True


def test_fetch_college_reads_both_feed_files():
    urls = []

    def fake_fetch(url):
        urls.append(url)
        return _fixture(url.removeprefix(BASE_URL))

    rows = fetch_college(fake_fetch)

    assert urls == [BASE_URL + "cfb_this_week.json", BASE_URL + "cfb_stadium_forecast.json"]
    assert {row["id"] for row in rows} == {401869950, 401858265}


def _weather_row(game_id, generated=NOW, **fields):
    return {"id": game_id, "forecastGenerated": generated.isoformat(), "weatherSource": "weather.football", **fields}


def test_upcoming_lays_weather_football_over_cfbd(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    # CFBD's row has a dew point the forecast feed lacks; it must survive the overlay.
    cfbd_row = {"id": 2001, "temperature": 50.0, "windSpeed": 20.0, "dewPoint": 41.0}
    (raw / "weather_2026.json").write_text(json.dumps([cfbd_row]), encoding="utf-8")
    module, _ = make_module(*default_data())

    result = build_upcoming(
        tmp_path,
        now=NOW,
        cfbd_module=module,
        token="t",
        weather_fetch=lambda: [_weather_row(2001, temperature=72.5, windSpeed=6.0, windGust=None)],
    )

    features = load_features_from(upcoming_features_path(tmp_path))
    assert features[2001]["weather_temperature"] == 72.5
    assert features[2001]["weather_windSpeed"] == 6.0
    assert features[2001]["weather_dewPoint"] == 41.0
    assert result.meta["weather_football"] == {"status": "ok", "games": 1}


def test_upcoming_builds_on_cfbd_weather_when_the_fetch_fails(tmp_path):
    module, _ = make_module(*default_data())

    def broken():
        raise OSError("proxy refused")

    result = build_upcoming(tmp_path, now=NOW, cfbd_module=module, token="t", weather_fetch=broken)

    assert result.meta["row_count"] > 0
    assert result.meta["weather_football"] == {"status": "failed: OSError", "games": 0}


def test_a_stale_snapshot_is_ignored(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    old = NOW - timedelta(hours=40)
    (raw / "weather_football_2026.json").write_text(json.dumps([_weather_row(2001, generated=old)]), encoding="utf-8")

    assert load_weather_override(tmp_path, 2026, NOW) == {}
    assert 2001 in load_weather_override(tmp_path, 2026, old + timedelta(hours=1))
