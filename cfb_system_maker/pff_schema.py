"""The pinned column types for the `stg.pff_*` tables, and the table list.

One source of truth for two readers: `scripts/pff_flatten.py`, which writes the CSVs, and
`duckdb_load._plan_loads`, which loads them. The Action Network pin
(`duckdb_load._AN_TICK_COLUMNS`) enumerates fifteen columns by hand; that does not scale to
twenty-one PFF tables of roughly thirty columns each, and a second hand-typed copy is how
the AN pin drifted once already. So the *table list* is pinned by hand -- a table that
stops being written is then a visible failure -- and the *types* come from a rule applied
to the header.

The rule exists because nothing may be inferred from the values. PFF declares one column
`integer` on a whole number and `number` otherwise, in the same column across two
responses (320 such columns in the 2025 pull), so `read_csv_auto` would type a table from
whichever file it happened to read first. See docs/pff-warehouse-schema.md §5b.
"""

from __future__ import annotations

import re

# Written by scripts/pff_flatten.py. Dimensions first, then facts small-to-large, so a
# failure shows up on a 341-row table rather than a 313k-row one.
PFF_TABLES = (
    "pff_franchise", "pff_player_season",
    "pff_field_goal", "pff_punting", "pff_kickoff", "pff_passing_allowed_pressure",
    "pff_team_pass_block_week", "pff_return", "pff_rushing", "pff_rushing_direction",
    "pff_blocking_alignment", "pff_offense_summary", "pff_defense_run",
    "pff_pass_blocking", "pff_defense_summary", "pff_special_teams",
    "pff_passing", "pff_defense_coverage", "pff_run_blocking", "pff_defense_pass_rush",
    "pff_receiving",
)

# A rate, a grade or an average is fractional even when this week's value happens to be
# whole. Everything else PFF reports is a count.
_DOUBLE = re.compile(r"(^grades_|_percent$|_rate$|^ypa$|_ypa$|^epa$|_epa$|^pbe$|^prp$|"
                     r"_diff$|^qb_rating|_per_|^yards_per_|^avg_|^yco_attempt$|"
                     r"^elusive_rating$|^pass_block_efficiency$)")
_VARCHAR = frozenset({"player", "position", "team_name", "split", "direction",
                      "jersey_number", "kind", "slug", "match"})
_INTEGER = frozenset({"season", "week", "player_id", "franchise_id", "cfbd_team_id",
                      "draft_season", "eligible_season"})


def column_type(column: str) -> str:
    """The pinned DuckDB type for one column name."""
    if column in _VARCHAR:
        return "VARCHAR"
    if column in _INTEGER:
        return "INTEGER"
    if column == "pulled_at":
        return "DATE"
    return "DOUBLE" if _DOUBLE.search(column) else "INTEGER"


def column_types(header: list[str]) -> dict[str, str]:
    """The pin for one table, from the header the flattener wrote."""
    return {column: column_type(column) for column in header}
