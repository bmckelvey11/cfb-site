"""Point-in-time averages for formerly post-game feature filters."""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from cfb_system_maker.features import get_nested
from cfb_system_maker.models import GameRecord

FIELDS = {
    "havoc_offense_rate": ("havoc", "offense.havocRate"),
    "havoc_defense_rate": ("havoc", "defense.havocRate"),
    "defense_explosiveness": ("ngt", "defense.explosiveness"),
    "defense_passingDowns_ppa": ("ngt", "defense.passingDowns.ppa"),
    "defense_ppa": ("ngt", "defense.ppa"),
    "defense_rushingPlays_ppa": ("ngt", "defense.rushingPlays.ppa"),
    "defense_successRate": ("ngt", "defense.successRate"),
}


def kickoff(row: dict[str, Any]) -> datetime | None:
    if row.get("startTimeTBD") or row.get("start_time_tbd"):
        return None
    try:
        value = datetime.fromisoformat(str(row.get("startDate") or row.get("start_date")).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return value if value.tzinfo is not None else None


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def build_prior_game_stats(
    games: list[GameRecord], raw_games: dict[int, dict], havoc: dict, ngt: dict,
) -> dict[tuple[int, str], dict[str, float | None]]:
    """Equal-weight game averages, excluding current/future/incomplete games.

    A conservative 24-hour lag avoids treating an earlier kickoff as a completed
    game. Historical files can contain later corrections; this is temporal
    feature isolation, not a claim of archived publication-time data vintages.
    """
    history: dict[tuple[int, str], list[tuple[datetime, int]]] = {}
    for game_id, row in raw_games.items():
        start = kickoff(row)
        if start is None or row.get("completed") is False:
            continue
        if finite_number(row.get("homePoints", row.get("home_points"))) is None or finite_number(row.get("awayPoints", row.get("away_points"))) is None:
            continue
        season = row.get("season")
        if season is None:
            continue
        for team in (row.get("homeTeam", row.get("home_team")), row.get("awayTeam", row.get("away_team"))):
            if team:
                history.setdefault((int(season), str(team)), []).append((start, game_id))

    output = {}
    sources = {"havoc": havoc, "ngt": ngt}
    for game in games:
        start = kickoff(raw_games.get(game.game_id, {}))
        for team in (game.home_team, game.away_team):
            values: dict[str, list[float]] = {key: [] for key in FIELDS}
            if start is not None:
                for previous_start, previous_id in history.get((game.season, team), []):
                    if previous_id == game.game_id or previous_start + timedelta(hours=24) > start:
                        continue
                    for key, (source, path) in FIELDS.items():
                        value = finite_number(get_nested(sources[source].get((previous_id, team), {}), path))
                        if value is not None:
                            values[key].append(value)
            output[(game.game_id, team)] = {
                key: round(math.fsum(items) / len(items), 6) if items else None
                for key, items in values.items()
            }
    return output
