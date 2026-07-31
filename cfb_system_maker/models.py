from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GameRecord:
    game_id: int
    season: int
    week: int
    home_team: str
    away_team: str
    home_conference: str | None
    away_conference: str | None
    home_points: int | None
    away_points: int | None
    provider: str | None
    spread: float | None
    total: float | None


@dataclass(frozen=True)
class FeatureFilter:
    key: str
    op: str
    value: object
    perspective: str = "single"


@dataclass(frozen=True)
class SystemFilter:
    bet_type: str = "spread"
    side: str = "home"
    total_side: str = "over"
    seasons: set[int] = field(default_factory=set)
    weeks: set[int] = field(default_factory=set)
    teams: set[str] = field(default_factory=set)
    conferences: set[str] = field(default_factory=set)
    favorite: bool = False
    underdog: bool = False
    home: bool = False
    away: bool = False
    fade: bool = False
    providers: set[str] = field(default_factory=set)
    min_spread: float | None = None
    max_spread: float | None = None
    min_total: float | None = None
    max_total: float | None = None
    feature_filters: tuple[FeatureFilter, ...] = ()


@dataclass(frozen=True)
class SystemStats:
    break_even_rate: float
    edge: float
    wilson_low: float
    wilson_high: float
    z_score: float
    p_value: float
    roi_std_error: float
    roi_t_stat: float
    low_sample: bool
    max_win_streak: int = 0
    max_loss_streak: int = 0
    permutation_p_value: float = 1.0


@dataclass(frozen=True)
class BetDetail:
    game_id: int
    season: int
    week: int
    team: str
    opponent: str
    side: str
    spread: float
    total: float | None
    line: float
    result: str
    profit: float
    margin: float = 0.0


@dataclass(frozen=True)
class SeasonRecord:
    season: int
    bets: int
    wins: int
    losses: int
    pushes: int
    profit: float
    roi: float


@dataclass(frozen=True)
class BacktestResult:
    bets: int
    wins: int
    losses: int
    pushes: int
    hit_rate: float
    profit: float
    roi: float
    average_line: float | None
    average_stake: float
    bet_details: list[BetDetail]
    stats: SystemStats | None = None
    season_breakdown: tuple[SeasonRecord, ...] = ()
    average_margin: float | None = None
    grade: str | None = None


@dataclass(frozen=True)
class SavedSystem:
    name: str
    saved_at: str
    system: SystemFilter
    theory: str = ""
    source: str = "manual"
    search_candidates_tested: int | None = None
