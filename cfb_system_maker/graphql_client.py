"""Bulk scraper over the CFBD GraphQL (Hasura) API — Patreon Tier 3 only.

GraphQL collapses per-row REST fan-out into a few paginated queries: one request
returns up to ``page_size`` rows. Tables, columns and sort keys are discovered by
introspection, so this stays generic like the REST registry — the only hand-kept
list is which root tables to pull. Output lands in ``data/graphql/`` (kept separate
from REST ``data/raw/`` because the GraphQL row shapes differ).
"""

from __future__ import annotations

import json
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
    "game", "gameLines", "gameTeam", "gameMedia", "gameWeather",
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

# Introspected tables deliberately kept OUT of the default pull, and why. Lives here rather
# than in the audit script so the rationale sits next to the list it modifies; the audit
# reads both. Mirrors DELIBERATE on the REST side.
GQL_EXCLUDED: dict[str, str] = {
    "gamePlayerStat": "~6.7M rows, multi-GB; pull per season with --tables/--season",
    "scoreboard": "live in-progress games, no historical value",
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
    fields = " ".join(table.scalars)
    # Hasura names this arg `orderBy` and takes an UPPERCASE enum; `order_by: {x: asc}` is
    # rejected on both counts. The docs warn that `offset` without `orderBy` has no stable
    # row order, so an unsorted paginated pull can skip or repeat rows between pages.
    order = f"orderBy: {{{table.sort_key}: ASC}}" if "orderBy" in table.args else ""
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
