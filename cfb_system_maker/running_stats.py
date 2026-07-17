from __future__ import annotations

from typing import Any

from cfb_system_maker.models import GameRecord


def compute_running_stats(
    games: list[GameRecord],
    *,
    ppa: dict[tuple[int, str], tuple[float | None, float | None]] | None = None,
    adv: dict[tuple[int, str], dict[str, float | None]] | None = None,
    start_dates: dict[int, str] | None = None,
) -> dict[tuple[int, str], dict[str, Any]]:
    ppa = ppa or {}
    adv = adv or {}
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
        ppa_off_sum = ppa_def_sum = 0.0
        ppa_off_count = ppa_def_count = 0
        adv_success_off_sum = 0.0
        adv_success_off_count = 0

        for _sort_key, game_id, game, side in entries:
            decided = wins + losses
            ats_decided = ats_wins + ats_losses
            stats[(game_id, team)] = {
                "games_played": played,
                "win_pct": round(wins / decided, 4) if decided else None,
                "ats_pct": round(ats_wins / ats_decided, 4) if ats_decided else None,
                "ppa_off": round(ppa_off_sum / ppa_off_count, 4) if ppa_off_count else None,
                "ppa_def": round(ppa_def_sum / ppa_def_count, 4) if ppa_def_count else None,
                "adv_success_off": round(adv_success_off_sum / adv_success_off_count, 4) if adv_success_off_count else None,
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
            game_ppa = ppa.get((game_id, team))
            if game_ppa:
                off_value, def_value = game_ppa
                if off_value is not None:
                    ppa_off_sum += float(off_value)
                    ppa_off_count += 1
                if def_value is not None:
                    ppa_def_sum += float(def_value)
                    ppa_def_count += 1
            game_adv = adv.get((game_id, team))
            if game_adv:
                success_off = game_adv.get("success_off")
                if success_off is not None:
                    adv_success_off_sum += float(success_off)
                    adv_success_off_count += 1

    return stats
