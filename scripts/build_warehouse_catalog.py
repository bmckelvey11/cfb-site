"""Regenerate the `const DATA = {...}` block in docs/cfb-warehouse-catalog.html.

The catalog's HTML/CSS/JS shell is hand-written; only the embedded DATA
literal is machine-generated. Everything in DATA is derived from the live
DuckDB plus the loader's own GraphQL destination maps and the PFF_GLOSSARY /
CORE_NOTES tables below -- nothing is carried forward from the previous render
except the two genuinely editorial fields (`domainOrder` copy and `coreNote`
prose), which are seeded from the file and reported when a new table has no
entry. `grain` is *computed*, not editorial: it is a per-table uniqueness
check over the candidate key columns, overridden with CORE_NOTES prose for
core tables so the Tables pane has one field to read regardless of schema.

Derivation rules, recovered from the 2026-08-29 hand-built catalog and pinned by
tests/test_warehouse_catalog.py:

* origin `o`   core/meta by schema; `an_*` -> Action Network; a `raw`/`stg` name
                that is a GraphQL destination (`GQL_ENTITY_TO_RAW` /
                `GQL_ENTITY_TO_STG`) -> GraphQL; everything else REST. The old
                `graphql` schema is gone (ADR-0003, collapsed 2026-09-10), so
                origin is the only surviving record of transport.
* wstats       numeric/boolean columns that are not keys or calendar grain.
                BOOLEAN -> `flag`, the rest -> `stat`.
* `ns` / `nn`  count of `stat` wstats / count of JSON+nested columns.
* named        the four long-format stat vocabularies, counted in place.

Usage: python scripts/build_warehouse_catalog.py [--check]

`--check` renders and diffs without writing -- exit 1 if the file is stale.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cfb_paths  # noqa: E402
from cfb_system_maker.graphql_client import (  # noqa: E402
    GQL_ENTITY_TO_RAW,
    GQL_ENTITY_TO_STG,
)

CATALOG = Path(__file__).resolve().parents[1] / "docs" / "cfb-warehouse-catalog.html"

# Grain prose for the Kimball core. Editorial, so it lives here rather than
# being guessed from column names; `--check` names any core table missing one.
CORE_NOTES = {
    "dim_team": "School / classification / FBS flag",
    "dim_conference": "Name, abbreviation, classification",
    "dim_venue": "City, dome, grass, capacity, elevation",
    "dim_week": "Season × week × season_type calendar",
    "dim_lines_provider": "Book key (consensus, draftkings, …)",
    "dim_coach": "Coach identity: id + first / last name",
    "dim_draft_pick": "NFL draft pick: round, overall, college and NFL team",
    "dim_recruit": "Recruit identity, stars / rating, commitment",
    "fact_game": "One row per game; selected spread/total + scores",
    "fact_game_historical": "Pre-2001 games from the GraphQL historical feed",
    "fact_game_line": "Per-book open/close spread, total, moneylines",
    "fact_game_odds": "Odds API ticks: one row per book × market × side × pull",
    "fact_game_team": "Entering-game running W% / ATS / streaks",
    "fact_coach_season": "Coach × team × season record, SP+/SRS, ranks",
    "fact_team_talent": "247 composite team talent by season",
    "dim_athlete": "Athlete identity: team, position, jersey, height / weight",
    "dim_position": "Player position code and display name",
    "dim_recruit_position": "Recruit position code and its position group",
    "dim_draft_position": "NFL draft position code",
    "dim_draft_team": "NFL franchise (not a CFB team)",
    "dim_play_type": "Play type code and text",
    "dim_play_stat_type": "Play-stat type code",
    "dim_poll_type": "Poll code (AP, Coaches, CFP, …)",
    "dim_weather_condition": "Weather condition code and description",
    "dim_stat_category": "Box-score stat category vocabulary",
    "fact_team_season_rating_postgame": (
        "Season × team: SP+, SRS, Elo, FPI, GraphQL ratings, core_ratings, PPA "
        "and adjusted EPA, prefixed by source"
    ),
    "fact_team_season_record_postgame": (
        "Season × team: W/L/T by home, away, neutral, conference, postseason"
    ),
    "fact_team_ats_postgame": "Season × team: ATS record and average cover margin",
    "fact_team_recruiting": "Season × team: recruiting class points and rank",
    "fact_team_returning_production": "Season × team: returning usage and PPA share",
    "fact_game_weather": "Game weather, GraphQL and REST feeds merged",
    "fact_poll_rank": "Poll ballot: season × week × poll × team, rank and points",
    "fact_drive_postgame": "One drive: result, yards, plays, start/end field position",
    "coach_name_conflicts": "Audit: one name, several coach ids",
    "coach_season_unmatched": "Audit: coach seasons that would not join",
    "fact_game_line_conflicts": "Audit: REST and GraphQL disagree on a line",
    "game_projections": "Per-site projected spread and total (teamrankings, numberfire)",
}

DATA_SPAN = re.compile(r"(const DATA = \{)(.*?)(\n      \};)", re.S)

# Columns that are numeric but identify or slice a row rather than measure it.
# Recovered from the hand-built catalog: every numeric column it left out of
# wstats matches one of these.
KEY_NAMES = frozenset({"season", "year", "week", "id"})
KEY_SUFFIXES = ("_id", "Id", "ID")
# Kickoff clock parts and the TBD flag are grain, not measurements.
KEY_EXTRA = frozenset(
    {"startTimeTbd", "startTimeTBD", "startTime_minutes", "startTime_seconds"}
)

NUMERIC = frozenset(
    {
        "BIGINT", "UBIGINT", "HUGEINT", "UHUGEINT", "INTEGER", "UINTEGER",
        "SMALLINT", "USMALLINT", "TINYINT", "UTINYINT", "DOUBLE", "FLOAT", "REAL",
    }
)

# Only these carry a NaN state distinct from NULL in DuckDB.
FLOATY = frozenset({"DOUBLE", "FLOAT", "REAL"})

# PFF column-name patterns -> plain-language definitions, sourced from
# docs/pff-methodology-research.md. Checked most-specific-first against
# whole name tokens (see `_tokens`). Where the source doc says a formula
# is not public, the entry says that rather than guessing at one --
# `report()` below never lets a paraphrase stand in for a disclosed number.
PFF_GLOSSARY = [
    (
        "grade",
        "PFF grade (0-100)",
        "Play-by-play grades on a -2..+2 scale (0.5 increments, 0 = expected), "
        "transformed into a 0-100 game/season summary. PFF has not published the "
        "conversion, aggregation weighting, or an opponent-adjustment formula for "
        "the headline number.",
        "PFF grades",
    ),
    (
        "snap_count",
        "Charted snap count",
        "Snaps the player was on the field for, by role/split. Denominator for "
        "most of the rate stats below.",
        "PFF signature stats",
    ),
    (
        "avg_ttt", "Time to throw (by split)",
        "Average time-to-throw broken out by what happened on the dropback "
        "(attempts / sacks / scrambles) -- not a count of that event itself. "
        "See the plain `time_to_throw` entry below.",
        "PFF signature stats",
    ),
    (
        "pressure",
        "Pressure (charted)",
        "A charted pass-rush disruption (sack, hit, or hurry). Rate = pressures / "
        "pass-rush (or pass-block) opportunities. Definition and blocking-fault "
        "attribution are PFF charting judgments, not measured from tracking data.",
        "PFF signature stats",
    ),
    (
        "def_gen_pressure",
        "Pressures generated (defense)",
        "Charted pressures generated by the defender's pass rush.",
        "PFF signature stats",
    ),
    (
        "sack", "Sack (charted)",
        "A charted sack, split from pressures/hits/hurries by outcome, not a "
        "separate measurement.",
        "PFF signature stats",
    ),
    (
        "hurr", "Hurry (charted)",
        "A charted pressure that produced neither a sack nor a hit.",
        "PFF signature stats",
    ),
    (
        "time_to_throw", "Time to throw",
        "Seconds from snap to release or sack, charted. Reflects coverage, "
        "protection, and QB decision-making together, not any one of them alone.",
        "PFF signature stats",
    ),
    (
        "depth_of_target", "Depth of target (aDOT)",
        "Average air yards on intended targets. Not a receiver-separation or "
        "QB arm-strength measure by itself.",
        "PFF signature stats",
    ),
    (
        "route", "Routes run",
        "Charted pass routes. Denominator for yards-per-route-run and similar "
        "rate stats; routes are not the same as targets.",
        "PFF signature stats",
    ),
    (
        "yprr", "Yards per route run",
        "Receiving yards divided by routes run. Output per route, but scheme "
        "and QB quality drive it as much as receiver skill.",
        "PFF signature stats",
    ),
    (
        "contested", "Contested target/catch",
        "A charted contested-catch situation. Boundary judgment calls are "
        "subjective; rate confounds receiver talent with target selection.",
        "PFF signature stats",
    ),
    (
        "catch", "Catch rate",
        "Receptions over charted catchable (or all) targets, per PFF's charting.",
        "PFF signature stats",
    ),
    (
        "drop", "Drop (charted)",
        "A charted drop on a catchable target.",
        "PFF signature stats",
    ),
    (
        "avoided_tackle", "Avoided/missed tackle",
        "A charted broken or avoided tackle after contact. Attribution and "
        "pursuit-role context are charting judgments.",
        "PFF signature stats",
    ),
    (
        "missed_tackle", "Missed tackle rate",
        "Missed tackles over charted tackle opportunities. Opportunity "
        "definition and pursuit role vary by scheme.",
        "PFF signature stats",
    ),
    (
        "qb_rating_against", "Passer rating allowed",
        "NFL passer-rating formula computed on the QB's targets against this "
        "defender/unit. Not a pure coverage metric -- QB and receiver quality "
        "flow straight through it.",
        "PFF signature stats",
    ),
    (
        "block", "Blocking snaps/grade",
        "Pass- or run-blocking snaps and charted grade for that role.",
        "PFF grades",
    ),
    (
        "epa", "Expected points added",
        "Play-level EPA from PFF's public-metrics stack, not a PFF-proprietary "
        "grade.",
        "Public play metrics",
    ),
    (
        "penalt", "Penalties (charted)",
        "Penalties charted to this player, declined or accepted as marked by "
        "the column name.",
        "PFF signature stats",
    ),
    (
        "big_time_throw", "Big-time throw",
        "A charted high-value, high-difficulty completion. Rate (`btt_rate`) is "
        "big-time throws over attempts.",
        "PFF signature stats",
    ),
    ("btt_rate", "Big-time-throw rate", "See `big_time_throw`.", "PFF signature stats"),
    (
        "turnover_worthy", "Turnover-worthy play",
        "A charted throw that should have been intercepted regardless of outcome. "
        "Rate (`twp_rate`) is turnover-worthy plays over attempts.",
        "PFF signature stats",
    ),
    ("twp_rate", "Turnover-worthy-play rate", "See `turnover_worthy`.", "PFF signature stats"),
    (
        "yards_after_contact", "Yards after contact",
        "Post-contact yardage creation -- the run-game analog of YAC. Tackle "
        "attribution and blocking context are charted, not measured.",
        "PFF signature stats",
    ),
    (
        "elu", "Elusive rating / missed-tackles-forced",
        "PFF's composite elusiveness metric and its missed-tackles-forced (mtf) "
        "and yards-created-per-touch (yco) components. Proprietary composite, "
        "not independently replicable from public documentation.",
        "PFF signature stats",
    ),
    (
        "coverage_snaps_per", "Coverage snaps per target/reception",
        "Snaps covered per charted target or reception allowed. Low volume can "
        "mean avoidance or an untested role -- not necessarily strong coverage.",
        "PFF signature stats",
    ),
    (
        "pass_rush_win_rate", "Pass-rush win rate",
        "Charted rate of beating a blocker within a PFF-defined win window, "
        "independent of whether the rush produced a pressure.",
        "PFF signature stats",
    ),
    (
        "pbe", "Pass-block efficiency",
        "PFF's weighted pass-blocking composite (sacks weighted heaviest, then "
        "hits, then hurries, per pass-block snap). Proprietary weighting.",
        "PFF signature stats",
    ),
    (
        "war", "PFF WAR / wins above average",
        "A PFF valuation output. No public formula sufficient for independent "
        "replication is documented -- treat as a proprietary model output, not "
        "an observed count.",
        "PFF WAR and ratings",
    ),
]


def pff_glossary_match(col: str) -> int | None:
    """Index into PFF_GLOSSARY for the first pattern found in `col`'s tokens."""
    low = col.lower()
    for i, (needle, *_rest) in enumerate(PFF_GLOSSARY):
        if needle in low:
            return i
    return None

# Long-format stat vocabularies: (table, name expression, category expression).
# `stat_categories` is a catalog of names with no fact rows, hence n = 0.
NAMED_SOURCES = [
    ("team_stats", '"statName"', "'team box'"),
    ("player_season_stats", "category || '.' || \"statType\"", "category"),
    ("play_stats", '"statType"', "'play event'"),
    ("stat_categories", '"value"', "'box catalog'"),
]

# Matched against whole name tokens, most specific domain first. Order carries
# the hand-built catalog's judgement calls and is pinned by the tests:
#   * `personnel` is roster acquisition (recruiting, draft, transfers), so it
#     outranks the generic `players`.
#   * derived ratings outrank the raw thing they rate (`kicker_paar` is a
#     rating, not a player table).
#   * a per-game team table is a game table (`team_stats`, `records`), so
#     `games` outranks `teams`.
# Substring matching is wrong here: it puts `players` in plays, `playoff` in
# plays, and `line_scores` in betting -- match whole tokens.
DOMAIN_RULES = [
    ("plays", {"play", "plays", "drive", "drives"}),
    ("coaches", {"coach", "coaches"}),
    ("weather", {"weather", "condition", "conditions"}),
    ("venues", {"venue", "venues"}),
    ("personnel", {"recruit", "recruits", "recruiting", "transfer", "transfers",
                   "portal", "draft", "commits"}),
    ("betting", {"line", "lines", "linescore", "odds", "bet", "bets", "market",
                 "markets", "spread", "spreads", "moneyline", "an", "ats",
                 "provider", "providers", "book", "books", "tick", "ticks"}),
    ("ratings", {"rating", "ratings", "elo", "sp", "srs", "fpi", "ppa", "poll",
                 "polls", "rank", "ranks", "ranking", "rankings", "talent",
                 "predicted", "massey", "adjusted", "metrics", "wepa", "paar",
                 "ep", "prob", "probability", "returning", "production",
                 "playoff", "postseason", "participants"}),
    ("players", {"player", "players", "athlete", "athletes", "roster", "rosters",
                 "position", "positions", "passing", "rushing", "receiving",
                 "kicker", "kickers", "kicking", "punting", "hometown",
                 "hometowns", "usage", "pff"}),
    ("games", {"game", "games", "calendar", "week", "weeks", "media",
               "scoreboard", "box", "stat", "stats", "record", "records",
               "matchup", "matchups", "score", "scores", "havoc"}),
    ("teams", {"team", "teams", "conference", "conferences", "fbs",
               "explosiveness"}),
]


def _mask_strings(src: str) -> tuple[str, list[str]]:
    """Swap every JS string literal for a sentinel so key-quoting regexes are safe."""
    out: list[str] = []
    lits: list[str] = []
    i, n = 0, len(src)
    while i < n:
        if src[i] == '"':
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == '"':
                    break
                j += 1
            lits.append(src[i : j + 1])
            out.append(f"\x00{len(lits) - 1}\x00")
            i = j + 1
        else:
            out.append(src[i])
            i += 1
    return "".join(out), lits


def parse_data(html: str) -> dict:
    """Read the current DATA literal (JS object notation) back into Python."""
    m = DATA_SPAN.search(html)
    if not m:
        raise SystemExit("could not locate the `const DATA = {...};` block")
    src, lits = _mask_strings("{" + m.group(2) + "\n}")
    src = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', src)
    src = re.sub(r",(\s*[\]\}])", r"\1", src)
    src = re.sub(r"\x00(\d+)\x00", lambda mo: lits[int(mo.group(1))], src)
    return json.loads(src)


def origin_of(schema: str, name: str) -> str:
    if schema in ("core", "meta"):
        return schema
    if name.startswith("an_"):
        return "an"
    if schema == "raw" and name in set(GQL_ENTITY_TO_RAW.values()):
        return "gql"
    if schema == "stg" and name in set(GQL_ENTITY_TO_STG.values()):
        return "gql"
    return "rest"


def _tokens(name: str) -> set[str]:
    """Split a table name into lowercase word tokens (snake and camel boundaries)."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return {t for t in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if t}


def domain_of(schema: str, name: str) -> str:
    """Domain for a table. The root before `__` decides: an exploded child like
    `advanced_box_score__teams_rushing` belongs wherever its parent does, not in
    whatever domain its leaf column group happens to name."""
    if schema in ("core", "meta"):
        return schema
    root = name.split("__", 1)[0]
    if root.startswith("gql_"):
        root = root[4:]
    toks = _tokens(root)
    for domain, needles in DOMAIN_RULES:
        if toks & needles:
            return domain
    return "other"


SAMPLE_ROWS = 8
CELL_CHARS = 60
_DATA_ROOT_RE = re.compile(
    re.escape(str(cfb_paths.DATA_ROOT)).replace(r"\\", "[\\\\/]") + "[\\\\/]?",
    re.IGNORECASE,
)


def sample_cell(value: object) -> object:
    """One preview cell: JSON-safe, machine-path-free, one line, short.

    `_source_file` columns hold absolute paths, so the data root is stripped --
    a committed doc should not carry whoever built it's home directory, and the
    path would go stale on any other machine anyway.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()[:19]
    text = _DATA_ROOT_RE.sub("", str(value))
    # JSON payloads are pretty-printed; collapsing gets more signal per char.
    text = " ".join(text.split())
    if len(text) > CELL_CHARS:
        text = text[: CELL_CHARS - 1] + "…"
    return text


def is_nested(ctype: str) -> bool:
    return (
        ctype == "JSON"
        or "STRUCT" in ctype
        or "MAP(" in ctype
        or ctype.endswith("[]")
    )


def sample_rows(
    con: duckdb.DuckDBPyConnection, schema: str, name: str, cols: list
) -> list[list]:
    """A few preview rows, ordered so the same data always samples the same way.

    An unordered `limit` returns whatever the scan reaches first, so `--check`
    fires after a reload that changed nothing. `ORDER BY ALL` is tried first --
    `raw.gamePlayerStat` and `raw.win_probability` tie on every scalar column
    they have (one source file, one season, no week), and only the JSON payload
    separates them, so a full order is what determinism needs there. That is
    also what OOM'd `raw.an_scoreboard`, whose JSON blobs run past 4MB a row:
    on OOM, retry ordered by scalar columns only. A tie only a nested column
    would break then stays a tie -- which duplicate lands in the preview isn't
    worth an OOM to pin down.
    """
    tbl = f'"{schema}"."{name}"'
    try:
        got = con.execute(
            f"select * from {tbl} order by all limit {SAMPLE_ROWS}"
        ).fetchall()
    except duckdb.Error:
        scalar_cols = [c[0] for c in cols if not is_nested(c[1]) and c[1] != "BLOB"]
        order = ", ".join(f'"{c}"' for c in scalar_cols) if scalar_cols else "all"
        try:
            got = con.execute(
                f"select * from {tbl} order by {order} limit {SAMPLE_ROWS}"
            ).fetchall()
        except duckdb.Error as exc:
            # Both orderings failed -- take an unordered sample rather than
            # abort the whole build. Non-deterministic for this one table
            # (`--check` may cry wolf on it after an unrelated reload), but a
            # generator that dies on the least hospitable table in the
            # warehouse is worse than one preview that occasionally reshuffles.
            print(f"  ! unordered sample for {schema}.{name}: {exc}", file=sys.stderr)
            got = con.execute(f"select * from {tbl} limit {SAMPLE_ROWS}").fetchall()
    return [[sample_cell(v) for v in row] for row in got]


def column_stats(
    con: duckdb.DuckDBPyConnection, schema: str, name: str, cols: list
) -> dict[str, tuple]:
    """Per-column min / max / distinct-count / null-count (+ NaN-count for floats).

    Two queries, not one. min/max/null are streaming aggregates -- cheap at any
    width. `count(distinct ...)` builds a hash set per column, and a wide table
    with several million rows and many high-cardinality text columns (an
    exploded JSON child, `plays`) OOM'd running all of those hash sets alongside
    the streaming ones in a single query. Split, the cheap half always survives;
    the distinct-count half degrades to "not computed" (nd=None) under the same
    OOM rather than losing min/max/nulls too. Nested (JSON/STRUCT/MAP/array) and
    BLOB columns are skipped outright: a JSON min/max is lexicographic over a
    huge blob and tells you nothing.
    """
    scalars = [(c[0], c[1]) for c in cols if not is_nested(c[1]) and c[1] != "BLOB"]
    if not scalars:
        return {}
    tbl = f'"{schema}"."{name}"'

    exprs = []
    for col, ctype in scalars:
        cq = f'"{col}"'
        exprs += [
            f"min({cq})", f"max({cq})", f"count(*) filter (where {cq} is null)",
        ]
        if ctype in FLOATY:
            exprs.append(f"count(*) filter (where isnan({cq}))")
    try:
        row = con.execute(f'select {", ".join(exprs)} from {tbl}').fetchone()
    except duckdb.Error as exc:
        print(f"  ! stats skipped for {schema}.{name}: {exc}", file=sys.stderr)
        return {}

    out: dict[str, tuple] = {}
    i = 0
    for col, ctype in scalars:
        mn, mx, nn = row[i : i + 3]
        i += 3
        na = None
        if ctype in FLOATY:
            na = row[i]
            i += 1
        out[col] = [sample_cell(mn), sample_cell(mx), None, nn, na]

    try:
        nd_exprs = ", ".join(f'count(distinct "{col}")' for col, _ in scalars)
        nd_row = con.execute(f"select {nd_exprs} from {tbl}").fetchone()
        for (col, _ctype), nd in zip(scalars, nd_row):
            out[col][2] = nd
    except duckdb.Error as exc:
        print(f"  ! distinct-counts skipped for {schema}.{name}: {exc}", file=sys.stderr)

    return {col: tuple(v) for col, v in out.items()}


def compute_grain(
    con: duckdb.DuckDBPyConnection, schema: str, name: str, cols: list, n_rows: int
) -> str:
    """'One row per <key columns>', computed from actual uniqueness, not guessed.

    Candidate keys are the columns `is_key()` already carves out for wstats
    (season/week/id-shaped columns). If their tuple is unique across the table,
    say so; if not, say how many rows collide rather than asserting a false grain.
    """
    keys = [c for c, ctype, *_ in cols if is_key(c)]
    if not keys or n_rows == 0:
        return ""
    tuple_expr = " || '\x01' || ".join(
        f"coalesce(\"{c}\"::varchar, '\x00')" for c in keys
    )
    distinct = con.execute(
        f'select count(distinct {tuple_expr}) from "{schema}"."{name}"'
    ).fetchone()[0]
    label = ", ".join(keys)
    if distinct == n_rows:
        return f"One row per {label}"
    return f"Not unique on {label} ({n_rows - distinct} duplicate rows)"


def is_key(col: str) -> bool:
    return col in KEY_NAMES or col in KEY_EXTRA or col.endswith(KEY_SUFFIXES)


def measure_kind(col: str, ctype: str) -> str | None:
    """`flag` for booleans, `stat` for measurements, None for keys and text."""
    if col.startswith("_"):
        return None
    if is_key(col):
        return None
    if ctype == "BOOLEAN":
        return "flag"
    if ctype in NUMERIC:
        return "stat"
    return None


def introspect(con: duckdb.DuckDBPyConnection, seed: dict) -> dict:
    rows = con.execute(
        "select schema_name, table_name from duckdb_tables() order by 1, 2"
    ).fetchall()

    tables, wstats, detail, grain = [], [], {}, {}
    pff_unmatched: set[str] = set()
    for schema, name in rows:
        cols = con.execute(f'describe "{schema}"."{name}"').fetchall()
        n_rows = con.execute(f'select count(*) from "{schema}"."{name}"').fetchone()[0]
        stats = column_stats(con, schema, name, cols)
        is_pff = name.startswith("pff_")
        col_rows = []
        for c in cols:
            col, ctype = c[0], c[1]
            entry = [col, ctype, *stats.get(col, (None, None, None, None, None))]
            if is_pff:
                gi = pff_glossary_match(col)
                entry.append(gi)
                if gi is None and not col.startswith("_") and not is_key(col):
                    pff_unmatched.add(col)
            col_rows.append(entry)
        detail[f"{schema}.{name}"] = {
            "c": col_rows,
            "s": sample_rows(con, schema, name, cols),
        }
        grain[f"{schema}.{name}"] = compute_grain(con, schema, name, cols, n_rows)
        domain = domain_of(schema, name)
        n_stat = n_nested = 0
        for col, ctype, *_ in cols:
            if is_nested(ctype):
                n_nested += 1
            kind = measure_kind(col, ctype)
            if kind is None:
                continue
            if kind == "stat":
                n_stat += 1
            wstats.append(
                {"s": schema, "t": name, "c": col, "y": ctype, "k": kind, "g": domain}
            )
        tables.append(
            {
                "s": schema,
                "n": name,
                "r": n_rows,
                "g": domain,
                "o": origin_of(schema, name),
                "c": len(cols),
                "ns": n_stat,
                "nn": n_nested,
            }
        )

    live = {(s, n) for s, n in rows}
    named = []
    for table, name_expr, cat_expr in NAMED_SOURCES:
        if ("stg", table) not in live:
            continue
        zero = table == "stat_categories"
        for stat_name, cat, cnt in con.execute(
            f'select {name_expr}, {cat_expr}, count(*) from stg."{table}" '
            f"where {name_expr} is not null group by 1, 2 order by 3 desc, 1"
        ).fetchall():
            named.append(
                {"src": table, "name": stat_name, "cat": cat, "n": 0 if zero else cnt}
            )

    by_schema: dict[str, list[dict]] = {}
    for t in tables:
        by_schema.setdefault(t["s"], []).append(t)

    # Core tables get the hand-written CORE_NOTES prose in the general `grain`
    # field too, so the Tables pane has one field to read regardless of schema;
    # `coreNote` below is untouched -- it is what the dedicated Core pane reads.
    for t in by_schema.get("core", []):
        note = CORE_NOTES.get(t["n"])
        if note:
            grain[f"core.{t['n']}"] = note

    data = {
        "tables": tables,
        "wstats": wstats,
        "named": named,
        "detail": detail,
        "grain": grain,
        "pffGlossary": [
            {"needle": g[0], "label": g[1], "def": g[2], "src": g[3]}
            for g in PFF_GLOSSARY
        ],
        "domainOrder": seed["domainOrder"],
        "coreNote": {
            t["n"]: CORE_NOTES.get(t["n"], "")
            for t in sorted(by_schema.get("core", []), key=lambda t: t["n"])
        },
        "loaded": date.today().isoformat(),
    }
    for schema in ("stg", "raw", "core", "meta"):
        group = by_schema.get(schema, [])
        data[f"{schema}_tables"] = len(group)
        data[f"{schema}_rows"] = sum(t["r"] for t in group)
    if pff_unmatched:
        print(
            f"  ? {len(pff_unmatched)} PFF columns matched no glossary entry: "
            + ", ".join(sorted(pff_unmatched)[:20])
            + (" ..." if len(pff_unmatched) > 20 else ""),
            file=sys.stderr,
        )
    return data


def render(data: dict) -> str:
    """Emit the DATA body. Prettier reformats it; the JSON is only the seed shape."""
    lines = []
    for key in ("tables", "wstats", "named"):
        lines.append(f"        {key}: [")
        for row in data[key]:
            body = ", ".join(f"{k}: {json.dumps(v)}" for k, v in row.items())
            lines.append(f"          {{ {body} }},")
        lines.append("        ],")
    # One line per table: 322 entries pretty-printed would swamp the diff.
    lines.append("        detail: {")
    for key, d in data["detail"].items():
        lines.append(
            f"          {json.dumps(key)}: "
            f"{json.dumps(d, separators=(',', ':'), ensure_ascii=False)},"
        )
    lines.append("        },")
    lines.append("        grain: {")
    for key, v in data["grain"].items():
        if v:
            lines.append(f"          {json.dumps(key)}: {json.dumps(v)},")
    lines.append("        },")
    lines.append("        pffGlossary: [")
    for g in data["pffGlossary"]:
        body = ", ".join(f"{k}: {json.dumps(v)}" for k, v in g.items())
        lines.append(f"          {{ {body} }},")
    lines.append("        ],")
    lines.append("        domainOrder: [")
    for d in data["domainOrder"]:
        lines.append(f"          {json.dumps(d)},")
    lines.append("        ],")
    lines.append("        coreNote: {")
    for k, v in data["coreNote"].items():
        lines.append(f"          {k}: {json.dumps(v)},")
    lines.append("        },")
    lines.append(f"        loaded: {json.dumps(data['loaded'])},")
    for schema in ("stg", "raw", "core", "meta"):
        lines.append(f"        {schema}_tables: {data[f'{schema}_tables']},")
    for schema in ("stg", "raw", "core", "meta"):
        lines.append(f"        {schema}_rows: {data[f'{schema}_rows']},")
    return "\n" + "\n".join(lines)


def build(html: str) -> tuple[str, dict, dict]:
    seed = parse_data(html)
    con = duckdb.connect(str(cfb_paths.DB_PATH), read_only=True)
    # DuckDB's default memory_limit is a fraction of *total* physical RAM, not
    # what is actually free -- on a dev box already running an IDE, a browser
    # and this agent, that ceiling is higher than the OS can hand over, and the
    # allocation fails as an OOM inside DuckDB rather than degrading. Capping
    # it low makes DuckDB spill the wide min/max/distinct aggregates to disk
    # instead of reaching for memory that was never really available.
    con.execute("PRAGMA memory_limit='2GB'")
    try:
        data = introspect(con, seed)
    finally:
        con.close()
    return DATA_SPAN.sub(lambda m: m.group(1) + render(data) + m.group(3), html), data, seed


def report(data: dict, seed: dict) -> None:
    was = {(t["s"], t["n"]) for t in seed["tables"]}
    now = {(t["s"], t["n"]) for t in data["tables"]}
    added = sorted(now - was)
    dropped = sorted(was - now)
    print(f"tables {len(seed['tables'])} -> {len(data['tables'])}  "
          f"(+{len(added)} / -{len(dropped)})")
    print(f"wstats {len(seed['wstats'])} -> {len(data['wstats'])}   "
          f"named {len(seed['named'])} -> {len(data['named'])}")
    for schema in ("core", "stg", "raw", "meta"):
        print(f"  {schema:5s} {data[f'{schema}_tables']:>4} tables  "
              f"{data[f'{schema}_rows']:>12,} rows")
    if dropped:
        print(f"\ndropped ({len(dropped)}):")
        for s, n in dropped:
            print(f"  - {s}.{n}")
    if added:
        print(f"\nadded ({len(added)}) -- check the auto-assigned domain:")
        dom = {(t["s"], t["n"]): t["g"] for t in data["tables"]}
        for s, n in added:
            print(f"  + {s}.{n:<38} domain={dom[(s, n)]}")

    # Where the rules disagree with the hand-built catalog on a table that
    # survived, the rules are probably wrong -- surface it rather than bury it.
    seed_dom = {(t["s"], t["n"]): t["g"] for t in seed["tables"]}
    drift = [
        (t["s"], t["n"], seed_dom[(t["s"], t["n"])], t["g"])
        for t in data["tables"]
        if (t["s"], t["n"]) in seed_dom and seed_dom[(t["s"], t["n"])] != t["g"]
    ]
    kept = len(now & was)
    print(f"\ndomain agrees with the hand-built catalog on "
          f"{kept - len(drift)}/{kept} surviving tables")
    for s, n, before, after in drift:
        print(f"  ~ {s}.{n:<38} {before} -> {after}")
    blank = [k for k, v in data["coreNote"].items() if not v]
    if blank:
        print(f"\ncore tables with no coreNote prose ({len(blank)}) -- write one:")
        for k in blank:
            print(f"  ? core.{k}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="report staleness without writing; exit 1 if stale")
    args = ap.parse_args()

    html = CATALOG.read_text(encoding="utf-8")
    new_html, data, seed = build(html)
    report(data, seed)

    if args.check:
        if new_html == html:
            print("\ncatalog is current")
            return 0
        print("\ncatalog is STALE -- run without --check")
        return 1
    CATALOG.write_text(new_html, encoding="utf-8", newline="\n")
    print(f"\nwrote {CATALOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
