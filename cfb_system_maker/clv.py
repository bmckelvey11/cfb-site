"""CLV (closing-line value) computation. Pure functions, heavily tested --
matches the style of backtest.py's stats functions. See
docs/superpowers/specs/2026-08-27-clv-betlog-ingestion-design.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from cfb_system_maker.betlog import BetLogRecord
from cfb_system_maker.storage import load_raw_json

_PROVIDER_CASCADE = ["consensus", "DraftKings", "Bovada", "ESPN Bet", "Caesars", "William Hill"]


def compute_clv(bet: BetLogRecord, closing_line: float) -> float:
    """CLV in points. Positive = the bettor's number was better than the
    closing number, from the side actually bet (docs/clv-analysis.md).

    For spread bets, `closing_line` is home-relative (CFBD's raw `spread`
    convention -- see models.GameRecord and backtest._side_spread) while
    `bet.line_taken` is side-relative (confirmed against the real Action
    Network export: an away favorite's own negative number is recorded
    from the away side, not translated to home terms). Convert
    closing_line to the bettor's side before comparing -- same flip
    backtest._side_spread applies for away bets.
    """
    if bet.bet_type == "total":
        if bet.side == "over":
            return round(closing_line - bet.line_taken, 4)
        return round(bet.line_taken - closing_line, 4)  # under
    # spread: convert home-relative closing_line to side-relative, then a
    # bigger side-relative number is always better for the side that took it.
    closing_side_relative = closing_line if bet.side == "home" else -closing_line
    return round(bet.line_taken - closing_side_relative, 4)


@dataclass(frozen=True)
class ClvStats:
    n: int
    mean_clv: float
    t_stat: float
    std_error: float


def compute_clv_stats(clv_values: list[float]) -> ClvStats:
    n = len(clv_values)
    if n == 0:
        return ClvStats(n=0, mean_clv=0.0, t_stat=0.0, std_error=0.0)
    mean = sum(clv_values) / n
    variance = sum((v - mean) ** 2 for v in clv_values) / n
    std_error = math.sqrt(variance / n) if variance > 0 else 0.0
    t_stat = mean / std_error if std_error else 0.0
    return ClvStats(n=n, mean_clv=round(mean, 4), t_stat=round(t_stat, 4), std_error=round(std_error, 4))


@dataclass(frozen=True)
class SeasonClv:
    season: int
    n: int
    mean_clv: float


def compute_clv_by_season(bets_with_clv: list[tuple[BetLogRecord, float]]) -> list[SeasonClv]:
    by_season: dict[int, list[float]] = {}
    for bet, clv in bets_with_clv:
        season = int(bet.date[:4])
        by_season.setdefault(season, []).append(clv)
    return [
        SeasonClv(season=season, n=len(values), mean_clv=round(sum(values) / len(values), 4))
        for season, values in sorted(by_season.items())
    ]


def find_closing_line(bet: BetLogRecord, data_dir: str | Path) -> float | None:
    bet_year = int(bet.date[:4])
    field = "overUnder" if bet.bet_type == "total" else "spread"
    # Try the calendar year first (the common case), then fall back to the
    # prior year for January bowl/CFP games, which CFBD files under the
    # prior season -- same pattern as betlog._build_games_by_date.
    for season in (bet_year, bet_year - 1):
        try:
            games = load_raw_json(data_dir, "lines", season)
        except FileNotFoundError:
            continue
        game = next((g for g in games if g.get("id") == bet.game_id), None)
        if game is None:
            continue
        lines = game.get("lines", [])
        for provider in _PROVIDER_CASCADE:
            for line in lines:
                if line.get("provider") == provider and line.get(field) is not None:
                    return line[field]
        return None  # game found but no usable line from any preferred provider
    return None
