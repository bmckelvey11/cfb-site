"""Bulk scraper over the CFBD GraphQL (Hasura) API — Patreon Tier 3 only.

GraphQL collapses per-row REST fan-out into a few paginated queries: one request
returns up to ``page_size`` rows. Tables, columns and sort keys are discovered by
introspection, so this stays generic like the REST registry — the only hand-kept
list is which root tables to pull. Output lands in ``data/graphql/`` (kept separate
from REST ``data/raw/`` because the GraphQL row shapes differ).
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from cfb_system_maker.cfbd_client import find_cfbd_token

GRAPHQL_URL = "https://graphql.collegefootballdata.com/v1/graphql"

# Root query fields to pull in bulk. Each resolves to a table; columns/sort key are
# discovered by introspection. Large tables (gamePlayerStat, athlete) honor --season
# where the table has a season/year column.
GQL_DEFAULT_TABLES: list[str] = [
    "game", "gameLines", "gameTeam", "gameWeather",
    "recruit", "recruitingTeam", "ratings", "teamTalent",
    "athlete", "athleteTeam", "coach", "coachSeason", "transfer",
    "adjustedPlayerMetrics", "adjustedTeamMetrics", "draftPicks",
    "poll", "pollRank", "calendar", "conference", "currentTeams",
    "historicalTeam", "predictedPoints",
    # Small lookup tables (2.5 KB - 2.2 MB each). They were reachable only via --tables
    # until scripts/audit_endpoints.py made introspection the universe and showed them
    # sitting outside the default pull.
    "draftPosition", "draftTeam", "hometown", "linesProvider", "playerStatCategory",
    "playerStatType", "pollType", "position", "recruitPosition", "recruitSchool",
    "weatherCondition",
]


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


# Destination table name for each GraphQL entity, per schema. Explicit and total on
# purpose: a clash resolver that picks a winner by load order previously caused
# `stg.calendar` (REST, 258 rows) and `stg.calendar_gql` (GraphQL, 424 rows) to swap
# provenance across a rebuild with nothing recording which was which.
#
# GQL_ENTITY_TO_STG: bare `stg_gql` destination. GraphQL lives in its own schema, so
# no prefix is needed to stay disjoint from REST's `stg` destinations.
#
# GQL_ENTITY_TO_RAW: `raw` destination, decoupled from the above on purpose. `raw`
# mixes REST and GraphQL dumps in one schema (no `raw_gql`), so it keeps the `gql_`
# prefix that keeps it collision-free with REST raw dumps of the same snake_case name
# (`draft_picks`, `predicted_points`, `calendar` all collide once GraphQL is bare).
#
# The keys are the upstream API contract and must not be renamed.
GQL_ENTITY_TO_STG: dict[str, str] = {entity: _snake(entity) for entity in GQL_DEFAULT_TABLES}
GQL_ENTITY_TO_RAW: dict[str, str] = {
    entity: "gql_" + _snake(entity) for entity in GQL_DEFAULT_TABLES
}
GQL_RAW_TO_ENTITY: dict[str, str] = {raw: entity for entity, raw in GQL_ENTITY_TO_RAW.items()}

# Tables whose scalar columns do not identify a row: the identity lives in a to-one
# relation. For each, the relation and the few columns lifted from it — enough to join,
# not the whole related row. Selected AND sorted on, since a table like pollRank has only
# (rank, points, firstPlaceVotes) as scalars and would otherwise paginate on heavy ties.
GQL_RELATION_KEYS: dict[str, dict[str, list[str]]] = {
    "pollRank": {
        # `pollType` separates the AP and Coaches polls, which otherwise produce
        # byte-identical rows whenever both rank a team the same in the same week.
        "poll": ["season", "seasonType", "week", "pollType.name"],
        "team": ["school", "conference", "classification"],
    },
}

# Introspected tables deliberately kept OUT of the default pull, and why. Lives here rather
# than in the audit script so the rationale sits next to the list it modifies; the audit
# reads both. Mirrors DELIBERATE on the REST side.
GQL_EXCLUDED: dict[str, str] = {
    "gamePlayerStat": "~6.7M rows, multi-GB; pull per season with --tables/--season",
    "scoreboard": "live in-progress games, no historical value",
    "gameMedia": "no join key exists on this root — GameMedia is reachable only as "
                 "game.mediaInfo, so a dump of it cannot be tied back to a game; the REST "
                 "media_{season}.json files carry gameId and are what enrich reads",
}

Poster = Callable[[str, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class TableInfo:
    root: str
    scalars: list[str]
    sort_key: str
    season_col: str | None
    args: frozenset[str]  # query args the root field accepts (limit/offset/order_by/where)


@dataclass(frozen=True)
class GqlReport:
    name: str
    rows: int
    pages: int
    error: str | None = None
    skipped: bool = False


def graphql_scrape(
    *,
    tables: list[str] | None = None,
    data_dir: str | Path = "data",
    seasons: list[int] | None = None,
    page_size: int = 1000,
    only: set[str] | None = None,
    token: str | None = None,
    post_fn: Poster | None = None,
) -> list[GqlReport]:
    """Pull each table to ``data/graphql/{table}.json``. ``post_fn`` injectable for tests."""
    post = post_fn or _make_poster(token or find_cfbd_token())
    schema = _introspect(post)

    reports: list[GqlReport] = []
    for name in (tables or GQL_DEFAULT_TABLES):
        if only is not None and name not in only:
            continue
        if name not in schema:
            reports.append(GqlReport(name, 0, 0, error="not a queryable table"))
            continue
        try:
            rows, pages = _paginate(schema[name], post, page_size, seasons)
            _write(data_dir, f"{name}.json", rows)
            reports.append(GqlReport(name, len(rows), pages))
        except Exception as exc:  # one table failing must not abort the run
            reports.append(GqlReport(name, 0, 0, error=f"{type(exc).__name__}: {exc}"))
    return reports


_INTROSPECTION = """
{
  __schema {
    queryType { fields { name args { name } type { ...TR } } }
    types { name fields { name type { ...TR } } }
  }
}
""".replace("...TR", "kind name ofType{ kind name ofType{ kind name ofType{ kind name ofType{ kind name } } } }")


def _introspect(post: Poster) -> dict[str, TableInfo]:
    data = post(_INTROSPECTION, {})
    schema = data["__schema"]

    root_type = {f["name"]: _unwrap(f["type"])[1] for f in schema["queryType"]["fields"]}
    root_args = {f["name"]: frozenset(a["name"] for a in (f.get("args") or [])) for f in schema["queryType"]["fields"]}
    type_scalars: dict[str, list[str]] = {}
    for typ in schema["types"]:
        if not typ.get("fields"):
            continue
        type_scalars[typ["name"]] = [
            f["name"] for f in typ["fields"] if _unwrap(f["type"])[0] == "SCALAR"
        ]

    info: dict[str, TableInfo] = {}
    for root, type_name in root_type.items():
        scalars = type_scalars.get(type_name)
        if not scalars:
            continue
        sort_key = "id" if "id" in scalars else scalars[0]
        season_col = "season" if "season" in scalars else ("year" if "year" in scalars else None)
        info[root] = TableInfo(root, scalars, sort_key, season_col, root_args.get(root, frozenset()))
    return info


def _paginate(
    table: TableInfo,
    post: Poster,
    page_size: int,
    seasons: list[int] | None,
) -> tuple[list[dict[str, Any]], int]:
    relations = GQL_RELATION_KEYS.get(table.root, {})
    blocks = [f"{rel} {{ {_selection(cols)} }}" for rel, cols in relations.items()]
    fields = " ".join([*table.scalars, *blocks])
    # Hasura names this arg `orderBy` and takes an UPPERCASE enum; `order_by: {x: asc}` is
    # rejected on both counts. The docs warn that `offset` without `orderBy` has no stable
    # row order, so an unsorted paginated pull can skip or repeat rows between pages.
    #
    # The sort must be a TOTAL order or it does not fix anything: 20 of the 35 default
    # tables have no `id`, and ordering those by one arbitrary column (gameTeam by `endElo`)
    # leaves ties to break differently per request, which silently drops rows across page
    # boundaries. Ordering by every scalar column leaves ties only between byte-identical
    # rows, which are interchangeable. Measured at 0.3s for a gameTeam page.
    order = ""
    if "orderBy" in table.args:
        if "id" in table.scalars:
            clauses = ["{id: ASC}"]
        else:
            # Relation keys come first: they are what actually separates rows on a table
            # whose own scalars repeat (pollRank has three, all small integers).
            clauses = [
                _order_clause(f"{rel}.{col}")
                for rel, cols in relations.items()
                for col in cols
            ]
            clauses += [f"{{{col}: ASC}}" for col in table.scalars]
        order = f"orderBy: [{', '.join(clauses)}]"
    where = ""
    if seasons and table.season_col and "where" in table.args:
        where = f"where: {{{table.season_col}: {{_in: [{', '.join(str(s) for s in seasons)}]}}}}"
    static = ", ".join(part for part in (order, where) if part)

    # Tables without limit/offset args (non-paginated views) are fetched in one shot.
    if not ({"limit", "offset"} <= table.args):
        args = f"({static})" if static else ""
        query = f"{{ {table.root}{args} {{ {fields} }} }}"
        data = post(query, {})
        return list(data[table.root]), 1

    head = "limit: $limit, offset: $offset" + (f", {static}" if static else "")
    query = f"query($limit: Int!, $offset: Int!) {{ {table.root}({head}) {{ {fields} }} }}"
    rows: list[dict[str, Any]] = []
    offset = 0
    pages = 0
    # Stop only on an empty page, advancing by actual page length. Some tables are
    # capped server-side (e.g. ~999 rows/request regardless of limit), so a short
    # page does NOT mean the end — only a zero-length page does.
    while True:
        data = post(query, {"limit": page_size, "offset": offset})
        page = data[table.root]
        if not page:
            break
        rows.extend(page)
        pages += 1
        offset += len(page)
    return rows, pages


# gamePlayerStat can't go through the generic path: its scalar columns are just
# {id, stat, athleteId, gameTeamId} — the meaning lives in relations, and it has no
# season scalar (must filter through gameTeam->game->season). This bespoke query
# flattens the useful relation fields and scopes by season, written one file per season.
_PLAYER_STAT_QUERY = (
    "query($limit: Int!, $offset: Int!) {\n"
    "  gamePlayerStat(limit: $limit, offset: $offset, where: {gameTeam: {game: {season: {_eq: SEASON}}}}) {\n"
    "    id\n"
    "    stat\n"
    "    athleteId\n"
    "    athlete { name }\n"
    "    statType: playerStatType { name }\n"
    "    category: playerStatCategory { name }\n"
    "    gameTeam { gameId teamId homeAway game { season week seasonType } }\n"
    "  }\n}"
)


def pull_game_player_stats(
    seasons: list[int],
    *,
    data_dir: str | Path = "data",
    page_size: int = 1000,
    resume: bool = True,
    token: str | None = None,
    post_fn: Poster | None = None,
) -> list[GqlReport]:
    """Pull labeled player-game stats, one file per season (gamePlayerStat_{season}.json)."""
    post = post_fn or _make_poster(token or find_cfbd_token())
    reports: list[GqlReport] = []
    for season in seasons:
        name = f"gamePlayerStat_{season}"
        if resume and (Path(data_dir) / "graphql" / f"{name}.json").exists():
            reports.append(GqlReport(name, 0, 0, skipped=True))
            continue
        try:
            query = _PLAYER_STAT_QUERY.replace("SEASON", str(season))
            rows: list[dict[str, Any]] = []
            offset = 0
            pages = 0
            while True:
                data = post(query, {"limit": page_size, "offset": offset})
                page = data["gamePlayerStat"]
                if not page:
                    break
                rows.extend(page)
                pages += 1
                offset += len(page)
            _write(data_dir, f"{name}.json", rows)
            reports.append(GqlReport(name, len(rows), pages))
        except Exception as exc:
            reports.append(GqlReport(name, 0, 0, error=f"{type(exc).__name__}: {exc}"))
    return reports


def _selection(cols: list[str]) -> str:
    """Render relation columns, nesting dotted paths: `pollType.name` -> `pollType { name }`."""
    plain = [c for c in cols if "." not in c]
    nested: dict[str, list[str]] = {}
    for col in cols:
        if "." in col:
            head, _, tail = col.partition(".")
            nested.setdefault(head, []).append(tail)
    blocks = [f"{head} {{ {_selection(tail)} }}" for head, tail in nested.items()]
    return " ".join([*plain, *blocks])


def _order_clause(path: str) -> str:
    """`poll.pollType.name` -> `{poll: {pollType: {name: ASC}}}` (Hasura orders through
    relations, and a key that only appears in the selection cannot break a tie)."""
    head, _, tail = path.partition(".")
    inner = _order_clause(tail) if tail else "ASC"
    return f"{{{head}: {inner}}}"


def _unwrap(type_ref: dict[str, Any]) -> tuple[str, str | None]:
    """Strip NON_NULL/LIST wrappers; return (base kind, base name)."""
    node = type_ref
    while node.get("ofType"):
        node = node["ofType"]
    return node["kind"], node["name"]


def _make_poster(token: str) -> Poster:
    def post(query: str, variables: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        request = urllib.request.Request(
            GRAPHQL_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "cfb-system-maker/1.0",  # Cloudflare 403s the default urllib UA
            },
        )
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read())
        if payload.get("errors"):
            raise RuntimeError(payload["errors"])
        return payload["data"]

    return post


def _write(data_dir: str | Path, filename: str, rows: list[dict[str, Any]]) -> Path:
    path = Path(data_dir) / "graphql" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, default=str, indent=2, sort_keys=True), encoding="utf-8")
    return path
