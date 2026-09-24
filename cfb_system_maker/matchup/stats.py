"""Stat registry for the matchup page: what each row reads and whether it is knowable pre-game.

Verdicts copy `scripts/audit_pregame_eligibility.py` wherever it covers the column
(`tests/test_matchup_page.py` fails when the two disagree). Where the audit does not cover a
table, the verdict is assigned here and `reason` says why; the guide lists those.

How a verdict is shown:
- pregame_windowed: aggregated over the as-of window (games before the selected week).
- pregame_direct: fixed before the season; shown as-is.
- lookahead_only: a season-final snapshot. In as-of mode only the prior season's value is
  shown (labelled PRIOR SEASON); the current season's lives in the postgame panel.
- postgame: this game's result; postgame panel only.
"""
from __future__ import annotations

from dataclasses import dataclass

PREGAME_WINDOWED = "pregame_windowed"
PREGAME_DIRECT = "pregame_direct"
LOOKAHEAD_ONLY = "lookahead_only"
POSTGAME = "postgame"


@dataclass(frozen=True)
class Stat:
    key: str
    label: str
    table: str
    column: str
    higher_is_better: bool | None  # None: descriptive only, no edge marker
    fmt: str  # "pct" (0-1 rate) | "num" | "signed" (+ on positives) | "int"
    verdict: str
    reason: str = ""  # required when the audit does not cover table.column
    dp: int | None = None  # decimals shown; None lets the page scale by magnitude


_SEASON_FINAL = "season-final snapshot with no as-of date; same shape as the audited stg.fpi"

RATINGS: tuple[Stat, ...] = (
    Stat("sp_rating", "SP+", "stg.sp", "rating", True, "signed", LOOKAHEAD_ONLY, _SEASON_FINAL, dp=1),
    Stat("sp_offense", "SP+ offense", "stg.sp", "offense_rating", True, "num", LOOKAHEAD_ONLY, _SEASON_FINAL, dp=1),
    Stat("sp_defense", "SP+ defense", "stg.sp", "defense_rating", False, "num", LOOKAHEAD_ONLY, _SEASON_FINAL, dp=1),
    Stat("sp_special_teams", "SP+ special teams", "stg.sp", "specialTeams_rating", True, "signed", LOOKAHEAD_ONLY, _SEASON_FINAL, dp=1),
    Stat("fpi", "FPI", "stg.fpi", "fpi", True, "signed", LOOKAHEAD_ONLY, dp=1),
    Stat("fpi_offense", "FPI offense eff.", "stg.fpi", "efficiencies_offense", True, "num", LOOKAHEAD_ONLY, dp=1),
    Stat("fpi_defense", "FPI defense eff.", "stg.fpi", "efficiencies_defense", True, "num", LOOKAHEAD_ONLY, dp=1),
    Stat("srs", "SRS", "stg.srs", "rating", True, "signed", LOOKAHEAD_ONLY, _SEASON_FINAL, dp=1),
    Stat("elo", "Elo", "stg.elo", "elo", True, "int", LOOKAHEAD_ONLY),
    Stat("cr_overall", "Core rating", "stg.core_ratings", "overall", True, "signed", LOOKAHEAD_ONLY, dp=1),
    Stat("cr_offense", "Core offense", "stg.core_ratings", "offense", True, "num", LOOKAHEAD_ONLY, dp=1),
    Stat("cr_defense", "Core defense", "stg.core_ratings", "defense", False, "num", LOOKAHEAD_ONLY, dp=1),
)


# Opponent-adjusted season aggregates: postgame panel / full-season mode only.
ADJUSTED: tuple[Stat, ...] = (
    Stat("adj_epa", "Adj. EPA/play", "stg.adjusted_team_season", "epa_total", True, "signed", LOOKAHEAD_ONLY),
    Stat("adj_epa_allowed", "Adj. EPA/play allowed", "stg.adjusted_team_season", "epaAllowed_total", False, "signed", LOOKAHEAD_ONLY),
    Stat("adj_sr", "Adj. success rate", "stg.adjusted_team_season", "successRate_total", True, "pct", LOOKAHEAD_ONLY),
    Stat("adj_sr_allowed", "Adj. success rate allowed", "stg.adjusted_team_season", "successRateAllowed_total", False, "pct", LOOKAHEAD_ONLY),
    Stat("adj_expl", "Adj. explosiveness", "stg.adjusted_team_season", "explosiveness", True, "num", LOOKAHEAD_ONLY),
    Stat("adj_expl_allowed", "Adj. explosiveness allowed", "stg.adjusted_team_season", "explosivenessAllowed", False, "num", LOOKAHEAD_ONLY),
)

# Fixed before the season starts.
PROFILE: tuple[Stat, ...] = (
    Stat("talent", "Talent composite", "stg.talent", "talent", True, "num", PREGAME_DIRECT),
    Stat("recruiting", "Recruiting points", "stg.recruiting_teams", "points", True, "num", PREGAME_DIRECT),
    Stat("returning_ppa", "Returning PPA", "stg.returning_production", "percentPPA", True, "pct", PREGAME_DIRECT),
    Stat("returning_usage", "Returning usage", "stg.returning_production", "usage", True, "pct", PREGAME_DIRECT),
)

ALL: tuple[Stat, ...] = RATINGS + ADJUSTED + PROFILE


# --- unit matchups: game-grain, windowed over games before the selected week -------------

@dataclass(frozen=True)
class Source:
    """A game-grain source with offense_<stem>/defense_<stem> columns per team-game."""
    key: str
    table: str  # the all-plays table; the audit and the drift test key on it
    ngt: str | None  # its no-garbage-time twin, if CFBD publishes one
    label: str


ADVANCED = Source("advanced", "stg.advanced_game_stats", "stg.advanced_game_stats_ngt", "CFBD advanced box")
PPA = Source("ppa", "stg.ppa_games", "stg.ppa_games_ngt", "CFBD PPA by game")
HAVOC = Source("havoc", "stg.game_havoc_stats", None, "CFBD havoc")
DRIVES = Source("drives", "core.fact_drive_postgame", None, "Drives")
SOURCES = {s.key: s for s in (ADVANCED, PPA, HAVOC, DRIVES)}

_PPA_REASON = "game grain with week; same shape as the audited stg.advanced_game_stats"
_HAVOC_REASON = "game grain with week; same shape as the audited stg.advanced_game_stats"
_DRIVE_REASON = ("drive grain rolled up per game; prior games' drives only, the audited stg.drives "
                 "non-score columns are pregame_windowed")


@dataclass(frozen=True)
class Unit:
    """One stat as offense_<stem> (for the offense) against defense_<stem> (for the defense).

    `higher_is_better` is the offense's direction; CFBD's defense_<stem> is what the defense
    allowed or caused, so the defense's direction is the opposite.
    """
    key: str
    label: str
    source: str
    stem: str
    higher_is_better: bool | None
    fmt: str
    weight: str | None  # stem of the play/drive count that pools it; None pools as a game mean
    verdict: str = PREGAME_WINDOWED
    reason: str = ""
    dp: int | None = None

    @property
    def table(self) -> str:
        return SOURCES[self.source].table


def _adv(key, label, stem, hib, fmt, dp=None):
    return Unit(key, label, "advanced", stem, hib, fmt, "plays", dp=dp)


def _ppa(key, label, stem):
    return Unit(key, label, "ppa", stem, True, "signed", None, reason=_PPA_REASON, dp=3)


def _drv(key, label, stem, hib, fmt, weight="drives", dp=2):
    return Unit(key, label, "drives", stem, hib, fmt, weight, reason=_DRIVE_REASON, dp=dp)


# (concept key, row label, candidates; the first is the default)
UNIT_GROUPS: tuple[tuple[str, tuple[tuple[str, str, tuple[Unit, ...]], ...]], ...] = (
    ("Efficiency", (
        ("sr", "Success rate", (
            _adv("sr", "Success rate", "successRate", True, "pct"),
            _adv("sr_std", "Standard-downs SR", "standardDowns_successRate", True, "pct"),
            _adv("sr_pass_downs", "Passing-downs SR", "passingDowns_successRate", True, "pct"))),
        ("ppa", "PPA per play", (
            _adv("ppa", "PPA per play", "ppa", True, "signed", 3),
            _ppa("ppa_games", "PPA per play (PPA feed)", "overall"))),
        ("expl", "Explosiveness", (
            _adv("expl", "Explosiveness", "explosiveness", True, "num", 3),
            _adv("expl_std", "Standard-downs explosiveness", "standardDowns_explosiveness", True, "num", 3),
            _adv("expl_pass_downs", "Passing-downs explosiveness", "passingDowns_explosiveness", True, "num", 3))),
    )),
    ("Rushing", (
        ("rush", "Rushing efficiency", (
            _adv("rush_ppa", "Rushing PPA", "rushingPlays_ppa", True, "signed", 3),
            _adv("rush_sr", "Rushing success rate", "rushingPlays_successRate", True, "pct"),
            _ppa("rush_ppa_games", "Rushing PPA (PPA feed)", "rushing"))),
        ("line_yards", "Line yards", (_adv("line_yards", "Line yards", "lineYards", True, "num", 2),)),
        ("second_level", "Second-level yards", (_adv("second_level", "Second-level yards", "secondLevelYards", True, "num", 2),)),
        ("open_field", "Open-field yards", (_adv("open_field", "Open-field yards", "openFieldYards", True, "num", 2),)),
        ("power", "Power success", (_adv("power", "Power success", "powerSuccess", True, "pct"),)),
        ("stuff", "Stuff rate", (_adv("stuff", "Stuff rate", "stuffRate", False, "pct"),)),
    )),
    ("Passing", (
        ("pass", "Passing efficiency", (
            _adv("pass_ppa", "Passing PPA", "passingPlays_ppa", True, "signed", 3),
            _adv("pass_sr", "Passing success rate", "passingPlays_successRate", True, "pct"),
            _ppa("pass_ppa_games", "Passing PPA (PPA feed)", "passing"))),
        ("pass_expl", "Passing explosiveness", (
            _adv("pass_expl", "Passing explosiveness", "passingPlays_explosiveness", True, "num", 3),)),
    )),
    ("PPA by down", (
        ("ppa_1", "1st down PPA", (_ppa("ppa_1", "1st down PPA", "firstDown"),)),
        ("ppa_2", "2nd down PPA", (_ppa("ppa_2", "2nd down PPA", "secondDown"),)),
        ("ppa_3", "3rd down PPA", (_ppa("ppa_3", "3rd down PPA", "thirdDown"),)),
    )),
    ("Havoc", (
        ("havoc", "Havoc rate", (
            Unit("havoc", "Havoc rate", "havoc", "havocRate", False, "pct", "totalPlays", reason=_HAVOC_REASON),
            Unit("havoc_f7", "Front-seven havoc", "havoc", "frontSevenHavocRate", False, "pct", "totalPlays", reason=_HAVOC_REASON),
            Unit("havoc_db", "DB havoc", "havoc", "dbHavocRate", False, "pct", "totalPlays", reason=_HAVOC_REASON))),
    )),
    ("Drives", (
        ("ppd", "Points per drive", (_drv("ppd", "Points per drive", "ppd", True, "num"),)),
        ("so_rate", "Scoring-opportunity rate", (_drv("so_rate", "Scoring-opportunity rate", "so_rate", True, "pct"),)),
        ("start", "Avg start (yards to goal)", (_drv("start", "Avg start (yards to goal)", "start", False, "num", dp=1),)),
        ("plays_per_drive", "Plays per drive", (_drv("plays_per_drive", "Plays per drive", "plays_per_drive", None, "num", dp=1),)),
        ("sec_per_play", "Seconds per play (pace)", (_drv("sec_per_play", "Seconds per play (pace)", "sec_per_play", None, "num", "plays", dp=1),)),
    )),
)

UNITS: tuple[Unit, ...] = tuple(u for _, rows in UNIT_GROUPS for _, _, cands in rows for u in cands)


def edge(a: float | None, b: float | None, higher_is_better: bool | None) -> str | None:
    """Which side a stat row favours: "a", "b", or None for no marker.

    Every stat row on the page renders its edge marker from this one function, for ratings,
    unit matchups, PFF grades and special teams alike, so a stat's values can be a 0-1 rate
    (success rate 0.452), a rating (SP+ 18.3) or a count (Elo 1712).
    """
    if a is None or b is None or higher_is_better is None:
        return None
    # ponytail: one 1% relative band with a 0.001 floor for every scale; give a Stat its own
    # tolerance if a row's ties read wrong (the floor keeps near-zero PPA from flipping on noise).
    if abs(a - b) <= max(0.01 * max(abs(a), abs(b)), 1e-3):
        return None
    return "a" if (a > b) == higher_is_better else "b"
