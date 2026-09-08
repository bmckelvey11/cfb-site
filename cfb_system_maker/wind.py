"""Wind direction relative to the field's long axis.

Combines pregame ``windDirection``/``windSpeed`` with the venue's field azimuth
(``data/raw/venue_orientation.json``, an OpenStreetMap pitch match) to say whether
the wind runs goalpost-to-goalpost or sideline-to-sideline.

Conventions:

* ``wind_direction_deg`` is meteorological -- the compass heading the wind blows
  *from* (CFBD's upstream weather provider, matching near-universal API practice).
* ``azimuth_deg`` is the undirected field axis in [0, 180]. A football field is
  symmetric and teams swap ends each quarter, so an along-axis wind is a headwind
  for one direction of play and a tailwind for the other. "Headwind" below names
  that axis, not a specific offense.
"""

from __future__ import annotations

import math
from typing import Any

# Only trust an orientation matched to an actual football pitch close to the venue
# coordinates. OSM matches to a basketball court or baseball diamond a few hundred
# metres away carry a real azimuth for the wrong polygon.
MAX_PITCH_DIST_M = 50.0
CALM_MPH = 3.0
HEADWIND_MAX_ANGLE = 30.0
CROSSWIND_MIN_ANGLE = 60.0

_CARDINALS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

WIND_FIELDS = (
    "wind_axis_angle",
    "wind_along_mph",
    "wind_cross_mph",
    "wind_relative",
    "wind_relative_cardinal",
)


def orientation_is_usable(record: dict[str, Any] | None) -> bool:
    """True when the OSM match is a football pitch at the venue's coordinates."""
    if not record:
        return False
    azimuth = record.get("azimuth_deg")
    if azimuth is None:
        return False
    sport = (record.get("osm_sport") or "").lower()
    if "american_football" not in sport:
        return False
    dist = record.get("pitch_dist_m")
    return dist is not None and float(dist) < MAX_PITCH_DIST_M


def cardinal8(direction_deg: float) -> str:
    """Compass point the wind blows from, to the nearest eighth."""
    return _CARDINALS[int(((direction_deg % 360) + 22.5) // 45) % 8]


def axis_angle(direction_deg: float, azimuth_deg: float) -> float:
    """Angle between the wind line and the field axis, in [0, 90].

    0 means the wind runs straight up the field; 90 means straight across it.
    """
    delta = (direction_deg - azimuth_deg) % 180.0
    return min(delta, 180.0 - delta)


def derive(
    *,
    wind_direction_deg: float | None,
    wind_speed_mph: float | None,
    azimuth_deg: float | None,
    indoors: bool = False,
) -> dict[str, Any]:
    """Wind-vs-field fields for one game. All None when it cannot be computed."""
    blank: dict[str, Any] = dict.fromkeys(WIND_FIELDS)
    if indoors or wind_direction_deg is None or wind_speed_mph is None or azimuth_deg is None:
        return blank

    speed = float(wind_speed_mph)
    angle = axis_angle(float(wind_direction_deg), float(azimuth_deg))
    radians = math.radians(angle)
    result: dict[str, Any] = {
        "wind_axis_angle": round(angle, 1),
        "wind_along_mph": round(speed * math.cos(radians), 2),
        "wind_cross_mph": round(speed * math.sin(radians), 2),
    }

    if speed < CALM_MPH:
        result["wind_relative"] = "Calm"
        result["wind_relative_cardinal"] = "Calm"
        return result

    if angle <= HEADWIND_MAX_ANGLE:
        relative = "Headwind"
    elif angle >= CROSSWIND_MIN_ANGLE:
        relative = "Crosswind"
    else:
        relative = "Quartering"
    result["wind_relative"] = relative
    result["wind_relative_cardinal"] = f"{relative} ({cardinal8(float(wind_direction_deg))})"
    return result
