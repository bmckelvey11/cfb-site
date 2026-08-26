from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cfb_system_maker.features import effective_perspective
from cfb_system_maker.models import FeatureFilter, GameRecord, SavedSystem, SearchRun, SearchRunFinalist, SystemFilter

_SYSTEM_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# Bundled read-only example systems ship inside the package (D-14). The package
# runs from the repo root and is never installed, so a plain path relative to
# this module is enough — no package-resources API needed.
EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"

UPCOMING_FIELDS = [field.name for field in fields(GameRecord)] + ["start_date", "start_time_tbd"]


def _safe_system_name(name: str) -> str:
    if not _SYSTEM_NAME_RE.match(name):
        raise ValueError(f"invalid system name: {name!r}")
    return name


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


def save_upcoming_games(
    data_dir: str | Path,
    games: list[GameRecord],
    kickoffs: dict[int, dict[str, Any]],
) -> Path:
    """Write the upcoming-games table.

    Deliberately a separate file from ``games.csv``: it is not bound by the
    ``GameRecord`` field-order contract and carries two extra kickoff columns.
    """
    path = Path(data_dir) / "processed" / "upcoming.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=UPCOMING_FIELDS)
        writer.writeheader()
        for game in games:
            kickoff = kickoffs.get(game.game_id, {})
            row = asdict(game)
            start_date = kickoff.get("start_date")
            row["start_date"] = "" if start_date is None else str(start_date)
            row["start_time_tbd"] = "true" if kickoff.get("start_time_tbd") else "false"
            writer.writerow(row)
    return path


def load_upcoming_games(data_dir: str | Path) -> tuple[list[GameRecord], dict[int, dict[str, Any]]]:
    path = Path(data_dir) / "processed" / "upcoming.csv"
    games: list[GameRecord] = []
    kickoffs: dict[int, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            game = _row_to_game(row)
            games.append(game)
            kickoffs[game.game_id] = {
                "start_date": _none_if_blank(row["start_date"]),
                "start_time_tbd": row["start_time_tbd"] == "true",
            }
    return games, kickoffs


def save_upcoming_meta(data_dir: str | Path, meta: dict[str, Any]) -> Path:
    path = Path(data_dir) / "processed" / "upcoming_meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, default=str, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_upcoming_meta(data_dir: str | Path) -> dict[str, Any]:
    path = Path(data_dir) / "processed" / "upcoming_meta.json"
    return json.loads(path.read_text(encoding="utf-8"))


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


def save_system(
    name: str,
    system: SystemFilter,
    data_dir: str | Path,
    theory: str = "",
    *,
    source: str = "manual",
    search_candidates_tested: int | None = None,
) -> Path:
    name = _safe_system_name(name)
    saved = SavedSystem(
        name=name,
        saved_at=datetime.now(timezone.utc).isoformat(),
        system=system,
        theory=theory,
        source=source,
        search_candidates_tested=search_candidates_tested,
    )
    path = Path(data_dir) / "systems" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_system_to_dict(saved), indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_system(name: str, data_dir: str | Path) -> SystemFilter:
    name = _safe_system_name(name)
    path = Path(data_dir) / "systems" / f"{name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _system_from_dict(payload)


def load_saved_system(name: str, data_dir: str | Path) -> SavedSystem:
    name = _safe_system_name(name)
    path = Path(data_dir) / "systems" / f"{name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("system payload must be a JSON object")
    return SavedSystem(
        name=str(payload.get("name", name)),
        saved_at=str(payload.get("saved_at", "")),
        system=_system_from_dict(payload),
        theory=str(payload.get("theory", "")),
        source=str(payload.get("source", "manual")),
        search_candidates_tested=payload.get("search_candidates_tested", None),
    )


def list_systems(data_dir: str | Path) -> list[str]:
    systems_dir = Path(data_dir) / "systems"
    if not systems_dir.exists():
        return []
    return sorted(path.stem for path in systems_dir.glob("*.json"))


def list_examples(examples_dir: str | Path | None = None) -> list[str]:
    """Enumerate the bundled examples. Sibling of list_systems, but package-rooted."""
    directory = Path(examples_dir) if examples_dir is not None else EXAMPLES_DIR
    if not directory.exists():
        return []
    return sorted(path.stem for path in directory.glob("*.json"))


def load_example_system(name: str, examples_dir: str | Path | None = None) -> SavedSystem:
    """Load one bundled example read-only, through the same name gate and parser."""
    name = _safe_system_name(name)
    directory = Path(examples_dir) if examples_dir is not None else EXAMPLES_DIR
    payload = json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
    return SavedSystem(
        name=str(payload.get("name", name)),
        saved_at=str(payload.get("saved_at", "")),
        system=_system_from_dict(payload),
        theory=str(payload.get("theory", "")),
        source=str(payload.get("source", "manual")),
        search_candidates_tested=payload.get("search_candidates_tested", None),
    )


def _system_to_dict(saved: SavedSystem) -> dict[str, Any]:
    system = saved.system
    return {
        "name": saved.name,
        "saved_at": saved.saved_at,
        "theory": saved.theory,
        "source": saved.source,
        "search_candidates_tested": saved.search_candidates_tested,
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
            "fade": system.fade,
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
    if not isinstance(payload, dict):
        raise ValueError("system payload must be a JSON object")
    system = payload.get("system", payload)
    bet_type = str(system.get("bet_type", "spread"))
    feature_filters = tuple(
        FeatureFilter(
            key=str(row["key"]),
            op=str(row["op"]),
            value=row["value"],
            # Legacy saves can carry bet_side/opponent on total systems, which
            # used to misresolve to the vestigial side field — normalize on load.
            perspective=effective_perspective(bet_type, str(row.get("perspective", "single"))),
        )
        for row in system.get("feature_filters", [])
    )
    return SystemFilter(
        bet_type=bet_type,
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
        fade=bool(system.get("fade", False)),
        providers=set(system.get("providers", [])),
        min_spread=system.get("min_spread"),
        max_spread=system.get("max_spread"),
        min_total=system.get("min_total"),
        max_total=system.get("max_total"),
        feature_filters=feature_filters,
    )


def _finalist_system_to_dict(system: SystemFilter) -> dict[str, Any]:
    return {
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
        "fade": system.fade,
        "providers": sorted(system.providers),
        "min_spread": system.min_spread,
        "max_spread": system.max_spread,
        "min_total": system.min_total,
        "max_total": system.max_total,
        "feature_filters": [
            {"key": f.key, "op": f.op, "value": f.value, "perspective": f.perspective}
            for f in system.feature_filters
        ],
    }


def _finalist_system_from_dict(payload: dict[str, Any]) -> SystemFilter:
    bet_type = payload.get("bet_type", "spread")
    return SystemFilter(
        bet_type=bet_type,
        side=payload.get("side", "home"),
        total_side=payload.get("total_side", "over"),
        seasons=set(payload.get("seasons", [])),
        weeks=set(payload.get("weeks", [])),
        teams=set(payload.get("teams", [])),
        conferences=set(payload.get("conferences", [])),
        favorite=payload.get("favorite", False),
        underdog=payload.get("underdog", False),
        home=payload.get("home", False),
        away=payload.get("away", False),
        fade=payload.get("fade", False),
        providers=set(payload.get("providers", [])),
        min_spread=payload.get("min_spread"),
        max_spread=payload.get("max_spread"),
        min_total=payload.get("min_total"),
        max_total=payload.get("max_total"),
        feature_filters=tuple(
            FeatureFilter(
                key=f["key"],
                op=f["op"],
                value=f["value"],
                perspective=effective_perspective(bet_type, f.get("perspective", "single")),
            )
            for f in payload.get("feature_filters", [])
        ),
    )


def save_search_run(name: str, run: SearchRun, data_dir: str | Path) -> Path:
    name = _safe_system_name(name)
    payload = {
        "name": run.name,
        "saved_at": run.saved_at,
        "candidates_tested": run.candidates_tested,
        "finalists_graded": run.finalists_graded,
        "effective_params": run.effective_params,
        "finalists": [
            {
                "system": _finalist_system_to_dict(f.system),
                "wins": f.wins,
                "losses": f.losses,
                "pushes": f.pushes,
                "roi": f.roi,
                "raw_p": f.raw_p,
                "corrected_p": f.corrected_p,
                "bh_significant": f.bh_significant,
            }
            for f in run.finalists
        ],
    }
    path = Path(data_dir) / "search_runs" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_search_run(name: str, data_dir: str | Path) -> SearchRun:
    name = _safe_system_name(name)
    path = Path(data_dir) / "search_runs" / f"{name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SearchRun(
        name=str(payload.get("name", name)),
        saved_at=str(payload.get("saved_at", "")),
        candidates_tested=int(payload.get("candidates_tested", 0)),
        finalists_graded=int(payload.get("finalists_graded", 0)),
        effective_params=payload.get("effective_params", {}),
        finalists=tuple(
            SearchRunFinalist(
                system=_finalist_system_from_dict(f["system"]),
                wins=f["wins"],
                losses=f["losses"],
                pushes=f["pushes"],
                roi=f["roi"],
                raw_p=f["raw_p"],
                corrected_p=f["corrected_p"],
                bh_significant=f["bh_significant"],
            )
            for f in payload.get("finalists", [])
        ),
    )


def list_search_runs(data_dir: str | Path) -> list[str]:
    runs_dir = Path(data_dir) / "search_runs"
    if not runs_dir.exists():
        return []
    return sorted(path.stem for path in runs_dir.glob("*.json"))
