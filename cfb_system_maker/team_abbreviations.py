"""Action Network team short-name -> CFBD full team-name map.

Action Network's bet-history CSV export uses short team names/abbreviations
in its free-text `Game` column (e.g. "NAVY @ ND"). CFBD's `GameRecord.home_team`
/`away_team` use full names (e.g. "Notre Dame"). This map bridges the two so
imported bets can be joined to a CFBD game_id.

Grows incrementally: `betlog import` reports any Game-column team name it
can't resolve, and you add it here once you've confirmed the correct CFBD
name (usually via games.csv for that date).
"""

from __future__ import annotations

AN_TO_CFBD: dict[str, str] = {
    "NAVY": "Navy",
    "ND": "Notre Dame",
    "OHIO": "Ohio",
    "SDSU": "San Diego State",
    "MASS": "Massachusetts",
    "NMSU": "New Mexico State",
    "GB": "Green Bay",
    "DAL": "Dallas",
    "HOU": "Houston",
    "LA": "Los Angeles",
    "LAC": "Los Angeles Chargers",
    "WAS": "Washington",
}


def resolve_team(an_name: str) -> str | None:
    """Look up an Action Network team short name. Returns None if unknown."""
    return AN_TO_CFBD.get(an_name.strip())
