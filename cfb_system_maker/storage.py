from __future__ import annotations

import csv
import json
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cfb_system_maker.models import FeatureFilter, GameRecord, SavedSystem, SystemFilter


def save_raw_json(data_dir: str | Path, name: str, season: int, rows: list[dict[str, Any]]) -> Path:
    path = Path(data_dir) / "raw" / f"{name}_{season}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, default=str, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_raw_json(data_dir: str | Path, name: str, season: int) -> list[dict[str, Any]]:
    path = Path(data_dir) / "raw" / f"{name}_{season}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def save_raw(data_dir: str | Path, filename: str, rows: list[dict[str, Any]]) -> Path:
    path = Path(data_dir) / "raw" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, default=str, indent=2, sort_keys=True), encoding="utf-8")
    return path


def save_processed_games(data_dir: str | Path, games: list[GameRecord]) -> Path:
    path = Path(data_dir) / "processed" / "games.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(GameRecord)]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for game in games:
            writer.writerow(asdict(game))
    return path


def load_processed_games(data_dir: str | Path) -> list[GameRecord]:
    path = Path(data_dir) / "processed" / "games.csv"
    with path.open(newline="", encoding="utf-8") as file:
        return [_row_to_game(row) for row in csv.DictReader(file)]


def _row_to_game(row: dict[str, str]) -> GameRecord:
    return GameRecord(
        game_id=int(row["game_id"]),
        season=int(row["season"]),
        week=int(row["week"]),
        home_team=row["home_team"],
        away_team=row["away_team"],
        home_conference=_none_if_blank(row["home_conference"]),
        away_conference=_none_if_blank(row["away_conference"]),
        home_points=_optional_int(row["home_points"]),
        away_points=_optional_int(row["away_points"]),
        provider=_none_if_blank(row["provider"]),
        spread=_optional_float(row["spread"]),
        total=_optional_float(row["total"]),
    )


def _none_if_blank(value: str) -> str | None:
    return value if value != "" else None


def _optional_int(value: str) -> int | None:
    return int(value) if value != "" else None


def _optional_float(value: str) -> float | None:
    return float(value) if value != "" else None


def save_system(name: str, system: SystemFilter, data_dir: str | Path) -> Path:
    saved = SavedSystem(
        name=name,
        saved_at=datetime.now(timezone.utc).isoformat(),
        system=system,
    )
    path = Path(data_dir) / "systems" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_system_to_dict(saved), indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_system(name: str, data_dir: str | Path) -> SystemFilter:
    path = Path(data_dir) / "systems" / f"{name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _system_from_dict(payload)


def list_systems(data_dir: str | Path) -> list[str]:
    systems_dir = Path(data_dir) / "systems"
    if not systems_dir.exists():
        return []
    return sorted(path.stem for path in systems_dir.glob("*.json"))


def _system_to_dict(saved: SavedSystem) -> dict[str, Any]:
    system = saved.system
    return {
        "name": saved.name,
        "saved_at": saved.saved_at,
        "system": {
            "bet_type": system.bet_type,
            "side": system.side,
            "total_side": system.total_side,
            "seasons": sorted(system.seasons),
            "weeks": sorted(system.weeks),
            "teams": sorted(system.teams),
            "conferences": sorted(system.conferences),
            "favorite": system.favorite,
            "underdog": system.underdog,
            "home": system.home,
            "away": system.away,
            "providers": sorted(system.providers),
            "min_spread": system.min_spread,
            "max_spread": system.max_spread,
            "min_total": system.min_total,
            "max_total": system.max_total,
            "feature_filters": [
                {
                    "key": filt.key,
                    "op": filt.op,
                    "value": filt.value,
                    "perspective": filt.perspective,
                }
                for filt in system.feature_filters
            ],
        },
    }


def _system_from_dict(payload: dict[str, Any]) -> SystemFilter:
    system = payload.get("system", payload)
    feature_filters = tuple(
        FeatureFilter(
            key=str(row["key"]),
            op=str(row["op"]),
            value=row["value"],
            perspective=str(row.get("perspective", "single")),
        )
        for row in system.get("feature_filters", [])
    )
    return SystemFilter(
        bet_type=str(system.get("bet_type", "spread")),
        side=str(system.get("side", "home")),
        total_side=str(system.get("total_side", "over")),
        seasons=set(system.get("seasons", [])),
        weeks=set(system.get("weeks", [])),
        teams=set(system.get("teams", [])),
        conferences=set(system.get("conferences", [])),
        favorite=bool(system.get("favorite", False)),
        underdog=bool(system.get("underdog", False)),
        home=bool(system.get("home", False)),
        away=bool(system.get("away", False)),
        providers=set(system.get("providers", [])),
        min_spread=system.get("min_spread"),
        max_spread=system.get("max_spread"),
        min_total=system.get("min_total"),
        max_total=system.get("max_total"),
        feature_filters=feature_filters,
    )
