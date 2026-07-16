from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cfb_system_maker.features import FEATURE_REGISTRY, FeatureDef, get_nested
from cfb_system_maker.models import GameRecord
from cfb_system_maker.running_stats import compute_running_stats
from cfb_system_maker.storage import load_processed_games


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
    path = Path(data_dir) / "processed" / "features.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(features, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_features(data_dir: str | Path) -> dict[int, dict[str, Any]]:
    path = Path(data_dir) / "processed" / "features.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {int(game_id): values for game_id, values in raw.items()}


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
        _index_team_name_file(indexes["raw_teams"], data_dir / "raw" / f"teams_{season}.json")
        _index_coaches(indexes["raw_coaches"], data_dir / "raw" / f"coaches_{season}.json", season)
        _index_havoc(indexes["raw_havoc"], data_dir / "raw" / f"game_havoc_stats_{season}.json")

    _index_raw_file(indexes["graphql_game"], data_dir / "graphql" / "game.json", "id")
    _index_raw_file(indexes["graphql_weather"], data_dir / "graphql" / "gameWeather.json", "gameId")
    _index_graphql_lines(indexes["graphql_lines"], data_dir / "graphql" / "gameLines.json")
    _index_graphql_game_team(indexes["graphql_game_team"], data_dir / "graphql" / "gameTeam.json", games)

    indexes["computed_running"] = _build_running_index(data_dir, seasons, games, indexes["raw_game"])

    return indexes


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

    start_dates: dict[int, str] = {}
    for game_id, row in raw_games.items():
        start = row.get("startDate") or row.get("start_date")
        if start:
            start_dates[game_id] = str(start)

    return compute_running_stats(games, ppa=ppa, start_dates=start_dates)


def _apply_feature(row: dict[str, Any], feature: FeatureDef, game: GameRecord, indexes: dict[str, Any]) -> None:
    value = _lookup(feature, game, indexes)
    if feature.team_scoped and feature.join in {"team_season", "team_name", "game_id"}:
        if feature.source_kind in {"raw_havoc", "graphql_game_team", "computed_running"}:
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


def _lookup(feature: FeatureDef, game: GameRecord, indexes: dict[str, Any]) -> Any:
    if feature.source_kind == "raw_game":
        record = indexes["raw_game"].get(game.game_id)
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

    if feature.source_kind == "raw_team_season":
        return None

    if feature.source_kind == "raw_teams":
        return None

    if feature.source_kind == "raw_coaches":
        return None

    if feature.source_kind == "raw_havoc":
        havoc = indexes["raw_havoc"]
        home_val = _field_value(havoc.get((game.game_id, game.home_team)), feature.field)
        away_val = _field_value(havoc.get((game.game_id, game.away_team)), feature.field)
        return (home_val, away_val)

    if feature.source_kind == "computed_running":
        running = indexes["computed_running"]
        home_stats = running.get((game.game_id, game.home_team)) or {}
        away_stats = running.get((game.game_id, game.away_team)) or {}
        return (home_stats.get(feature.field), away_stats.get(feature.field))

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

    if feature.source_kind == "raw_teams":
        record = indexes["raw_teams"].get((team, season))
        return _field_value(record, feature.field) if record else None

    if feature.source_kind == "raw_coaches":
        record = indexes["raw_coaches"].get((team, season))
        if not record:
            return None
        if feature.field == "coach_name":
            return f"{record.get('firstName', '')} {record.get('lastName', '')}".strip()
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


def _index_team_season_file(bucket: dict[str, dict[tuple[str, int], dict[str, Any]]], path: Path, name: str) -> None:
    if not path.exists():
        return
    store = bucket.setdefault(name, {})
    for row in json.loads(path.read_text(encoding="utf-8")):
        team = row.get("team") or row.get("school")
        season = row.get("season") or row.get("year")
        if team is not None and season is not None:
            store[(str(team), int(season))] = row


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
