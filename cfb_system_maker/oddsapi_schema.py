"""One rule, three readers: the-odds-api table shapes and name resolution.

`scripts/oddsapi_flatten.py` writes the CSVs, `duckdb_load._plan_loads` loads them, and the
two audit scripts resolve vendor names the same way a load must. Keeping the rules here is
what stops those drifting apart -- the same reason `pff_schema.py` exists.

Types are pinned rather than sniffed. `read_csv_auto` would type a column from whichever
file it read first, and `line` is empty on every `h2h` row, so a snapshot with no spreads
or totals would type it VARCHAR and the next load would refuse.
"""

from __future__ import annotations

import re
import unicodedata

# Pinned by hand so a table that stops being written fails loudly rather than silently.
OA_TABLES: tuple[str, ...] = ("oa_odds_tick", "oa_snapshot")

_VARCHAR = frozenset({
    "event_id", "home_team", "away_team", "home_school", "away_school",
    "book", "book_title", "market", "side",
    "outcome_name", "sport", "regions", "markets", "odds_format", "_source_file",
})
_TIMESTAMP = frozenset({"pulled_at", "commence_time", "last_update"})
_DOUBLE = frozenset({"line"})


def column_type(name: str) -> str:
    if name in _VARCHAR:
        return "VARCHAR"
    if name in _TIMESTAMP:
        return "TIMESTAMP WITH TIME ZONE"
    if name in _DOUBLE:
        return "DOUBLE"
    return "INTEGER"          # odds, requests_*, event_count


def column_types(header: list[str]) -> dict[str, str]:
    """Positional: `read_csv`'s `columns` maps by order, so this follows the header."""
    return {c: column_type(c) for c in header}


# ---------------------------------------------------------------- name resolution

# Mascots are one or two trailing tokens ("Hurricanes", "Thundering Herd"). Mirrors
# `OA_MAX_MASCOT_TOKENS` in research/spread/scripts/weekly_slate.py.
MAX_MASCOT_TOKENS = 2

# The only three snapshot names with no `core.dim_team` row under a mascot strip, measured
# 2026-09-10 -- see docs/oddsapi-team-name-join-2026-09-10.md. Grows the way OA_ALIASES
# does: add a line when a name shows up unresolved.
ALIASES = {
    "appalachian state": "app state",
    "southern mississippi": "southern miss",
    "umass": "massachusetts",
}


def norm(name: str) -> str:
    """Casefold, fold accents, delete apostrophes, drop other punctuation to spaces.

    The two rules that are not obvious are both CFBD spellings: `San José State` needs the
    accent folded rather than blanked (else "san jos state"), and `Hawai'i` needs the
    apostrophe *deleted* rather than turned into a space (else "hawai i", which never meets
    "hawaii"). Both presented as vendor gaps before they were understood as normalizer bugs.
    """
    folded = unicodedata.normalize("NFKD", str(name).lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c)).replace("'", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", folded)).strip()


def candidates(name: str) -> list[str]:
    """Every head the mascot strip would try, longest first, aliases applied.

    Longest-first is what keeps "Miami (OH) RedHawks" off "miami".
    """
    parts = str(name).split()
    out = []
    for cut in range(len(parts), max(0, len(parts) - MAX_MASCOT_TOKENS) - 1, -1):
        head = norm(" ".join(parts[:cut]))
        out.append(head)
        if head in ALIASES:
            out.append(ALIASES[head])
    return out
