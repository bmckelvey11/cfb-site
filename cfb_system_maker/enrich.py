from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from cfb_system_maker.coach_style import COACH_STYLE_CLUSTERS
from cfb_system_maker.features import FEATURE_REGISTRY, FeatureDef, get_nested, registry_version
from cfb_system_maker.models import GameRecord
from cfb_system_maker.normalize import _first, _select_line, _select_total
from cfb_system_maker.running_stats import compute_running_stats
from cfb_system_maker.storage import load_processed_games
from cfb_system_maker.v1_model import load_v1_fit, score_v1
from cfb_system_maker.wind import derive as derive_wind
from cfb_system_maker.wind import orientation_is_usable


def enrich_games(data_dir: str | Path, games: list[GameRecord] | None = None) -> dict[str, dict[str, Any]]:
    data_dir = Path(data_dir)
    games = games or load_processed_games(data_dir)
    indexes = _build_indexes(data_dir, games)

    output: dict[str, dict[str, Any]] = {}
    for game in games:
        row: dict[str, Any] = {}
        for feature in FEATURE_REGISTRY:
            _apply_feature(row, feature, game, indexes)
        output[str(game.game_id)] = row
    return output


def save_features(data_dir: str | Path, features: dict[str, dict[str, Any]]) -> Path:
    return save_features_to(_features_path(data_dir), features)


def save_features_to(path: str | Path, features: dict[str, dict[str, Any]]) -> Path:
    """Write a features sidecar to an explicit path.

    The upcoming-games path needs its own file; reusing ``save_features``' fixed
    path would silently clobber the historical sidecar.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"_meta": _build_meta(features), "games": features}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _build_meta(features: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "registry_version": registry_version(),
        "game_count": len(features),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def load_features(data_dir: str | Path) -> dict[int, dict[str, Any]]:
    return load_features_from(_features_path(data_dir))


def load_features_from(path: str | Path) -> dict[int, dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = raw["games"] if "_meta" in raw and "games" in raw else raw
    return {int(game_id): values for game_id, values in rows.items()}


def load_features_meta(data_dir: str | Path) -> dict[str, Any] | None:
    path = _features_path(data_dir)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    meta = raw.get("_meta") if isinstance(raw, dict) else None
    return meta if isinstance(meta, dict) else None


def _features_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / "processed" / "features.json"


def upcoming_features_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / "processed" / "upcoming_features.json"


def run_enrich(data_dir: str | Path) -> Path:
    features = enrich_games(data_dir)
    return save_features(data_dir, features)


def _build_indexes(data_dir: Path, games: list[GameRecord]) -> dict[str, Any]:
    seasons = sorted({game.season for game in games})
    indexes: dict[str, Any] = {
        "raw_game": {},
        "raw_lines": {},
        "raw_weather": {},
        "raw_media": {},
        "raw_team_season": {},
        "raw_teams": {},
        "raw_coaches": {},
        "raw_havoc": {},
        "raw_adv_ngt": {},
        "raw_venues": {},
        "raw_conferences": {},
        "raw_pregame_wp": {},
        "raw_player_agg": {},
        "raw_prior_team_season": {},
        "raw_conference_change": {},
        "graphql_game": {},
        "graphql_weather": {},
        "graphql_lines": {},
        "graphql_game_team": {},
    }

    for season in seasons:
        _index_raw_file(indexes["raw_game"], data_dir / "raw" / f"games_{season}.json", "id")
        _index_raw_lines(indexes["raw_lines"], data_dir / "raw" / f"lines_{season}.json")
        _index_raw_file(indexes["raw_weather"], data_dir / "raw" / f"weather_{season}.json", "id")
        _index_raw_file(indexes["raw_media"], data_dir / "raw" / f"media_{season}.json", "id")
        _index_team_season_file(indexes["raw_team_season"], data_dir / "raw" / f"returning_production_{season}.json", "returning_production")
        _index_team_season_file(indexes["raw_team_season"], data_dir / "raw" / f"talent_{season}.json", "talent")
        _index_team_season_file(indexes["raw_team_season"], data_dir / "raw" / f"recruiting_teams_{season}.json", "recruiting_teams")
        _index_coach_seasons(indexes["raw_team_season"], data_dir / "raw" / f"coach_seasons_{season}.json", "coach_seasons")
        _index_team_season_file(indexes["raw_team_season"], data_dir / "raw" / f"core_ratings_{season}.json", "core_ratings")
        _index_team_name_file(indexes["raw_teams"], data_dir / "raw" / f"teams_{season}.json")
        _index_coaches(indexes["raw_coaches"], data_dir / "raw" / f"coaches_{season}.json", season)
        _index_havoc(indexes["raw_havoc"], data_dir / "raw" / f"game_havoc_stats_{season}.json")
        _index_havoc(indexes["raw_adv_ngt"], data_dir / "raw" / f"advanced_game_stats_ngt_{season}.json")
        _index_raw_file(indexes["raw_pregame_wp"], data_dir / "raw" / f"pregame_win_prob_{season}.json", "gameId")
        _index_prior_player_agg(indexes["raw_player_agg"], data_dir / "raw" / f"adjusted_player_passing_{season - 1}.json", season)
        _index_prior_team_season(indexes["raw_prior_team_season"], data_dir / "raw" / f"core_ratings_{season - 1}.json", "core_ratings", season)
        _index_prior_team_season(indexes["raw_prior_team_season"], data_dir / "raw" / f"srs_expanded_{season - 1}.json", "srs_expanded", season)
        _index_conference_change(indexes["raw_conference_change"], data_dir / "raw" / f"conference_changes_{season}.json", season)

    _index_raw_file(indexes["raw_venues"], data_dir / "raw" / "venues.json", "id")
    _index_conferences(indexes["raw_conferences"], data_dir / "raw" / "conferences.json")

    _index_raw_file(indexes["graphql_game"], data_dir / "graphql" / "game.json", "id")
    _index_raw_file(indexes["graphql_weather"], data_dir / "graphql" / "gameWeather.json", "gameId")
    _index_graphql_lines(indexes["graphql_lines"], data_dir / "graphql" / "gameLines.json")
    _index_graphql_game_team(indexes["graphql_game_team"], data_dir / "graphql" / "gameTeam.json", games)

    indexes["computed_running"] = _build_running_index(data_dir, seasons, games, indexes["raw_game"])
    indexes["computed_v1"] = _build_v1_index(data_dir, games)
    indexes["computed_line_move"] = _build_line_move_index(data_dir, seasons, games)
    indexes["computed_wind"] = _build_wind_index(
        data_dir, games, indexes["raw_game"], indexes["raw_weather"]
    )

    return indexes


def _build_wind_index(
    data_dir: Path,
    games: list[GameRecord],
    raw_games: dict[int, dict[str, Any]],
    raw_weather: dict[int, dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """Wind relative to the field axis, keyed by game_id.

    Orientation comes from ``raw/venue_orientation.json``; rows whose OSM match is
    not a nearby football pitch are dropped rather than trusted (see
    ``wind.orientation_is_usable``), so a game with a bad match reads as null, not
    as a confidently wrong crosswind.
    """
    path = data_dir / "raw" / "venue_orientation.json"
    orientation: dict[int, dict[str, Any]] = {}
    if path.exists():
        for row in json.loads(path.read_text(encoding="utf-8")):
            venue_id = row.get("venue_id")
            if venue_id is not None and orientation_is_usable(row):
                orientation[int(venue_id)] = row

    index: dict[int, dict[str, Any]] = {}
    for game in games:
        weather = raw_weather.get(game.game_id) or {}
        game_row = raw_games.get(game.game_id) or {}
        venue_id = weather.get("venueId") if weather.get("venueId") is not None else game_row.get("venueId")
        venue = orientation.get(int(venue_id)) if venue_id is not None else None
        index[game.game_id] = derive_wind(
            wind_direction_deg=weather.get("windDirection"),
            wind_speed_mph=weather.get("windSpeed"),
            azimuth_deg=venue.get("azimuth_deg") if venue else None,
            indoors=bool(weather.get("gameIndoors") or (venue or {}).get("dome")),
        )
    return index


def _build_running_index(
    data_dir: Path,
    seasons: list[int],
    games: list[GameRecord],
    raw_games: dict[int, dict[str, Any]],
) -> dict[tuple[int, str], dict[str, Any]]:
    ppa: dict[tuple[int, str], tuple[float | None, float | None]] = {}
    for season in seasons:
        path = data_dir / "raw" / f"ppa_games_{season}.json"
        if not path.exists():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            game_id = row.get("gameId") if row.get("gameId") is not None else row.get("game_id")
            team = row.get("team")
            if game_id is None or team is None:
                continue
            offense = row.get("offense") or {}
            defense = row.get("defense") or {}
            ppa[(int(game_id), str(team))] = (offense.get("overall"), defense.get("overall"))

    adv: dict[tuple[int, str], dict[str, float | None]] = {}
    for season in seasons:
        path = data_dir / "raw" / f"advanced_game_stats_{season}.json"
        if not path.exists():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            game_id = row.get("gameId") if row.get("gameId") is not None else row.get("game_id")
            team = row.get("team")
            if game_id is None or team is None:
                continue
            offense = row.get("offense") or {}
            defense = row.get("defense") or {}
            adv[(int(game_id), str(team))] = {
                "success_off": _coerce_numeric(offense.get("successRate")),
                "success_def": _coerce_numeric(defense.get("successRate")),
                "explosiveness_off": _coerce_numeric(offense.get("explosiveness")),
                "explosiveness_def": _coerce_numeric(defense.get("explosiveness")),
            }

    start_dates: dict[int, str] = {}
    kick_dates: dict[int, date] = {}
    for game_id, row in raw_games.items():
        start = row.get("startDate") or row.get("start_date")
        if start:
            start_dates[game_id] = str(start)
            kick_date = _et_date(start)
            if kick_date is not None:
                kick_dates[game_id] = kick_date

    return compute_running_stats(
        games, ppa=ppa, adv=adv, start_dates=start_dates, kick_dates=kick_dates
    )


def _build_v1_index(data_dir: Path, games: list[GameRecord]) -> dict[int, float]:
    """P(over) per game_id from the cached v1 fit (data/processed/v1_fit.json,
    written by ``cfb-system-maker refit-v1``). Empty dict if no fit is cached
    yet -- feature reads back None until a refit is run, same fail-closed
    pattern as the other computed_* indexes."""
    fit = load_v1_fit(data_dir)
    if fit is None:
        return {}
    return score_v1(games, fit)


def _build_line_move_index(
    data_dir: Path, seasons: list[int], games: list[GameRecord]
) -> dict[int, dict[str, float | None]]:
    """spread_open/spread_move/total_open/total_move, keyed by game_id.

    The open must come from the SAME provider row that supplied the built close
    (game.provider / game.spread / game.total) -- a cross-book open-minus-close is a
    basis difference, not line movement. Re-selects that row via normalize's own
    _select_line/_select_total rather than trusting _index_raw_lines, which flattens
    to lines[0] and would silently pick a different book. Missing open -> all four
    None (fail closed), never a zero default.
    """
    lines_by_season: dict[int, dict[int, list[dict[str, Any]]]] = {}
    for season in seasons:
        path = data_dir / "raw" / f"lines_{season}.json"
        if not path.exists():
            continue
        bucket: dict[int, list[dict[str, Any]]] = {}
        for row in json.loads(path.read_text(encoding="utf-8")):
            game_id = row.get("id")
            if game_id is None:
                continue
            bucket[int(game_id)] = row.get("lines") or []
        lines_by_season[season] = bucket

    index: dict[int, dict[str, float | None]] = {}
    for game in games:
        season_lines = lines_by_season.get(game.season)
        if season_lines is None:
            continue
        lines = season_lines.get(game.game_id)
        if not lines:
            continue

        selected = _select_line(lines, game.provider)
        if selected is None:
            continue

        spread_open = _coerce_numeric(selected.get("spreadOpen"))
        spread_move = (
            game.spread - spread_open if spread_open is not None and game.spread is not None else None
        )

        total_row = _select_total(lines, selected)
        total_open = _coerce_numeric(_first(total_row, "overUnderOpen", "over_under_open"))
        total_move = (
            game.total - total_open if total_open is not None and game.total is not None else None
        )

        index[game.game_id] = {
            "spread_open": spread_open,
            "spread_move": spread_move,
            "total_open": total_open,
            "total_move": total_move,
        }

    return index


def _coerce_numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _apply_feature(row: dict[str, Any], feature: FeatureDef, game: GameRecord, indexes: dict[str, Any]) -> None:
    if feature.team_scoped and feature.join == "conference_name":
        row[f"home_{feature.key}"] = _lookup_conference(feature, game.home_conference, indexes)
        row[f"away_{feature.key}"] = _lookup_conference(feature, game.away_conference, indexes)
        return
    value = _lookup(feature, game, indexes)
    if feature.team_scoped and feature.join in {"team_season", "team_name", "game_id"}:
        if feature.source_kind in {"raw_havoc", "raw_adv_ngt", "graphql_game_team", "computed_running"}:
            home_val, away_val = value if isinstance(value, tuple) else (None, None)
            row[f"home_{feature.key}"] = home_val
            row[f"away_{feature.key}"] = away_val
        else:
            home_val = _lookup_team_scoped(feature, game.home_team, game.season, indexes)
            away_val = _lookup_team_scoped(feature, game.away_team, game.season, indexes)
            row[f"home_{feature.key}"] = home_val
            row[f"away_{feature.key}"] = away_val
    else:
        row[feature.key] = value


def _lookup_conference(feature: FeatureDef, conference: str | None, indexes: dict[str, Any]) -> Any:
    if conference is None:
        return None
    record = indexes["raw_conferences"].get(conference)
    return _field_value(record, feature.field) if record else None


def _lookup(feature: FeatureDef, game: GameRecord, indexes: dict[str, Any]) -> Any:
    if feature.source_kind == "raw_game":
        record = indexes["raw_game"].get(game.game_id)
        if feature.field == "kickoff_hour":
            return _kickoff_hour_et(record)
        return _field_value(record, feature.field) if record else None

    if feature.source_kind == "raw_lines":
        record = indexes["raw_lines"].get(game.game_id)
        if not record:
            return None
        field = feature.lines_field or feature.field
        return record.get(field)

    if feature.source_kind == "raw_weather":
        record = indexes["raw_weather"].get(game.game_id)
        return _field_value(record, feature.field) if record else None

    if feature.source_kind == "raw_media":
        record = indexes["raw_media"].get(game.game_id)
        return _field_value(record, feature.field) if record else None

    if feature.source_kind == "raw_pregame_wp":
        record = indexes["raw_pregame_wp"].get(game.game_id)
        return _field_value(record, feature.field) if record else None

    if feature.source_kind == "raw_team_season":
        return None

    if feature.source_kind == "raw_teams":
        return None

    if feature.source_kind == "raw_coaches":
        return None

    if feature.source_kind == "raw_venues":
        game_row = indexes["raw_game"].get(game.game_id)
        venue_id = game_row.get("venueId") if game_row else None
        record = indexes["raw_venues"].get(int(venue_id)) if venue_id is not None else None
        return _field_value(record, feature.field) if record else None

    if feature.source_kind == "raw_havoc":
        havoc = indexes["raw_havoc"]
        home_val = _field_value(havoc.get((game.game_id, game.home_team)), feature.field)
        away_val = _field_value(havoc.get((game.game_id, game.away_team)), feature.field)
        return (home_val, away_val)

    if feature.source_kind == "raw_adv_ngt":
        adv = indexes["raw_adv_ngt"]
        home_val = _field_value(adv.get((game.game_id, game.home_team)), feature.field)
        away_val = _field_value(adv.get((game.game_id, game.away_team)), feature.field)
        return (home_val, away_val)

    if feature.source_kind == "computed_running":
        running = indexes["computed_running"]
        home_stats = running.get((game.game_id, game.home_team)) or {}
        away_stats = running.get((game.game_id, game.away_team)) or {}
        return (home_stats.get(feature.field), away_stats.get(feature.field))

    if feature.source_kind == "computed_v1":
        return indexes["computed_v1"].get(game.game_id)

    if feature.source_kind == "computed_line_move":
        return indexes["computed_line_move"].get(game.game_id, {}).get(feature.field)

    if feature.source_kind == "computed_wind":
        return indexes["computed_wind"].get(game.game_id, {}).get(feature.field)

    if feature.source_kind == "graphql_game":
        record = indexes["graphql_game"].get(game.game_id)
        return _field_value(record, feature.field) if record else None

    if feature.source_kind == "graphql_weather":
        record = indexes["graphql_weather"].get(game.game_id)
        return _field_value(record, feature.field) if record else None

    if feature.source_kind == "graphql_lines":
        record = indexes["graphql_lines"].get(game.game_id)
        return _field_value(record, feature.field) if record else None

    if feature.source_kind == "graphql_game_team":
        team_index = indexes["graphql_game_team"]
        home_val = _field_value(team_index.get((game.game_id, "home")), feature.field)
        away_val = _field_value(team_index.get((game.game_id, "away")), feature.field)
        return (home_val, away_val)

    return None


def _lookup_team_scoped(feature: FeatureDef, team: str, season: int, indexes: dict[str, Any]) -> Any:
    if feature.source_kind == "raw_team_season":
        bucket = indexes["raw_team_season"].get(feature.source_file or "")
        record = bucket.get((team, season)) if bucket else None
        return _field_value(record, feature.field) if record else None

    if feature.source_kind == "raw_prior_team_season":
        bucket = indexes["raw_prior_team_season"].get(feature.source_file or "")
        record = bucket.get((team, season)) if bucket else None
        return _field_value(record, feature.field) if record else None

    if feature.source_kind == "raw_conference_change":
        teams = indexes["raw_conference_change"].get(season)
        return None if teams is None else team in teams

    if feature.source_kind == "raw_player_agg":
        record = indexes["raw_player_agg"].get((team, season))
        return record.get(feature.field) if record else None

    if feature.source_kind == "raw_teams":
        record = indexes["raw_teams"].get((team, season))
        return _field_value(record, feature.field) if record else None

    if feature.source_kind == "raw_coaches":
        record = indexes["raw_coaches"].get((team, season))
        if not record:
            return None
        if feature.field == "coach_name":
            return f"{record.get('firstName', '')} {record.get('lastName', '')}".strip()
        if feature.field == "coach_style_cluster":
            name = f"{record.get('firstName', '')} {record.get('lastName', '')}".strip()
            return COACH_STYLE_CLUSTERS.get(name)
        return _field_value(record, feature.field)

    return None


def _field_value(record: dict[str, Any] | None, field: str) -> Any:
    if record is None:
        return None
    if "." in field:
        return get_nested(record, field)
    return record.get(field)


def _index_raw_file(bucket: dict[int, dict[str, Any]], path: Path, key_field: str) -> None:
    if not path.exists():
        return
    for row in json.loads(path.read_text(encoding="utf-8")):
        key = row.get(key_field)
        if key is not None:
            bucket[int(key)] = row


def _index_raw_lines(bucket: dict[int, dict[str, Any]], path: Path) -> None:
    if not path.exists():
        return
    for row in json.loads(path.read_text(encoding="utf-8")):
        game_id = row.get("id")
        if game_id is None:
            continue
        lines = row.get("lines") or []
        if not lines:
            continue
        bucket[int(game_id)] = lines[0]


_ET = ZoneInfo("America/New_York")


def _kickoff_hour_et(record: dict[str, Any] | None) -> int | None:
    """Eastern hour (0–23) from a games-row startDate. TBD clock → None."""
    if not record:
        return None
    if record.get("startTimeTBD") or record.get("start_time_tbd"):
        return None
    raw = record.get("startDate") or record.get("start_date")
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(_ET).hour


def _et_date(raw: Any) -> date | None:
    """Eastern calendar date from a games-row startDate.

    Unlike _kickoff_hour_et this ignores startTimeTBD: a TBD clock time still has a
    known date, which is all rest days needs. Eastern rather than UTC so a 10pm ET
    west-coast kickoff stays on its own Saturday instead of rolling to Sunday and
    shifting rest by a day.
    """
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(_ET).date()


def _index_coach_seasons(
    bucket: dict[str, dict[tuple[str, int], dict[str, Any]]], path: Path, name: str
) -> None:
    """Index coach_seasons rows; ``team`` is a nested {school} object on this endpoint."""
    if not path.exists():
        return
    store = bucket.setdefault(name, {})
    for row in json.loads(path.read_text(encoding="utf-8")):
        team = row.get("team") or row.get("school")
        if isinstance(team, dict):
            team = team.get("school") or team.get("name")
        season = row.get("year") or row.get("season")
        if team is not None and season is not None:
            store[(str(team), int(season))] = row


def _index_team_season_file(bucket: dict[str, dict[tuple[str, int], dict[str, Any]]], path: Path, name: str) -> None:
    if not path.exists():
        return
    store = bucket.setdefault(name, {})
    for row in json.loads(path.read_text(encoding="utf-8")):
        team = row.get("team") or row.get("school")
        season = row.get("season") or row.get("year")
        if team is not None and season is not None:
            store[(str(team), int(season))] = row


def _index_prior_player_agg(bucket: dict[tuple[str, int], dict[str, Any]], path: Path, season: int) -> None:
    """Aggregate a prior-season player wEPA file into (team, season) team totals.

    `path` is the season S-1 file; results are keyed under the current season S, so a
    season-S game reads S-1 players only (no-lookahead). Only teams with >=1 numeric
    wepa are stored, so an absent/empty file or a missing team yields None (fails closed).
    """
    if not path.exists():
        return
    sums: dict[str, float] = {}
    for row in json.loads(path.read_text(encoding="utf-8")):
        team = row.get("team")
        wepa = row.get("wepa")
        if team is None or isinstance(wepa, bool) or not isinstance(wepa, (int, float)):
            continue
        sums[str(team)] = sums.get(str(team), 0.0) + float(wepa)
    for team, total in sums.items():
        bucket[(team, season)] = {"prior_off_wepa": total}


def _index_prior_team_season(
    bucket: dict[str, dict[tuple[str, int], dict[str, Any]]],
    path: Path,
    name: str,
    season: int,
) -> None:
    """Index a season S-1 team-season file under key S, so season-S games read S-1 only.

    Same no-lookahead shape as `_index_prior_player_agg`: core ratings and expanded SRS are
    season-FINAL values (core rows carry `throughSeasonType: postseason`), so the current
    season's row would contain the result of the game being bet. A missing file or team
    yields None, which fails closed as a filter.
    """
    if not path.exists():
        return
    store = bucket.setdefault(name, {})
    for row in json.loads(path.read_text(encoding="utf-8")):
        team = row.get("team") or row.get("school")
        if team is not None:
            store[(str(team), season)] = row


def _index_conference_change(bucket: dict[int, set[str]], path: Path, season: int) -> None:
    """Teams whose conference move takes effect in `season`.

    Current-season on purpose: realignment is public before kickoff, so it is not lookahead.
    Stored per season as a set so a team absent from a *loaded* season resolves to False
    rather than None — "did not change conferences" is a real answer, not missing data.
    """
    if not path.exists():
        return
    teams = bucket.setdefault(season, set())
    for row in json.loads(path.read_text(encoding="utf-8")):
        team = row.get("team")
        if team is not None:
            teams.add(str(team))


def _index_team_name_file(bucket: dict[tuple[str, int], dict[str, Any]], path: Path) -> None:
    if not path.exists():
        return
    season = _season_from_filename(path)
    for row in json.loads(path.read_text(encoding="utf-8")):
        school = row.get("school")
        if school is not None and season is not None:
            bucket[(str(school), season)] = row


def _index_coaches(bucket: dict[tuple[str, int], dict[str, Any]], path: Path, season: int) -> None:
    if not path.exists():
        return
    for coach in json.loads(path.read_text(encoding="utf-8")):
        for season_row in coach.get("seasons") or []:
            if int(season_row.get("year", 0)) != season:
                continue
            school = season_row.get("school")
            if school:
                bucket[(str(school), season)] = coach


def _index_conferences(bucket: dict[str, dict[str, Any]], path: Path) -> None:
    if not path.exists():
        return
    for row in json.loads(path.read_text(encoding="utf-8")):
        name = row.get("name")
        if name is not None:
            bucket[str(name)] = row


def _index_havoc(bucket: dict[tuple[int, str], dict[str, Any]], path: Path) -> None:
    if not path.exists():
        return
    for row in json.loads(path.read_text(encoding="utf-8")):
        game_id = row.get("gameId")
        team = row.get("team")
        if game_id is not None and team is not None:
            bucket[(int(game_id), str(team))] = row


def _index_graphql_lines(bucket: dict[int, dict[str, Any]], path: Path) -> None:
    if not path.exists():
        return
    for row in json.loads(path.read_text(encoding="utf-8")):
        game_id = row.get("gameId")
        if game_id is None:
            continue
        bucket.setdefault(int(game_id), row)


def _index_graphql_game_team(
    bucket: dict[tuple[int, str], dict[str, Any]],
    path: Path,
    games: list[GameRecord],
) -> None:
    if not path.exists():
        return
    game_sides: dict[int, dict[str, str]] = {}
    for game in games:
        game_sides[game.game_id] = {"home": game.home_team, "away": game.away_team}

    team_ids: dict[tuple[int, str], int] = {}
    for row in json.loads(path.read_text(encoding="utf-8")):
        game_id = row.get("gameId")
        home_away = row.get("homeAway")
        team_id = row.get("teamId")
        if game_id is None or home_away is None or team_id is None:
            continue
        team_ids[(int(game_id), str(home_away))] = int(team_id)

    for row in json.loads(path.read_text(encoding="utf-8")):
        game_id = row.get("gameId")
        home_away = row.get("homeAway")
        if game_id is None or home_away is None:
            continue
        bucket[(int(game_id), str(home_away))] = row


def _season_from_filename(path: Path) -> int | None:
    stem = path.stem
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return int(parts[1])
    return None
