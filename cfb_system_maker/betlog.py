"""Action Network bet-history CSV import: parsing, filtering, and matching
bets to CFBD games. See docs/superpowers/specs/2026-08-27-clv-betlog-ingestion-design.md.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from cfb_system_maker.models import GameRecord
from cfb_system_maker.team_abbreviations import resolve_team

_IN_SCOPE_TYPES = {"spread_home", "spread_away", "over", "under"}
_IN_SCOPE_PERIOD = "game"
_EXPECTED_FIELD_COUNT = 14


@dataclass(frozen=True)
class RawBetRow:
    league: str
    start_time: str
    game: str
    bet_type: str
    side: str
    line_taken: float
    odds: int
    result: str
    units_wagered: float
    units_net: float


@dataclass(frozen=True)
class ParsedImport:
    in_scope: list[RawBetRow]
    out_of_scope_count: int
    malformed_count: int


@dataclass(frozen=True)
class BetLogRecord:
    game_id: int
    date: str
    home_team: str
    away_team: str
    bet_type: str  # "spread" | "total"
    side: str  # "home" | "away" | "over" | "under"
    line_taken: float
    odds: int
    result: str
    units_wagered: float
    units_net: float


def parse_betlog_csv(path: str | Path) -> ParsedImport:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    # Real exports have a stray `data:text/csv;charset=utf-8,` artifact line
    # before the real header. Detect and skip it if present.
    start = 0
    if lines and lines[0].strip().startswith("data:text/csv"):
        start = 1

    reader = csv.reader(lines[start:])
    header = next(reader)
    if len(header) != _EXPECTED_FIELD_COUNT:
        raise ValueError(f"unexpected header shape: {header!r}")

    in_scope: list[RawBetRow] = []
    out_of_scope = 0
    malformed = 0

    for raw_row in reader:
        if len(raw_row) != _EXPECTED_FIELD_COUNT:
            malformed += 1
            continue
        row = dict(zip(header, raw_row))
        if row.get("League") != "ncaaf":
            out_of_scope += 1
            continue
        bet_type = row.get("Type", "")
        period = row.get("Period", "")
        if bet_type not in _IN_SCOPE_TYPES or period != _IN_SCOPE_PERIOD:
            out_of_scope += 1
            continue
        try:
            line_taken = float(row["Odds/Spread/Total"])
            odds = int(float(row["Odds"]))
            units_wagered = float(row["Units Wagered"])
            units_net = float(row["Units Net"])
        except (KeyError, ValueError):
            malformed += 1
            continue
        in_scope.append(
            RawBetRow(
                league=row["League"],
                start_time=row["Start Time"],
                game=row["Game"],
                bet_type=bet_type,
                side=bet_type,  # side derived properly in match_to_game
                line_taken=line_taken,
                odds=odds,
                result=row.get("Result", ""),
                units_wagered=units_wagered,
                units_net=units_net,
            )
        )

    return ParsedImport(in_scope=in_scope, out_of_scope_count=out_of_scope, malformed_count=malformed)


def _split_game_field(game: str) -> tuple[str, str] | None:
    """'NAVY @ ND' -> ('NAVY', 'ND') meaning (away, home)."""
    parts = [p.strip() for p in game.split("@")]
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def match_to_game(row: RawBetRow, games_by_date: dict[str, list[GameRecord]]) -> BetLogRecord | None:
    teams = _split_game_field(row.game)
    if teams is None:
        return None
    away_short, home_short = teams
    away_cfbd = resolve_team(away_short)
    home_cfbd = resolve_team(home_short)
    if away_cfbd is None or home_cfbd is None:
        return None

    date = row.start_time[:10]  # "2023-08-26T23:00:00.000Z" -> "2023-08-26"
    candidates = games_by_date.get(date, [])
    game = next(
        (g for g in candidates if g.home_team == home_cfbd and g.away_team == away_cfbd),
        None,
    )
    if game is None:
        return None

    if row.bet_type in ("spread_home", "spread_away"):
        bet_type = "spread"
        side = "home" if row.bet_type == "spread_home" else "away"
    else:
        bet_type = "total"
        side = row.bet_type  # "over" | "under"

    return BetLogRecord(
        game_id=game.game_id,
        date=date,
        home_team=home_cfbd,
        away_team=away_cfbd,
        bet_type=bet_type,
        side=side,
        line_taken=row.line_taken,
        odds=row.odds,
        result=row.result,
        units_wagered=row.units_wagered,
        units_net=row.units_net,
    )
