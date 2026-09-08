from __future__ import annotations

from datetime import date
from typing import Any

from cfb_system_maker.models import GameRecord

# output stat key -> adv-dict inner key (each accumulated as a strictly-prior game-average)
_ADV_FIELDS: dict[str, str] = {
    "adv_success_off": "success_off",
    "adv_success_def": "success_def",
    "adv_explosiveness_off": "explosiveness_off",
    "adv_explosiveness_def": "explosiveness_def",
}


def compute_running_stats(
    games: list[GameRecord],
    *,
    ppa: dict[tuple[int, str], tuple[float | None, float | None]] | None = None,
    adv: dict[tuple[int, str], dict[str, float | None]] | None = None,
    start_dates: dict[int, str] | None = None,
    kick_dates: dict[int, date] | None = None,
) -> dict[tuple[int, str], dict[str, Any]]:
    ppa = ppa or {}
    adv = adv or {}
    start_dates = start_dates or {}
    kick_dates = kick_dates or {}

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
        # Signed run length entering the game: +n won/covered last n, -n lost/
        # failed to cover last n, 0 for no history or after a tie/ATS push.
        streak = ats_streak = 0
        ppa_off_sum = ppa_def_sum = 0.0
        ppa_off_count = ppa_def_count = 0
        adv_sums: dict[str, float] = {out_key: 0.0 for out_key in _ADV_FIELDS}
        adv_counts: dict[str, int] = {out_key: 0 for out_key in _ADV_FIELDS}
        prev_date: date | None = None

        for _sort_key, game_id, game, side in entries:
            decided = wins + losses
            kick_date = kick_dates.get(game_id)
            rest_days = (kick_date - prev_date).days if kick_date and prev_date else None
            # Entries without a kickoff date sort to the tail of the season (the
            # week fallback string sorts after every ISO date), so their neighbours'
            # order is not trustworthy -- a non-positive gap means None, not 0.
            if rest_days is not None and rest_days <= 0:
                rest_days = None
            ats_decided = ats_wins + ats_losses
            stats[(game_id, team)] = {
                "games_played": played,
                "rest_days": rest_days,
                "win_pct": round(wins / decided, 4) if decided else None,
                "ats_pct": round(ats_wins / ats_decided, 4) if ats_decided else None,
                "streak": streak,
                "ats_streak": ats_streak,
                "ppa_off": round(ppa_off_sum / ppa_off_count, 4) if ppa_off_count else None,
                "ppa_def": round(ppa_def_sum / ppa_def_count, 4) if ppa_def_count else None,
                **{
                    out_key: round(adv_sums[out_key] / adv_counts[out_key], 4) if adv_counts[out_key] else None
                    for out_key in _ADV_FIELDS
                },
            }

            # Rest is schedule-derived, so it advances on every game -- including one
            # with no score, which the result accumulators below skip. A missing date
            # breaks the chain rather than measuring rest from two games back.
            prev_date = kick_date

            team_points = game.home_points if side == "home" else game.away_points
            opponent_points = game.away_points if side == "home" else game.home_points
            if team_points is None or opponent_points is None:
                continue
            played += 1
            if team_points > opponent_points:
                wins += 1
                streak = streak + 1 if streak > 0 else 1
            elif team_points < opponent_points:
                losses += 1
                streak = streak - 1 if streak < 0 else -1
            else:
                streak = 0  # a tie belongs to neither run
            if game.spread is not None:
                side_spread = game.spread if side == "home" else -game.spread
                margin = team_points + side_spread - opponent_points
                if margin > 0:
                    ats_wins += 1
                    ats_streak = ats_streak + 1 if ats_streak > 0 else 1
                elif margin < 0:
                    ats_losses += 1
                    ats_streak = ats_streak - 1 if ats_streak < 0 else -1
                else:
                    ats_streak = 0
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
                for out_key, inner_key in _ADV_FIELDS.items():
                    value = game_adv.get(inner_key)
                    if value is not None:
                        adv_sums[out_key] += float(value)
                        adv_counts[out_key] += 1

    return stats
