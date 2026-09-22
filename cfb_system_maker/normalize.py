from __future__ import annotations

import math
from typing import Any

from cfb_system_maker.models import GameRecord


def normalize_games(
    games: list[dict[str, Any]],
    betting_games: list[dict[str, Any]],
    *,
    provider: str | None = None,
) -> list[GameRecord]:
    """Build graded game records against the *median* line across books.

    ``provider`` is accepted and ignored: the system builder no longer grades against
    one book. Kept in the signature so existing callers (cli, upcoming, tests) are not
    all rewritten for an argument that now has no effect; ``duckdb_core`` still selects
    per book for the warehouse, which is where per-book truth (and CLV) lives.
    """
    lines_by_id = {_game_id(row): row for row in betting_games if _game_id(row) is not None}
    normalized: list[GameRecord] = []

    for game in games:
        game_id = _game_id(game)
        if game_id is None:
            continue
        betting_game = lines_by_id.get(game_id, {})
        selected_line = median_line(betting_game.get("lines", []))
        if selected_line is None:
            continue

        normalized.append(
            GameRecord(
                game_id=game_id,
                season=int(_first(game, "season")),
                week=int(_first(game, "week")),
                home_team=str(_first(game, "homeTeam", "home_team", fallback=_first(betting_game, "homeTeam", "home_team"))),
                away_team=str(_first(game, "awayTeam", "away_team", fallback=_first(betting_game, "awayTeam", "away_team"))),
                home_conference=_first(game, "homeConference", "home_conference", fallback=_first(betting_game, "homeConference", "home_conference")),
                away_conference=_first(game, "awayConference", "away_conference", fallback=_first(betting_game, "awayConference", "away_conference")),
                home_points=_optional_int(_first(game, "homePoints", "home_points", "homeScore", "home_score", fallback=_first(betting_game, "homeScore", "home_score"))),
                away_points=_optional_int(_first(game, "awayPoints", "away_points", "awayScore", "away_score", fallback=_first(betting_game, "awayScore", "away_score"))),
                provider=MEDIAN_PROVIDER,
                spread=_optional_float(_first(selected_line, "spread")),
                total=_optional_float(_first(selected_line, "overUnder")),
                season_type=str(_first(game, "seasonType", "season_type",
                                       fallback=_first(betting_game, "seasonType", "season_type",
                                                       fallback="regular"))),
            )
        )

    return normalized


# CFBD emits DraftKings under two spellings **in the same `lines` array**, on 215 games.
# Measured 2026-09-10: `Draft Kings` is strictly a degraded duplicate -- it never carries a
# value `DraftKings` lacks, while `DraftKings` supplies 161 `spreadOpen`, 121
# `overUnderOpen` and ~185 moneylines the other leaves null. One book, two names.
#
# Owned here rather than in `duckdb_core` because this module is where a provider row is
# chosen; `duckdb_core._provider_key` delegates to `provider_key` below, so `games.csv`,
# `core.fact_game`, `core.fact_game_line` and `enrich`'s line-move index cannot disagree
# about what a book is called or which of its rows is the real one.
#
# Deliberately NOT extended to the Caesars family -- `Caesars`, `Caesars (Pennsylvania)`
# and `Caesars Sportsbook (Colorado)` never share a game and hold disjoint season ranges,
# consistent with either a rename history or separate state licences. Nothing measured
# settles which, and merging on a guess destroys the distinction irreversibly.
PROVIDER_ALIASES = {"draft kings": "draftkings"}


def provider_key(value: Any) -> str | None:
    """The canonical lowercase key for a vendor provider string."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    return PROVIDER_ALIASES.get(text, text)


MEDIAN_PROVIDER = "median"


def _book_rows(usable: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per *book*, not per array entry.

    CFBD posts the same book twice in one array (`DraftKings` / `Draft Kings`, and the
    Caesars family), so a median taken over raw rows double-weights whichever book
    happens to be duplicated. Collapsing on ``provider_key`` first -- keeping that
    book's most complete row, the same rule ``_best_of_book`` applies -- makes the
    median one-book-one-vote.
    """
    best: dict[str, dict[str, Any]] = {}
    for line in usable:
        key = provider_key(line.get("provider"))
        if key is None:
            continue
        if key not in best or _line_values(line) > _line_values(best[key]):
            best[key] = line
    return list(best.values())


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _snap_to_half(value: float) -> float:
    """Nearest half point.

    An even number of books averages to quarters (-6.5 and -7 -> -6.75), which no book
    posts and which can never push. Leaving them unsnapped would quietly delete pushes
    from every backtest, so the median is put back on a bettable number.

    Ties (a .25 exactly between two half points) go away from zero, so -6.75 -> -7.0 and
    +6.75 -> +7.0. Deliberately not ``round``: its banker's rounding sends a tie to
    whichever neighbour happens to be even, which is asymmetric between a home and an
    away price for the same game.
    """
    sign = -1.0 if value < 0 else 1.0
    return sign * math.floor(abs(value) * 2 + 0.5) / 2


def _median_of(rows: list[dict[str, Any]], *keys: str) -> float | None:
    values = []
    for row in rows:
        raw = _first(row, *keys)
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    median = _median(values)
    return None if median is None else _snap_to_half(median)


def median_line(lines: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A synthetic line: the median across books of each number, snapped to a half point.

    Each number is medianed over the books that posted *that* number, so the spread and
    the total may rest on different book sets -- and so may an open and its close. That
    is deliberate: the alternative is dropping a game because one book withheld one
    value. Opens are medianed the same way so ``enrich``'s move features compare
    median-open against median-close rather than mixing constructions.
    """
    usable = [
        line
        for line in lines
        if line.get("spread") is not None or _first(line, "overUnder", "over_under") is not None
    ]
    rows = _book_rows(usable)
    if not rows:
        return None

    line = {
        "provider": MEDIAN_PROVIDER,
        "book_count": len(rows),
        "spread": _median_of(rows, "spread"),
        "overUnder": _median_of(rows, "overUnder", "over_under", "total"),
        "spreadOpen": _median_of(rows, "spreadOpen", "spread_open"),
        "overUnderOpen": _median_of(rows, "overUnderOpen", "over_under_open", "total_open"),
    }
    if line["spread"] is None and line["overUnder"] is None:
        return None
    return line


def _line_values(line: dict[str, Any]) -> int:
    """How many of the six line numbers this row actually carries."""
    return sum(
        1
        for keys in (
            ("spread",),
            ("spreadOpen", "spread_open"),
            ("overUnder", "over_under", "total"),
            ("overUnderOpen", "over_under_open", "total_open"),
            ("homeMoneyline", "home_moneyline"),
            ("awayMoneyline", "away_moneyline"),
        )
        if _first(line, *keys) is not None
    )


def _best_of_book(lines: list[dict[str, Any]], chosen: dict[str, Any]) -> dict[str, Any]:
    """The most complete row for the *same book* as ``chosen``.

    Which book gets selected is untouched -- only which of that book's duplicate rows is
    read. Without this the choice is array order, so the degraded `Draft Kings` twin wins
    roughly half the time and its nulls become a null line-move feature for a game whose
    open is sitting in the same payload.
    """
    key = provider_key(chosen.get("provider"))
    if key is None:
        return chosen
    best = chosen
    for line in lines:
        if line is chosen or provider_key(line.get("provider")) != key:
            continue
        if _line_values(line) > _line_values(best):
            best = line
    return best


def _select_line(lines: list[dict[str, Any]], provider: str | None) -> dict[str, Any] | None:
    usable = [line for line in lines if line.get("spread") is not None or _first(line, "overUnder", "over_under") is not None]
    if not usable:
        return None
    if provider:
        wanted = provider_key(provider)
        for line in usable:
            if provider_key(line.get("provider")) == wanted:
                return _best_of_book(usable, line)
    return _best_of_book(usable, usable[0])


def _select_total(lines: list[dict[str, Any]], selected_line: dict[str, Any]) -> dict[str, Any]:
    # If the spread-selected line has no total, fall back to the FIRST sibling
    # line (original order) that has one. This picks the first available total
    # across providers, not necessarily the spread's provider — provider
    # precedence for totals may be revisited later (e.g. preferring a specific
    # provider's total the way spread does).
    if _first(selected_line, "overUnder", "over_under", "total") is not None:
        return selected_line
    for line in lines:
        if _first(line, "overUnder", "over_under", "total") is not None:
            return line
    return selected_line


def _game_id(row: dict[str, Any]) -> int | None:
    value = _first(row, "id", "gameId", "game_id")
    return int(value) if value is not None else None


def _first(row: dict[str, Any], *keys: str, fallback: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return fallback


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None

