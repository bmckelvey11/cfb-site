"""Regenerate the `const DATA = {...}` block in docs/cfb-warehouse-catalog.html.

The catalog's HTML/CSS/JS shell is hand-written and stays put; only the embedded
DATA literal is machine-generated. Everything in DATA is derived from the live
DuckDB plus the loader's own GraphQL destination maps -- nothing is carried
forward from the previous render except the two genuinely editorial fields
(`domainOrder` copy and `coreNote` prose), which are seeded from the file and
reported when a new table has no entry.

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
from datetime import date
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
    "coach_name_conflicts": "Audit: one name, several coach ids",
    "coach_season_unmatched": "Audit: coach seasons that would not join",
    "fact_game_line_conflicts": "Audit: REST and GraphQL disagree on a line",
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


def is_nested(ctype: str) -> bool:
    return (
        ctype == "JSON"
        or "STRUCT" in ctype
        or "MAP(" in ctype
        or ctype.endswith("[]")
    )


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

    tables, wstats = [], []
    for schema, name in rows:
        cols = con.execute(f'describe "{schema}"."{name}"').fetchall()
        n_rows = con.execute(f'select count(*) from "{schema}"."{name}"').fetchone()[0]
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

    data = {
        "tables": tables,
        "wstats": wstats,
        "named": named,
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
