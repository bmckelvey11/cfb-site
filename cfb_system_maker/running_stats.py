from __future__ import annotations

from typing import Any

from cfb_system_maker.models import GameRecord


def compute_running_stats(
    games: list[GameRecord],
    *,
    start_dates: dict[int, str] | None = None,
) -> dict[tuple[int, str], dict[str, Any]]:
    start_dates = start_dates or {}

    by_team_season: dict[tuple[str, int], list[tuple[str, int, GameRecord, str]]] = {}
    for game in games:
        sort_key = start_dates.get(game.game_id) or f"{game.season:04d}-w{game.week:02d}"
        for side, team in (("home", game.home_team), ("away", game.away_team)):
            by_team_season.setdefault((team, game.season), []).append((sort_key, game.game_id, game, side))

    stats: dict[tuple[int, str], dict[str, Any]] = {}
    for (team, _season), entries in by_team_season.items():
        entries.sort(key=lambda entry: (entry[0], entry[1]))
        played = wins = losses = 0
        ats_wins = ats_losses = 0

        for _sort_key, game_id, game, side in entries:
            decided = wins + losses
            ats_decided = ats_wins + ats_losses
            stats[(game_id, team)] = {
                "games_played": played,
                "win_pct": round(wins / decided, 4) if decided else None,
                "ats_pct": round(ats_wins / ats_decided, 4) if ats_decided else None,
            }

            team_points = game.home_points if side == "home" else game.away_points
            opponent_points = game.away_points if side == "home" else game.home_points
            if team_points is None or opponent_points is None:
                continue
            played += 1
            if team_points > opponent_points:
                wins += 1
            elif team_points < opponent_points:
                losses += 1
            if game.spread is not None:
                side_spread = game.spread if side == "home" else -game.spread
                margin = team_points + side_spread - opponent_points
                if margin > 0:
                    ats_wins += 1
                elif margin < 0:
                    ats_losses += 1
                # margin == 0 is an ATS push: counts toward neither side

    return stats
