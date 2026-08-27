"""Action Network bet-history CSV import: parsing, filtering, and matching
bets to CFBD games. See docs/superpowers/specs/2026-08-27-clv-betlog-ingestion-design.md.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from cfb_system_maker.models import GameRecord
from cfb_system_maker.storage import load_raw_json
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


_BETLOG_FIELDS = [
    "game_id", "date", "home_team", "away_team", "bet_type", "side",
    "line_taken", "odds", "result", "units_wagered", "units_net",
]


@dataclass(frozen=True)
class ImportSummary:
    total_rows: int
    in_scope: int
    already_imported: int
    newly_imported: int
    matched: int
    unmatched: list[str]
    malformed: int


def _dedupe_key(bet: BetLogRecord) -> tuple:
    return (bet.date, bet.home_team, bet.away_team, bet.bet_type, bet.side, bet.odds)


def load_betlog(data_dir: str | Path) -> list[BetLogRecord]:
    path = Path(data_dir) / "betlog" / "bets.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [
            BetLogRecord(
                game_id=int(row["game_id"]),
                date=row["date"],
                home_team=row["home_team"],
                away_team=row["away_team"],
                bet_type=row["bet_type"],
                side=row["side"],
                line_taken=float(row["line_taken"]),
                odds=int(row["odds"]),
                result=row["result"],
                units_wagered=float(row["units_wagered"]),
                units_net=float(row["units_net"]),
            )
            for row in reader
        ]


def save_betlog(records: list[BetLogRecord], data_dir: str | Path) -> None:
    directory = Path(data_dir) / "betlog"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "bets.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_BETLOG_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "game_id": record.game_id, "date": record.date,
                    "home_team": record.home_team, "away_team": record.away_team,
                    "bet_type": record.bet_type, "side": record.side,
                    "line_taken": record.line_taken, "odds": record.odds,
                    "result": record.result, "units_wagered": record.units_wagered,
                    "units_net": record.units_net,
                }
            )


def _build_games_by_date(data_dir: str | Path, in_scope: list[RawBetRow]) -> dict[str, list[GameRecord]]:
    # CFBD's games_{season}.json files are keyed by CFBD season, not calendar
    # year: a January bowl/CFP game dated e.g. "2024-01-08" belongs to the 2023
    # season's file. Always check both the bet's calendar year and the year
    # before it -- a season file that turns out not to have the game is
    # already safely absorbed by the FileNotFoundError handling below.
    bet_years = {int(row.start_time[:4]) for row in in_scope}
    seasons_needed = bet_years | {year - 1 for year in bet_years}
    games_by_date: dict[str, list[GameRecord]] = {}
    for season in seasons_needed:
        try:
            raw_games = load_raw_json(data_dir, "games", season)
        except FileNotFoundError:
            continue
        for raw in raw_games:
            date = str(raw.get("startDate", ""))[:10]
            if not date:
                continue
            games_by_date.setdefault(date, []).append(
                GameRecord(
                    game_id=raw["id"], season=season, week=raw.get("week", 0),
                    home_team=raw.get("homeTeam", ""), away_team=raw.get("awayTeam", ""),
                    home_conference=raw.get("homeConference"), away_conference=raw.get("awayConference"),
                    home_points=raw.get("homePoints"), away_points=raw.get("awayPoints"),
                    provider=None, spread=None, total=None,
                )
            )
    return games_by_date


def import_betlog(csv_path: str | Path, data_dir: str | Path) -> ImportSummary:
    parsed = parse_betlog_csv(csv_path)
    total_rows = len(parsed.in_scope) + parsed.out_of_scope_count + parsed.malformed_count

    games_by_date = _build_games_by_date(data_dir, parsed.in_scope)

    existing = load_betlog(data_dir)
    existing_keys = {_dedupe_key(bet) for bet in existing}

    matched_bets: list[BetLogRecord] = []
    unmatched: list[str] = []
    for row in parsed.in_scope:
        bet = match_to_game(row, games_by_date)
        if bet is None:
            unmatched.append(f"{row.start_time[:10]} {row.game}")
            continue
        matched_bets.append(bet)

    seen_keys = set(existing_keys)
    new_bets: list[BetLogRecord] = []
    for bet in matched_bets:
        key = _dedupe_key(bet)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        new_bets.append(bet)
    already_imported = len(matched_bets) - len(new_bets)

    save_betlog(existing + new_bets, data_dir)

    return ImportSummary(
        total_rows=total_rows,
        in_scope=len(parsed.in_scope),
        already_imported=already_imported,
        newly_imported=len(new_bets),
        matched=len(matched_bets),
        unmatched=unmatched,
        malformed=parsed.malformed_count,
    )
