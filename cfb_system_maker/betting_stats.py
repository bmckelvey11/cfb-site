"""League-wide betting figures per season, graded by the backtest engine.

Every cover, push and over here comes from ``backtest.grade_bet`` -- the same
grader a saved system uses -- so this page and a "bet every home team" system
can never disagree about what covered. Inputs are the processed ``games.csv``
rows the web app already loads: the selected closing line per game
(``GameRecord.spread`` is the **home** spread, ``total`` the closing total)
and the final score. Nothing here is a pre-game feature; it describes results.

Definitions (all rates exclude pushes from the denominator, so they read like
a system's hit rate; push rates are reported on their own):

- spread game: final score known and a closing spread present.
- total game: final score known and a closing total present.
- home ATS cover %: home side graded ``win`` / (wins + losses) over spread games.
- favorite ATS cover %: the favorite (home when spread < 0, away when
  spread > 0) graded ``win`` / decided. Pick'em (spread == 0) has no favorite
  and is left out.
- home-underdog cover %: home side graded ``win`` / decided, over spread
  games with spread > 0.
- ATS push %: pushes / all spread games.
- over %: over graded ``win`` / (overs + unders) over total games.
- O/U push %: pushes / all total games.
- avg total / avg combined points: means over total games, so the two are
  on the same set of games and their gap is the average miss of the total.
- avg home spread: mean signed closing home spread over spread games
  (negative means home teams were favored on average).
"""
from __future__ import annotations

from dataclasses import dataclass

from cfb_system_maker.backtest import grade_bet
from cfb_system_maker.models import GameRecord, SystemFilter

_HOME = SystemFilter(side="home")
_AWAY = SystemFilter(side="away")
_OVER = SystemFilter(bet_type="total", total_side="over")


@dataclass(frozen=True)
class BettingStatsRow:
    label: str
    season: int | None
    spread_games: int
    total_games: int
    home_cover_rate: float | None
    favorite_cover_rate: float | None
    favorite_games: int
    home_dog_cover_rate: float | None
    home_dog_games: int
    ats_push_rate: float | None
    over_rate: float | None
    ou_push_rate: float | None
    avg_total: float | None
    avg_points: float | None
    avg_home_spread: float | None


class _Tally:
    __slots__ = ("wins", "losses", "pushes")

    def __init__(self) -> None:
        self.wins = 0
        self.losses = 0
        self.pushes = 0

    def add(self, result: str) -> None:
        if result == "win":
            self.wins += 1
        elif result == "loss":
            self.losses += 1
        else:
            self.pushes += 1

    @property
    def games(self) -> int:
        return self.wins + self.losses + self.pushes

    @property
    def rate(self) -> float | None:
        decided = self.wins + self.losses
        return self.wins / decided if decided else None

    @property
    def push_rate(self) -> float | None:
        return self.pushes / self.games if self.games else None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _is_final(game: GameRecord) -> bool:
    return game.home_points is not None and game.away_points is not None


def summarize(games: list[GameRecord], *, label: str, season: int | None = None) -> BettingStatsRow:
    """One row of league figures over ``games`` (completed games with lines only)."""
    home, favorite, home_dog, over = _Tally(), _Tally(), _Tally(), _Tally()
    spreads: list[float] = []
    totals: list[float] = []
    points: list[float] = []
    for game in games:
        if not _is_final(game):
            continue
        if game.spread is not None:
            home_result = grade_bet(game, _HOME).result
            home.add(home_result)
            spreads.append(game.spread)
            if game.spread < 0:
                favorite.add(home_result)
            elif game.spread > 0:
                favorite.add(grade_bet(game, _AWAY).result)
                home_dog.add(home_result)
        if game.total is not None:
            over.add(grade_bet(game, _OVER).result)
            totals.append(game.total)
            points.append(game.home_points + game.away_points)
    return BettingStatsRow(
        label=label,
        season=season,
        spread_games=home.games,
        total_games=over.games,
        home_cover_rate=home.rate,
        favorite_cover_rate=favorite.rate,
        favorite_games=favorite.games,
        home_dog_cover_rate=home_dog.rate,
        home_dog_games=home_dog.games,
        ats_push_rate=home.push_rate,
        over_rate=over.rate,
        ou_push_rate=over.push_rate,
        avg_total=_mean(totals),
        avg_points=_mean(points),
        avg_home_spread=_mean(spreads),
    )


def betting_stats_by_season(games: list[GameRecord], season: int | None = None) -> list[BettingStatsRow]:
    """Newest season first, then an all-seasons row.

    With ``season`` given, only that season's row is returned (the all-seasons
    row would repeat it).
    """
    if season is not None:
        return [summarize([g for g in games if g.season == season], label=str(season), season=season)]
    seasons = sorted({game.season for game in games}, reverse=True)
    rows = [summarize([g for g in games if g.season == s], label=str(s), season=s) for s in seasons]
    rows.append(summarize(games, label="All seasons"))
    return rows
