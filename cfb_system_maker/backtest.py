from __future__ import annotations

import math
import random
from dataclasses import replace
from typing import Any

from cfb_system_maker.features import feature_ok
from cfb_system_maker.models import BacktestResult, BetDetail, GameRecord, SeasonRecord, SystemFilter, SystemStats


def run_backtest(
    games: list[GameRecord],
    system: SystemFilter,
    *,
    stake: float = 1.0,
    american_odds: int = -110,
    feature_map: dict[int, dict[str, Any]] | None = None,
) -> BacktestResult:
    feature_map = feature_map or {}
    matched = [game for game in games if matches_system(game, system, feature_map)]
    details = [
        grade_bet(game, system, stake=stake, american_odds=american_odds)
        for game in matched
    ]
    wins = sum(1 for bet in details if bet.result == "win")
    losses = sum(1 for bet in details if bet.result == "loss")
    pushes = sum(1 for bet in details if bet.result == "push")
    bets = len(details)
    decided = wins + losses
    profit = round(sum(bet.profit for bet in details), 4)
    risked = bets * stake
    average_line = round(sum(bet.line for bet in details) / bets, 4) if bets else None
    hit_rate = round(wins / decided, 4) if decided else 0.0
    roi = round(profit / risked, 4) if risked else 0.0

    return BacktestResult(
        bets=bets,
        wins=wins,
        losses=losses,
        pushes=pushes,
        hit_rate=hit_rate,
        profit=profit,
        roi=roi,
        average_line=average_line,
        average_stake=stake,
        bet_details=details,
        stats=compute_system_stats(details, hit_rate=hit_rate, roi=roi, american_odds=american_odds, stake=stake),
        season_breakdown=tuple(compute_season_breakdown(details, stake=stake)),
        average_margin=(round(sum(bet.margin for bet in details) / bets, 4) if bets and system.bet_type == "spread" else None),
    )


def split_holdout(
    system: SystemFilter,
    holdout_seasons: set[int],
    available_seasons: set[int],
) -> tuple[SystemFilter, SystemFilter]:
    base_seasons = system.seasons if system.seasons else available_seasons
    in_sample_seasons = base_seasons - holdout_seasons
    holdout_only_seasons = base_seasons & holdout_seasons
    # empty means "no restriction" in matches_system; use a sentinel so an
    # empty split yields zero bets, not everything.
    if not in_sample_seasons:
        in_sample_seasons = {-1}
    if not holdout_only_seasons:
        holdout_only_seasons = {-1}
    return replace(system, seasons=in_sample_seasons), replace(system, seasons=holdout_only_seasons)


def compute_season_breakdown(details: list[BetDetail], *, stake: float = 1.0) -> list[SeasonRecord]:
    by_season: dict[int, list[BetDetail]] = {}
    for bet in details:
        by_season.setdefault(bet.season, []).append(bet)

    records = []
    for season in sorted(by_season):
        bets = by_season[season]
        wins = sum(1 for bet in bets if bet.result == "win")
        losses = sum(1 for bet in bets if bet.result == "loss")
        pushes = sum(1 for bet in bets if bet.result == "push")
        profit = round(sum(bet.profit for bet in bets), 4)
        risked = len(bets) * stake
        roi = round(profit / risked, 4) if risked else 0.0
        records.append(
            SeasonRecord(
                season=season, bets=len(bets), wins=wins, losses=losses,
                pushes=pushes, profit=profit, roi=roi,
            )
        )
    return records


def sign_consistency(records: list[SeasonRecord]) -> tuple[int, int]:
    profitable = sum(1 for record in records if record.roi > 0)
    return profitable, len(records)


def matches_system(
    game: GameRecord,
    system: SystemFilter,
    feature_map: dict[int, dict[str, Any]] | None = None,
) -> bool:
    if game.home_points is None or game.away_points is None:
        return False
    if system.bet_type == "spread" and game.spread is None:
        return False
    if system.bet_type == "total" and game.total is None:
        return False

    side = system.side.lower()
    if system.bet_type not in {"spread", "total"}:
        raise ValueError("bet_type must be 'spread' or 'total'")
    if system.bet_type == "spread" and side not in {"home", "away"}:
        raise ValueError("system side must be 'home' or 'away'")
    if system.bet_type == "total" and system.total_side not in {"over", "under"}:
        raise ValueError("total_side must be 'over' or 'under'")

    team = game.home_team if side == "home" else game.away_team
    conference = game.home_conference if side == "home" else game.away_conference
    side_spread = _side_spread(game.spread, side) if game.spread is not None else None

    if system.seasons and game.season not in system.seasons:
        return False
    if system.weeks and game.week not in system.weeks:
        return False
    if system.providers and game.provider not in system.providers:
        return False
    if system.teams and team not in system.teams:
        return False
    if system.conferences and conference not in system.conferences:
        return False
    if system.home and side != "home":
        return False
    if system.away and side != "away":
        return False
    if system.bet_type == "total":
        if system.min_total is not None and game.total is not None and game.total < system.min_total:
            return False
        if system.max_total is not None and game.total is not None and game.total > system.max_total:
            return False
    else:
        if side_spread is None:
            return False
        if system.favorite and side_spread >= 0:
            return False
        if system.underdog and side_spread <= 0:
            return False
        if system.min_spread is not None and side_spread < system.min_spread:
            return False
        if system.max_spread is not None and side_spread > system.max_spread:
            return False
        if system.min_total is not None and (game.total is None or game.total < system.min_total):
            return False
        if system.max_total is not None and (game.total is None or game.total > system.max_total):
            return False

    features = (feature_map or {}).get(game.game_id, {})
    return all(feature_ok(features, filt, system) for filt in system.feature_filters)


def compute_system_stats(
    details: list[BetDetail],
    *,
    hit_rate: float,
    roi: float,
    american_odds: int,
    stake: float,
    iterations: int = 1000,
    seed: int = 42,
) -> SystemStats:
    decided = sum(1 for bet in details if bet.result in {"win", "loss"})
    break_even_rate = _break_even_rate(american_odds)
    edge = round(hit_rate - break_even_rate, 4)
    wilson_low, wilson_high = _wilson_interval(hit_rate, decided)
    z_score, p_value = _hit_rate_z_test(hit_rate, decided, break_even_rate)
    returns = [bet.profit / stake for bet in details if bet.result in {"win", "loss"}]
    roi_std_error, roi_t_stat = _roi_stats(returns, roi)
    max_win_streak, max_loss_streak = _streaks(sorted(details, key=lambda bet: (bet.season, bet.week, bet.game_id)))
    permutation_p_value = _permutation_p_value(details, american_odds=american_odds, stake=stake, iterations=iterations, seed=seed)

    return SystemStats(
        break_even_rate=round(break_even_rate, 4),
        edge=edge,
        wilson_low=wilson_low,
        wilson_high=wilson_high,
        z_score=z_score,
        p_value=p_value,
        roi_std_error=roi_std_error,
        roi_t_stat=roi_t_stat,
        low_sample=decided < 30,
        max_win_streak=max_win_streak,
        max_loss_streak=max_loss_streak,
        permutation_p_value=permutation_p_value,
    )


def grade_bet(
    game: GameRecord,
    system: SystemFilter | str,
    *,
    stake: float = 1.0,
    american_odds: int = -110,
) -> BetDetail:
    if isinstance(system, str):
        system = SystemFilter(side=system)
    normalized_side = system.side.lower()
    if game.home_points is None or game.away_points is None:
        raise ValueError("game must have spread and final score")
    if system.bet_type == "total":
        return _grade_total_bet(game, system, stake=stake, american_odds=american_odds)
    if game.spread is None:
        raise ValueError("game must have spread and final score")

    if normalized_side == "home":
        team = game.home_team
        opponent = game.away_team
        team_points = game.home_points
        opponent_points = game.away_points
    elif normalized_side == "away":
        team = game.away_team
        opponent = game.home_team
        team_points = game.away_points
        opponent_points = game.home_points
    else:
        raise ValueError("side must be 'home' or 'away'")

    spread = _side_spread(game.spread, normalized_side)
    cover_margin = team_points + spread - opponent_points
    if cover_margin > 0:
        result = "win"
        profit = _profit_for_win(stake, american_odds)
    elif cover_margin < 0:
        result = "loss"
        profit = -stake
    else:
        result = "push"
        profit = 0.0

    return BetDetail(
        game_id=game.game_id,
        season=game.season,
        week=game.week,
        team=team,
        opponent=opponent,
        side=normalized_side,
        spread=spread,
        total=game.total,
        line=spread,
        result=result,
        profit=round(profit, 4),
        margin=round(cover_margin, 4),
    )


def _grade_total_bet(
    game: GameRecord,
    system: SystemFilter,
    *,
    stake: float,
    american_odds: int,
) -> BetDetail:
    if game.total is None or game.home_points is None or game.away_points is None:
        raise ValueError("game must have total and final score")

    points = game.home_points + game.away_points
    if points > game.total:
        winner = "over"
    elif points < game.total:
        winner = "under"
    else:
        winner = "push"

    if winner == "push":
        result = "push"
        profit = 0.0
    elif winner == system.total_side:
        result = "win"
        profit = _profit_for_win(stake, american_odds)
    else:
        result = "loss"
        profit = -stake

    return BetDetail(
        game_id=game.game_id,
        season=game.season,
        week=game.week,
        team=system.total_side.title(),
        opponent=f"{game.away_team} at {game.home_team}",
        side=system.total_side,
        spread=0.0,
        total=game.total,
        line=game.total,
        result=result,
        profit=round(profit, 4),
    )


def _break_even_rate(american_odds: int) -> float:
    if american_odds < 0:
        return abs(american_odds) / (abs(american_odds) + 100)
    return 100 / (american_odds + 100)


def _wilson_interval(hit_rate: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = hit_rate
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    low = (center - margin) / denom
    high = (center + margin) / denom
    return round(max(0.0, low), 4), round(min(1.0, high), 4)


def _hit_rate_z_test(hit_rate: float, n: int, break_even_rate: float) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    denom = math.sqrt(break_even_rate * (1 - break_even_rate) / n)
    if denom == 0:
        return 0.0, 1.0
    z_score = (hit_rate - break_even_rate) / denom
    p_value = 1 - _norm_cdf(z_score)
    return round(z_score, 4), round(p_value, 4)


def _permutation_p_value(
    details: list[BetDetail],
    *,
    american_odds: int,
    stake: float,
    iterations: int = 1000,
    seed: int = 42,
) -> float:
    decided_bets = [bet for bet in details if bet.result in {"win", "loss"}]
    decided = len(decided_bets)
    if decided == 0:
        return 1.0

    observed_profit = sum(bet.profit for bet in decided_bets)
    risked = decided * stake
    observed_roi = observed_profit / risked

    break_even_rate = _break_even_rate(american_odds)
    win_profit = _profit_for_win(stake, american_odds)
    loss_profit = -stake

    rng = random.Random(seed)
    at_or_above = 0
    for _ in range(iterations):
        profit = sum(win_profit if rng.random() < break_even_rate else loss_profit for _ in range(decided))
        if profit / risked >= observed_roi:
            at_or_above += 1
    return round(at_or_above / iterations, 4)


def _roi_stats(returns: list[float], roi: float) -> tuple[float, float]:
    n = len(returns)
    if n == 0:
        return 0.0, 0.0
    mean = sum(returns) / n
    variance = sum((value - mean) ** 2 for value in returns) / n
    std_error = math.sqrt(variance / n) if variance > 0 else 0.0
    t_stat = roi / std_error if std_error else 0.0
    return round(std_error, 4), round(t_stat, 4)


def _streaks(details: list[BetDetail]) -> tuple[int, int]:
    best_win = best_loss = win_run = loss_run = 0
    for bet in details:
        if bet.result == "win":
            win_run += 1
            loss_run = 0
        elif bet.result == "loss":
            loss_run += 1
            win_run = 0
        else:
            continue  # pushes neither extend nor break a streak
        best_win = max(best_win, win_run)
        best_loss = max(best_loss, loss_run)
    return best_win, best_loss


def _norm_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _side_spread(home_spread: float, side: str) -> float:
    return home_spread if side == "home" else -home_spread


def _profit_for_win(stake: float, american_odds: int) -> float:
    if american_odds < 0:
        return stake * 100 / abs(american_odds)
    return stake * american_odds / 100
