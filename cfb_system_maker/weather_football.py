"""Client over weather.football's college forecast feed.

weather.football publishes no API, but its pages read two static JSON files that
it rebuilds hourly from the latest NBM run:

* ``/data/cfb_this_week.json`` -- one row per FBS game in the next ~11 days, with
  the kickoff-window forecast (temperature, sustained wind, gust, humidity,
  precipitation rate) and the site's Weather Football Index.
* ``/data/cfb_stadium_forecast.json`` -- hourly series per venue. Only its wind
  direction (``wdir.from_deg``, NDFD, degrees true, blowing FROM) is used here,
  because the game rows do not carry direction.

Game ``id`` and ``venue_id`` are ESPN ids, the same ids CFBD uses, so rows join
to ``GameRecord.game_id`` and ``raw/venue_orientation.json`` without name
matching.

``to_weather_rows`` emits CFBD ``/games/weather`` field names so ``enrich`` can
lay them over CFBD's rows field by field: where weather.football has a value it
wins, and CFBD keeps the fields this feed lacks (dew point, pressure, condition).
Units match CFBD's: degrees F, mph, inches of precipitation per hour.

The site states no terms of use and its robots.txt allows everything; one
upcoming refresh makes two requests. ``fetch_fn`` is injectable so tests run
network-free.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

BASE_URL = "https://weather.football/data/"
THIS_WEEK = "cfb_this_week.json"
STADIUM_FORECAST = "cfb_stadium_forecast.json"
SOURCE = "weather.football"

# Direction is hourly near term and 3- to 6-hourly further out; past this gap
# from kickoff the nearest reading says nothing about the game window.
MAX_WDIR_GAP = timedelta(hours=3)

_TIMEOUT_S = 60
_USER_AGENT = "cfb-system-maker (personal research; weather.football forecast feed)"

FetchFn = Callable[[str], Any]


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_college(fetch_fn: FetchFn | None = None) -> list[dict[str, Any]]:
    """Fetch the current college slate as CFBD-shaped weather rows."""
    fetch = fetch_fn or fetch_json
    this_week = fetch(BASE_URL + THIS_WEEK)
    stadiums = fetch(BASE_URL + STADIUM_FORECAST)
    return to_weather_rows(this_week, stadiums)


def to_weather_rows(this_week: dict[str, Any], stadiums: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    venues = (stadiums or {}).get("venues") or {}
    run = this_week.get("run")
    generated = this_week.get("generated")
    rows = []
    for game in this_week.get("games") or []:
        if game.get("id") is None:
            continue
        kickoff = _parse_utc(game.get("kickoff"))
        venue_id = game.get("venue_id")
        venue = venues.get(str(venue_id)) if venue_id is not None else None
        rows.append(
            {
                "id": int(game["id"]),
                "venueId": int(venue_id) if venue_id is not None else None,
                "startTime": game.get("kickoff"),
                "gameIndoors": bool(game.get("dome")) or game.get("roof") not in (None, "outdoors"),
                "temperature": game.get("temp_f"),
                "humidity": game.get("rh"),
                "precipitation": game.get("precip_in_hr"),
                "snowfall": game.get("snow_in_hr"),
                "windSpeed": game.get("wind_mph"),
                "windGust": game.get("gust_mph"),
                "windDirection": _wind_direction(venue, kickoff),
                "weatherSource": SOURCE,
                "wfi": game.get("wfi"),
                "wfiBand": game.get("band"),
                "rainChance": (game.get("rain_chance") or {}).get("pop"),
                "kickoffTbd": bool(game.get("tbd")),
                "forecastRun": run,
                "forecastGenerated": generated,
            }
        )
    return rows


def _wind_direction(venue: dict[str, Any] | None, kickoff: datetime | None) -> float | None:
    """Wind-from heading at the reading nearest kickoff, or None if none is close."""
    wdir = (venue or {}).get("wdir") or {}
    times, headings = wdir.get("times") or [], wdir.get("from_deg") or []
    if kickoff is None:
        return None
    best: tuple[timedelta, float] | None = None
    for raw_time, heading in zip(times, headings):
        moment = _parse_utc(raw_time)
        if moment is None or heading is None:
            continue
        gap = abs(moment - kickoff)
        if gap <= MAX_WDIR_GAP and (best is None or gap < best[0]):
            best = (gap, float(heading))
    return best[1] if best else None


def _parse_utc(raw: Any) -> datetime | None:
    """weather.football writes UTC as naive ISO strings (``2026-10-15T23:30:00``)."""
    if not raw:
        return None
    try:
        moment = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    return moment.astimezone(timezone.utc).replace(tzinfo=None) if moment.tzinfo else moment
