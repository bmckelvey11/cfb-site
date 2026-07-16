from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

Group = Literal["pregame", "season_to_date", "team_preseason", "metadata", "result_lookahead"]
Control = Literal["bool", "categorical", "numeric"]
Join = Literal["game_id", "team_season", "team_name", "conference_name"]
SourceKind = Literal[
    "raw_game",
    "raw_lines",
    "raw_weather",
    "raw_media",
    "raw_team_season",
    "raw_teams",
    "raw_coaches",
    "raw_havoc",
    "computed_running",
    "graphql_game",
    "graphql_weather",
    "graphql_lines",
    "graphql_game_team",
]


@dataclass(frozen=True)
class FeatureDef:
    key: str
    label: str
    group: Group
    source_kind: SourceKind
    field: str
    join: Join
    control: Control
    team_scoped: bool = False
    lines_field: str | None = None  # nested under lines[0] for raw_lines
    source_file: str | None = None  # raw/json basename without season suffix


FEATURE_REGISTRY: tuple[FeatureDef, ...] = (
    # --- pregame (game_id) ---
    FeatureDef("neutralSite", "Neutral Site", "pregame", "raw_game", "neutralSite", "game_id", "bool"),
    FeatureDef("conferenceGame", "Conference Game", "pregame", "raw_game", "conferenceGame", "game_id", "bool"),
    FeatureDef("venue", "Venue", "pregame", "raw_game", "venue", "game_id", "categorical"),
    FeatureDef("seasonType", "Season Type", "pregame", "raw_game", "seasonType", "game_id", "categorical"),
    FeatureDef("homePregameElo", "Home Pregame Elo", "pregame", "raw_game", "homePregameElo", "game_id", "numeric"),
    FeatureDef("awayPregameElo", "Away Pregame Elo", "pregame", "raw_game", "awayPregameElo", "game_id", "numeric"),
    FeatureDef(
        "pregame_win_prob",
        "Pregame Win Prob",
        "pregame",
        "graphql_game_team",
        "winProb",
        "game_id",
        "numeric",
        team_scoped=True,
    ),
    FeatureDef("spreadOpen", "Spread Open", "pregame", "raw_lines", "spreadOpen", "game_id", "numeric", lines_field="spreadOpen"),
    FeatureDef("overUnderOpen", "Over/Under Open", "pregame", "raw_lines", "overUnderOpen", "game_id", "numeric", lines_field="overUnderOpen"),
    FeatureDef("moneylineHome", "Home Moneyline", "pregame", "raw_lines", "homeMoneyline", "game_id", "numeric", lines_field="homeMoneyline"),
    FeatureDef("moneylineAway", "Away Moneyline", "pregame", "raw_lines", "awayMoneyline", "game_id", "numeric", lines_field="awayMoneyline"),
    FeatureDef("weather_temperature", "Temperature (F)", "pregame", "raw_weather", "temperature", "game_id", "numeric"),
    FeatureDef("weather_windSpeed", "Wind Speed", "pregame", "raw_weather", "windSpeed", "game_id", "numeric"),
    FeatureDef("weather_precipitation", "Precipitation", "pregame", "raw_weather", "precipitation", "game_id", "numeric"),
    FeatureDef("weather_humidity", "Humidity", "pregame", "raw_weather", "humidity", "game_id", "numeric"),
    FeatureDef("weather_dewPoint", "Dew Point", "pregame", "raw_weather", "dewPoint", "game_id", "numeric"),
    FeatureDef("weather_pressure", "Pressure", "pregame", "raw_weather", "pressure", "game_id", "numeric"),
    FeatureDef("weather_snowfall", "Snowfall", "pregame", "raw_weather", "snowfall", "game_id", "numeric"),
    FeatureDef("gameIndoors", "Game Indoors", "pregame", "raw_weather", "gameIndoors", "game_id", "bool"),
    FeatureDef("weather_condition", "Weather Condition", "pregame", "raw_weather", "weatherCondition", "game_id", "categorical"),
    FeatureDef("media_outlet", "TV Network", "pregame", "raw_media", "outlet", "game_id", "categorical"),
    # --- team preseason ---
    FeatureDef(
        "returning_ppa",
        "Returning PPA %",
        "team_preseason",
        "raw_team_season",
        "percentPPA",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="returning_production",
    ),
    FeatureDef(
        "returning_usage",
        "Returning Usage",
        "team_preseason",
        "raw_team_season",
        "usage",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="returning_production",
    ),
    FeatureDef(
        "team_talent",
        "Team Talent",
        "team_preseason",
        "raw_team_season",
        "talent",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="talent",
    ),
    FeatureDef(
        "recruiting_rank",
        "Recruiting Rank",
        "team_preseason",
        "raw_team_season",
        "rank",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="recruiting_teams",
    ),
    FeatureDef(
        "recruiting_points",
        "Recruiting Points",
        "team_preseason",
        "raw_team_season",
        "points",
        "team_season",
        "numeric",
        team_scoped=True,
        source_file="recruiting_teams",
    ),
    # --- metadata ---
    FeatureDef("team_state", "Team State", "metadata", "raw_teams", "location.state", "team_name", "categorical", team_scoped=True),
    FeatureDef("team_timezone", "Team Timezone", "metadata", "raw_teams", "location.timezone", "team_name", "categorical", team_scoped=True),
    FeatureDef("team_capacity", "Stadium Capacity", "metadata", "raw_teams", "location.capacity", "team_name", "numeric", team_scoped=True),
    FeatureDef("team_conference", "Team Conference", "metadata", "raw_teams", "conference", "team_name", "categorical", team_scoped=True),
    FeatureDef("coach_name", "Head Coach", "metadata", "raw_coaches", "coach_name", "team_season", "categorical", team_scoped=True),
    FeatureDef("coach_hire_date", "Coach Hire Date", "metadata", "raw_coaches", "hireDate", "team_season", "categorical", team_scoped=True),
    # --- season to date (computed, as-of-game) ---
    FeatureDef("running_games_played", "Games Played (to date)", "season_to_date", "computed_running", "games_played", "game_id", "numeric", team_scoped=True),
    FeatureDef("running_win_pct", "Win % (to date)", "season_to_date", "computed_running", "win_pct", "game_id", "numeric", team_scoped=True),
    FeatureDef("running_ats_pct", "ATS Win % (to date)", "season_to_date", "computed_running", "ats_pct", "game_id", "numeric", team_scoped=True),
    FeatureDef("running_ppa_off", "Off PPA (to date)", "season_to_date", "computed_running", "ppa_off", "game_id", "numeric", team_scoped=True),
    FeatureDef("running_ppa_def", "Def PPA (to date)", "season_to_date", "computed_running", "ppa_def", "game_id", "numeric", team_scoped=True),
    # --- result lookahead ---
    FeatureDef(
        "havoc_offense_rate",
        "Offense Havoc Rate",
        "result_lookahead",
        "raw_havoc",
        "offense.havocRate",
        "game_id",
        "numeric",
        team_scoped=True,
    ),
    FeatureDef(
        "havoc_defense_rate",
        "Defense Havoc Rate",
        "result_lookahead",
        "raw_havoc",
        "defense.havocRate",
        "game_id",
        "numeric",
        team_scoped=True,
    ),
    FeatureDef("attendance", "Attendance", "result_lookahead", "raw_game", "attendance", "game_id", "numeric"),
)

FEATURE_BY_KEY: dict[str, FeatureDef] = {feature.key: feature for feature in FEATURE_REGISTRY}


def registry_keys_unique() -> bool:
    return len(FEATURE_BY_KEY) == len(FEATURE_REGISTRY)


def registry_version() -> str:
    digest = hashlib.sha256(",".join(sorted(FEATURE_BY_KEY)).encode("utf-8")).hexdigest()
    return digest[:12]


def get_nested(row: dict[str, Any], path: str) -> Any:
    current: Any = row
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def resolve_storage_key(feature: FeatureDef, perspective: str) -> str:
    if not feature.team_scoped or perspective in {"single", ""}:
        return feature.key
    if perspective in {"home", "away", "bet_side", "opponent", "either"}:
        side = "home" if perspective in {"home", "bet_side"} else "away"
        if perspective == "opponent":
            side = "away"
        if perspective == "either":
            return f"either_{feature.key}"
        return f"{side}_{feature.key}"
    return feature.key


def resolve_feature_value(
    features: dict[str, Any],
    feature: FeatureDef,
    filt: FeatureFilterLike,
    system: SystemFilterLike,
) -> Any:
    perspective = filt.perspective or "single"
    if not feature.team_scoped or perspective in {"single", ""}:
        return features.get(feature.key)

    if perspective == "either":
        home_val = features.get(f"home_{feature.key}")
        away_val = features.get(f"away_{feature.key}")
        return (home_val, away_val)

    side = _perspective_to_side(perspective, system)
    return features.get(f"{side}_{feature.key}")


def _perspective_to_side(perspective: str, system: SystemFilterLike) -> str:
    if perspective == "home":
        return "home"
    if perspective == "away":
        return "away"
    if perspective == "bet_side":
        return system.side.lower()
    if perspective == "opponent":
        return "away" if system.side.lower() == "home" else "home"
    return "home"


class FeatureFilterLike:
    key: str
    perspective: str
    op: str
    value: object


class SystemFilterLike:
    side: str
    bet_type: str


def feature_ok(
    features: dict[str, Any],
    filt: FeatureFilterLike,
    system: SystemFilterLike,
) -> bool:
    feature = FEATURE_BY_KEY.get(filt.key)
    if feature is None:
        return False

    value = resolve_feature_value(features, feature, filt, system)
    if value is None:
        return False

    if filt.perspective == "either" and isinstance(value, tuple):
        home_val, away_val = value
        return any(
            candidate is not None and _value_matches(filt.op, filt.value, candidate)
            for candidate in (home_val, away_val)
        )

    return _value_matches(filt.op, filt.value, value)


def _value_matches(op: str, expected: object, actual: Any) -> bool:
    if op == "eq":
        return actual == expected
    if op == "in":
        return actual in expected  # type: ignore[operator]
    if op == "gte":
        return float(actual) >= float(expected)  # type: ignore[arg-type]
    if op == "lte":
        return float(actual) <= float(expected)  # type: ignore[arg-type]
    raise ValueError(f"unsupported op: {op}")
