"""Fetch and persist the current (or most recent) CFB week's games with lines.

Separate from the historical ``fetch`` / ``build`` path: this writes
``processed/upcoming.csv`` and never reads or writes ``processed/games.csv``.

The CFBD client is injectable (``cfbd_module``) the same way ``scrapers.scrape``
does it, so the whole pipeline runs network-free under test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cfb_system_maker.cfbd_client import _load_cfbd_module, _to_dict, find_cfbd_token
from cfb_system_maker.models import GameRecord
from cfb_system_maker.normalize import _first, normalize_games
from cfb_system_maker.storage import (
    save_raw_json,
    save_upcoming_games,
    save_upcoming_meta,
)

# How many seasons back the offseason fallback may step before giving up.
_MAX_SEASONS_BACK = 2

# One call covers regular + postseason, so a fallback that lands on a bowl week
# is found without a second round trip, and the raw dumps carry the whole season.
_BOTH = "both"


@dataclass(frozen=True)
class WeekResolution:
    season: int | None = None
    week: int | None = None
    season_type: str | None = None
    is_fallback: bool = False


@dataclass(frozen=True)
class UpcomingBuild:
    records: list[GameRecord] = field(default_factory=list)
    kickoffs: dict[int, dict[str, Any]] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


def resolve_target_week(
    now: datetime,
    *,
    cfbd_module: Any = None,
    token: str | None = None,
) -> WeekResolution:
    """Resolve the week to display. ``cfbd_module`` is injectable for tests."""
    cfbd = cfbd_module or _load_cfbd_module()
    configuration = cfbd.Configuration(access_token=token or find_cfbd_token())
    with cfbd.ApiClient(configuration) as api_client:
        resolution, _ = _resolve(cfbd.GamesApi(api_client), now)
    return resolution


def build_upcoming(
    data_dir: str | Path,
    *,
    now: datetime | None = None,
    cfbd_module: Any = None,
    token: str | None = None,
) -> UpcomingBuild:
    """Resolve the target week, fetch it, normalize it, and persist everything."""
    now = now or datetime.now(timezone.utc)
    cfbd = cfbd_module or _load_cfbd_module()
    configuration = cfbd.Configuration(access_token=token or find_cfbd_token())

    with cfbd.ApiClient(configuration) as api_client:
        games_api = cfbd.GamesApi(api_client)
        betting_api = cfbd.BettingApi(api_client)

        resolution, games_by_season = _resolve(games_api, now)
        if resolution.season is None:
            return _persist(data_dir, [], {}, resolution, now)

        season = resolution.season
        games = games_by_season.get(season)
        if games is None:
            games = [_to_dict(row) for row in games_api.get_games(year=season, season_type=_BOTH)]
        lines = [_to_dict(row) for row in betting_api.get_lines(year=season, season_type=_BOTH)]

    # Full season on both dumps: Plan 05-04 rebuilds its running-stats
    # accumulation base from these files and cannot recover what was never written.
    save_raw_json(data_dir, "games", season, games)
    save_raw_json(data_dir, "lines", season, lines)

    target = [row for row in games if _week_key(row) == (resolution.season_type, resolution.week)]
    records = normalize_games(target, lines, provider="consensus")
    kickoffs = _kickoffs(target)

    return _persist(data_dir, records, kickoffs, resolution, now)


def _resolve(games_api: Any, now: datetime) -> tuple[WeekResolution, dict[int, list[dict[str, Any]]]]:
    """Return the resolution plus any season game rows fetched along the way."""
    season = _season_for(now)
    games_by_season: dict[int, list[dict[str, Any]]] = {}

    calendar = [_to_dict(row) for row in games_api.get_calendar(year=season)]
    for week in calendar:
        start = _first(week, "startDate", "start_date")
        end = _first(week, "endDate", "end_date")
        if start is not None and end is not None and start <= now <= end:
            return (
                WeekResolution(
                    season=int(_first(week, "season", fallback=season)),
                    week=int(_first(week, "week")),
                    season_type=_season_type(week),
                    is_fallback=False,
                ),
                games_by_season,
            )

    # No window contains ``now`` -- step backward to the most recent played week.
    for candidate in range(season, season - _MAX_SEASONS_BACK - 1, -1):
        rows = [_to_dict(row) for row in games_api.get_games(year=candidate, season_type=_BOTH)]
        games_by_season[candidate] = rows
        latest = _latest_completed_week(rows)
        if latest is not None:
            season_type, week = latest
            return (
                WeekResolution(season=candidate, week=week, season_type=season_type, is_fallback=True),
                games_by_season,
            )

    return WeekResolution(), games_by_season


def _latest_completed_week(rows: list[dict[str, Any]]) -> tuple[str | None, int] | None:
    """Group completed games by (season_type, week); pick the group starting latest.

    Week numbers restart for the postseason, so groups are ranked by start date,
    never by week number.
    """
    latest_start: dict[tuple[str | None, int], datetime] = {}
    for row in rows:
        if not _first(row, "completed"):
            continue
        start = _first(row, "startDate", "start_date")
        week = _first(row, "week")
        if start is None or week is None:
            continue
        key = (_season_type(row), int(week))
        if key not in latest_start or start > latest_start[key]:
            latest_start[key] = start

    if not latest_start:
        return None
    return max(latest_start, key=lambda key: latest_start[key])


def _persist(
    data_dir: str | Path,
    records: list[GameRecord],
    kickoffs: dict[int, dict[str, Any]],
    resolution: WeekResolution,
    now: datetime,
) -> UpcomingBuild:
    meta = {
        "fetched_at": now.isoformat(),
        "season": resolution.season,
        "week": resolution.week,
        "season_type": resolution.season_type,
        "is_fallback": resolution.is_fallback,
        "row_count": len(records),
    }
    save_upcoming_games(data_dir, records, kickoffs)
    save_upcoming_meta(data_dir, meta)
    return UpcomingBuild(records=records, kickoffs=kickoffs, meta=meta)


def _kickoffs(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """``GameRecord`` has no date field, so kickoff is carried alongside it."""
    kickoffs: dict[int, dict[str, Any]] = {}
    for row in rows:
        game_id = _first(row, "id", "gameId", "game_id")
        if game_id is None:
            continue
        kickoffs[int(game_id)] = {
            "start_date": _first(row, "startDate", "start_date"),
            "start_time_tbd": bool(_first(row, "startTimeTBD", "start_time_tbd", fallback=False)),
        }
    return kickoffs


def _week_key(row: dict[str, Any]) -> tuple[str | None, int | None]:
    week = _first(row, "week")
    return (_season_type(row), int(week) if week is not None else None)


def _season_type(row: dict[str, Any]) -> str | None:
    value = _first(row, "seasonType", "season_type")
    return str(value) if value is not None else None


def _season_for(now: datetime) -> int:
    """January belongs to the previous season -- bowls and playoffs run into it."""
    return now.year - 1 if now.month == 1 else now.year
