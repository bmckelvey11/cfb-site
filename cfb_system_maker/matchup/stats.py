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
