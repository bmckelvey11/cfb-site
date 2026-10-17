"""Polymarket table shapes and name resolution, shared by the flatten and the loader.

Same reason `oddsapi_schema.py` exists: types are pinned rather than sniffed (`line` is
empty on every moneyline row), and the flatten and `duckdb_load._plan_loads` have to
agree on them.
"""

from __future__ import annotations

from cfb_system_maker.oddsapi_schema import norm

PM_TABLES: tuple[str, ...] = ("pm_market_tick", "pm_snapshot")

_VARCHAR = frozenset({
    "event_id", "event_slug", "pm_game_id", "home_team", "away_team", "home_school",
    "away_school", "market_id", "market_slug", "market", "side", "outcome_name",
    "sport", "series_id", "market_types", "_source_file",
})
_TIMESTAMP = frozenset({"pulled_at", "start_time", "updated_at"})
_DOUBLE = frozenset({"line", "price", "best_bid", "best_ask", "last_trade_price",
                     "liquidity", "volume"})
_BOOLEAN = frozenset({"accepting_orders"})


def column_type(name: str) -> str:
    if name in _VARCHAR:
        return "VARCHAR"
    if name in _TIMESTAMP:
        return "TIMESTAMP WITH TIME ZONE"
    if name in _DOUBLE:
        return "DOUBLE"
    if name in _BOOLEAN:
        return "BOOLEAN"
    return "INTEGER"          # pages, events_seen, event_count, market_count


def column_types(header: list[str]) -> dict[str, str]:
    """Positional: `read_csv`'s `columns` maps by order, so this follows the header."""
    return {c: column_type(c) for c in header}


# Polymarket names teams by school (`teams[].alias`, "Georgia State"), with no mascot, so
# there is no mascot strip here -- stripping a token off a school name is how "Georgia
# State" would quietly become "Georgia". Add a line when a name shows up unresolved.
# Keys and values are both `norm()`ed. The 14 below were unresolved in the first live pull
# (2026-10-17) and were checked against `teams_2025.json`/`teams_2026.json` by school id.
ALIASES: dict[str, str] = {
    "appalachian state": "app state",
    "central connecticut state": "central connecticut",
    "grambling state": "grambling",
    "liu": "long island university",
    "louisiana monroe": "ul monroe",
    "miami fl": "miami",                    # CFBD's plain `Miami`; `Miami (OH)` is its own
    "nicholls state": "nicholls",
    "penn": "pennsylvania",                 # the Quakers, not Penn State
    "southeastern louisiana": "se louisiana",
    "southern university": "southern",
    "st thomas": "st thomas mn",
    "tennessee martin": "ut martin",
    "umass": "massachusetts",
    "university at albany": "ualbany",
}


def school_key(name: str) -> str:
    key = norm(name)
    return ALIASES.get(key, key)
