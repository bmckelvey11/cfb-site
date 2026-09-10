"""Load scraped JSON dumps into a DuckDB staging file.

Each REST endpoint / GraphQL table becomes one DuckDB table. Nested objects stay
JSON (the documented JSONB staging shape) so season-to-season schema drift does
not break the load. Filename suffixes supply season/week columns.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import duckdb

from cfb_system_maker.graphql_client import GQL_ENTITY_TO_RAW, GQL_ENTITY_TO_STG, GQL_RAW_TO_ENTITY
from cfb_system_maker.pff_schema import PFF_TABLES, column_types as pff_column_types
from cfb_system_maker.oddsapi_schema import OA_TABLES, column_types as oa_column_types

# Skip account-metering telemetry (docs/data-coverage.md).
_SKIP_STEMS = frozenset({"user_info"})

# 1992–2026 games files exist on disk; keep the window wide for new seasons.
_YEAR_MIN = 1990
_YEAR_MAX = 2035

# Optional ``_post`` before ``_wk`` — postseason scrapes write ``{name}_{year}_post_wk{n}``.
_SEASON_WEEK_RE = re.compile(r"^(.+)_(\d{4})_(post_)?wk(\d+)$")
_SEASON_RE = re.compile(r"^(.+)_(\d{4})$")

# DuckDB allocates a buffer of maximum_object_size per JSON read. Size it to the
# file (plus slack) instead of a global gigabyte, or small tables OOM immediately.
_DEFAULT_OBJECT_SIZE = 16_777_216
_OBJECT_SIZE_SLACK = 1_048_576

_JSON_TABLE_SQL = """
CREATE TABLE {table} (
  payload JSON,
  source_file VARCHAR,
  season INTEGER,
  week INTEGER,
  season_type VARCHAR
)
"""


@dataclass(frozen=True)
class TableLoad:
    schema: str
    name: str
    files: int
    rows: int
    error: str | None = None


# Browse order for stg.* (JSON explode dumps keys in API order, so id/season
# sit at the end of games). Arrays stay with their group, after scalars.
_JOIN_ID_RANK = {
    "playId": 0,
    "play_id": 0,
    "event_id": 1,
    "gameId": 1,
    "game_id": 1,
    "driveId": 2,
    "drive_id": 2,
    "teamId": 3,
    "team_id": 3,
    "athleteId": 4,
    "athlete_id": 4,
    "conferenceId": 5,
    "conference_id": 5,
    "matchupId": 6,
}
_TIME_RANK = {
    "season": 0,
    "year": 1,
    "week": 2,
    "seasonType": 3,
    "season_type": 3,
    "startDate": 4,
    "start_date": 4,
    "startTime": 5,
    "start_time": 5,
    "startTimeTBD": 6,
    "date": 7,
    "wallclock": 8,
}
_ENTITY_RANK = {
    "team": 0,
    "school": 1,
    "name": 2,
    "opponent": 3,
    "mascot": 4,
    "abbreviation": 5,
    "classification": 6,
    "conference": 7,
    "division": 8,
    "playType": 9,
    "playText": 10,
    "driveResult": 11,
    "homeAway": 12,
    "book_id": 13,
    "period": 14,
    "market_type": 15,
    "side": 16,
}
_PREFIX_GROUPS = (
    "home",
    "away",
    "offense",
    "defense",
    "start",
    "end",
    "clock",
    "elapsed",
    "location",
    "venue",
)


# Bare ``id`` is the CFBD row's own key, but the value is a game/play/team/… id.
# Names match the FKs already on sibling tables (play_stats.playId, game.homeTeamId).
_BARE_ID_RENAME = {
    "athlete": "athleteId",
    "cfp_games": "matchupId",
    "coach": "coachId",
    "conference": "conferenceId",
    "conferences": "conferenceId",
    "draftPosition": "draftPositionId",
    "draftTeam": "draftTeamId",
    "drives": "driveId",
    "fbs_teams": "teamId",
    "game": "gameId",
    "game_player_stats": "gameId",
    "game_team_stats": "gameId",
    "games": "gameId",
    "historicalTeam": "teamId",
    "lines": "gameId",
    "linesProvider": "linesProviderId",
    "media": "gameId",
    "play_stat_types": "playStatTypeId",
    "play_types": "playTypeId",
    "player_success_game": "athleteId",
    "player_success_season": "athleteId",
    "player_usage": "athleteId",
    "plays": "playId",
    "pollType": "pollTypeId",
    "position": "positionId",
    "ppa_players_games": "athleteId",
    "ppa_players_season": "athleteId",
    "recruit": "recruitId",
    "recruitPosition": "recruitPositionId",
    "recruitSchool": "recruitSchoolId",
    "recruitingTeam": "recruitingTeamId",
    "recruits": "recruitId",
    "roster": "athleteId",
    "teams": "teamId",
    "venues": "venueId",
    "weather": "gameId",
    "weatherCondition": "weatherConditionId",
}
_EXTRA_ID_RENAMES = {
    "games": {"homeId": "homeTeamId", "awayId": "awayTeamId"},
    "win_probability": {"homeId": "homeTeamId", "awayId": "awayTeamId"},
}


def stg_id_renames(table: str, *, schema: str) -> dict[str, str]:
    """Map current column names → names that match what the id actually is.

    `schema` picks which id-rename spelling applies: only `stg_gql` tables reverse-
    resolve through `GQL_ENTITY_TO_STG` to a GraphQL entity name. A `stg` (REST) table
    that happens to share a bare name with a GraphQL entity (`draft_picks`,
    `predicted_points`, `calendar`) must not pick up the GraphQL entity's id rename.
    """
    base = table[:-4] if table.endswith("_ngt") else table
    source_name = base
    if schema == "stg_gql":
        source_name = next(
            (entity for entity, destination in GQL_ENTITY_TO_STG.items() if destination == base),
            base,
        )
    out: dict[str, str] = {}
    dest = _BARE_ID_RENAME.get(source_name)
    if dest:
        out["id"] = dest
    out.update(_EXTRA_ID_RENAMES.get(base, {}))
    return out


def stg_column_order(
    columns: list[tuple[str, str]],
    *,
    schema: str,
    table: str | None = None,
) -> list[str]:
    """Return column names in browse order. ``columns`` is ``(name, type)``."""
    pk = stg_id_renames(table, schema=schema).get("id") if table else None
    ranked: list[tuple[tuple[int, int, int, int], str]] = []
    for orig, (name, dtype) in enumerate(columns):
        ranked.append((_stg_nav_key(name, dtype, orig, pk), name))
    ranked.sort()
    return [name for _, name in ranked]


def _stg_nav_key(
    name: str, dtype: str, orig: int, pk: str | None = None
) -> tuple[int, int, int, int]:
    # (bucket, subrank, id/scalar/list, original index)
    if name in {"_source_file", "source_file"}:
        return (90, 0, 0, orig)
    inner = _within_group_flag(name, dtype)
    if name == "id" or (pk is not None and name == pk):
        return (0, 0, inner, orig)
    if name in _TIME_RANK:
        return (2, _TIME_RANK[name], inner, orig)
    if name in _ENTITY_RANK:
        return (3, _ENTITY_RANK[name], inner, orig)
    prefix = _prefix_group(name)
    if prefix is not None:
        return (4, _PREFIX_GROUPS.index(prefix), inner, orig)
    if name in _JOIN_ID_RANK or _is_id_column(name):
        return (1, _JOIN_ID_RANK.get(name, 50), inner, orig)
    return (5, 0, inner, orig)


def _within_group_flag(name: str, dtype: str) -> int:
    if name == "id" or _is_id_column(name):
        return 0
    if _is_list_type(dtype):
        return 2
    return 1


def _prefix_group(name: str) -> str | None:
    for prefix in _PREFIX_GROUPS:
        if _has_camel_prefix(name, prefix):
            return prefix
    return None


def _has_camel_prefix(name: str, prefix: str) -> bool:
    if name == prefix:
        return True
    if not name.startswith(prefix) or len(name) <= len(prefix):
        return False
    nxt = name[len(prefix)]
    return nxt == "_" or nxt.isupper()


def _is_id_column(name: str) -> bool:
    return name.endswith("Id") or name.endswith("_id") or name.endswith("ID")


def _is_list_type(dtype: object) -> bool:
    text = str(dtype).strip().upper()
    return text.endswith("[]") or text.startswith("LIST") or "[]" in text


def reorder_stg_columns(
    db: str | Path | duckdb.DuckDBPyConnection,
    *,
    progress: Callable[[TableLoad], None] | None = None,
) -> list[TableLoad]:
    """Rewrite ``stg.*`` tables so identity/time/sides come before leftover JSON keys."""
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    reports: list[TableLoad] = []
    try:
        for schema in _STG_SCHEMAS:
            views = con.execute(
                f"""
                SELECT view_name, sql
                FROM duckdb_views()
                WHERE schema_name = '{schema}'
                ORDER BY view_name
                """
            ).fetchall()
            for view_name, _sql in views:
                con.execute(f"DROP VIEW IF EXISTS {_qualify(schema, view_name)}")
            tables = [
                row[0]
                for row in con.execute(
                    f"""
                    SELECT table_name
                    FROM duckdb_tables()
                    WHERE schema_name = '{schema}'
                    ORDER BY table_name
                    """
                ).fetchall()
            ]
            for name in tables:
                report = _reorder_stg_table(con, schema, name)
                reports.append(report)
                if progress is not None:
                    progress(report)
                con.execute("CHECKPOINT")
            for view_name, sql in views:
                con.execute(sql)
    finally:
        if owns_connection:
            con.close()
    return reports


def _reorder_stg_table(con: duckdb.DuckDBPyConnection, schema: str, name: str) -> TableLoad:
    table = _qualify(schema, name)
    described = [
        (row[0], str(row[1])) for row in con.execute(f"DESCRIBE {table}").fetchall()
    ]
    ordered = stg_column_order(described, schema=schema, table=name)
    current = [col for col, _dtype in described]
    if ordered == current:
        rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return TableLoad(schema, name, 0, int(rows))
    tmp_name = name + "__reordering"
    tmp = _qualify(schema, tmp_name)
    select_list = ", ".join(_ident(col) for col in ordered)
    try:
        con.execute(f"DROP TABLE IF EXISTS {tmp}")
        con.execute(f"CREATE TABLE {tmp} AS SELECT {select_list} FROM {table}")
        con.execute(f"DROP TABLE {table}")
        con.execute(f"ALTER TABLE {tmp} RENAME TO {_ident(name)}")
        rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return TableLoad(schema, name, 1, int(rows))
    except Exception as exc:
        try:
            con.execute(f"DROP TABLE IF EXISTS {tmp}")
        except Exception:
            pass
        detail = str(exc).split("\n", 1)[0]
        return TableLoad(schema, name, 0, 0, error=f"{type(exc).__name__}: {detail}")


def rename_stg_id_columns(
    db: str | Path | duckdb.DuckDBPyConnection,
    *,
    progress: Callable[[TableLoad], None] | None = None,
) -> list[TableLoad]:
    """Rename bare ``id`` (and ``homeId``/``awayId``) to names that match the value."""
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    reports: list[TableLoad] = []
    try:
        for schema in _STG_SCHEMAS:
            views = con.execute(
                f"""
                SELECT view_name, sql
                FROM duckdb_views()
                WHERE schema_name = '{schema}'
                ORDER BY view_name
                """
            ).fetchall()
            for view_name, _sql in views:
                con.execute(f"DROP VIEW IF EXISTS {_qualify(schema, view_name)}")
            tables = [
                row[0]
                for row in con.execute(
                    f"""
                    SELECT table_name
                    FROM duckdb_tables()
                    WHERE schema_name = '{schema}'
                    ORDER BY table_name
                    """
                ).fetchall()
            ]
            for name in tables:
                renamed = _rename_stg_table_ids(con, schema, name)
                if renamed:
                    ordered = _reorder_stg_table(con, schema, name)
                    if ordered.error:
                        reports.append(ordered)
                    else:
                        reports.append(TableLoad(schema, name, renamed, ordered.rows))
                else:
                    rows = con.execute(
                        f"SELECT COUNT(*) FROM {_qualify(schema, name)}"
                    ).fetchone()[0]
                    reports.append(TableLoad(schema, name, 0, int(rows)))
                if progress is not None:
                    progress(reports[-1])
                con.execute("CHECKPOINT")
            for view_name, sql in views:
                try:
                    con.execute(sql)
                except Exception:
                    pass
    finally:
        if owns_connection:
            con.close()
    return reports


def _rename_stg_table_ids(con: duckdb.DuckDBPyConnection, schema: str, name: str) -> int:
    table = _qualify(schema, name)
    present = {row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()}
    changed = 0
    for old, new in stg_id_renames(name, schema=schema).items():
        if old not in present or new in present:
            continue
        con.execute(f"ALTER TABLE {table} RENAME COLUMN {_ident(old)} TO {_ident(new)}")
        present.discard(old)
        present.add(new)
        changed += 1
    return changed


def parse_dump_stem(stem: str) -> tuple[str, int | None, int | None, str | None]:
    """Split dump stems into ``(table, season, week, season_type)``.

    ``plays_2023_wk1`` → ``('plays', 2023, 1, 'regular')``;
    ``plays_2023_post_wk1`` → ``('plays', 2023, 1, 'postseason')``;
    ``games_2023`` → ``('games', 2023, None, None)`` (season-level; type is in payload);
    unknown stems stay whole with null season/week/type.
    """
    match = _SEASON_WEEK_RE.fullmatch(stem)
    if match:
        year = int(match.group(2))
        if _YEAR_MIN <= year <= _YEAR_MAX:
            season_type = "postseason" if match.group(3) else "regular"
            return match.group(1), year, int(match.group(4)), season_type
    match = _SEASON_RE.fullmatch(stem)
    if match:
        year = int(match.group(2))
        if _YEAR_MIN <= year <= _YEAR_MAX:
            return match.group(1), year, None, None
    return stem, None, None, None


def build_duckdb(
    data_dir: str | Path,
    output: str | Path | None = None,
    *,
    only: set[str] | None = None,
    include_actionnetwork: bool = True,
    explode: bool = False,
    progress: Callable[[TableLoad], None] | None = None,
) -> tuple[Path, list[TableLoad]]:
    """Create ``{data_dir}/cfb.duckdb`` (or ``output``) from raw + graphql dumps."""
    data_dir = Path(data_dir)
    db_path = Path(output) if output else data_dir / "cfb.duckdb"
    tmp_path = db_path.with_name(db_path.name + ".building")
    if tmp_path.exists():
        tmp_path.unlink()
    tmp_path.parent.mkdir(parents=True, exist_ok=True)

    jobs = _plan_loads(data_dir, only=only, include_actionnetwork=include_actionnetwork)
    reports: list[TableLoad] = []
    con = duckdb.connect(str(tmp_path))
    try:
        con.execute("SET preserve_insertion_order = false")
        con.execute("SET threads = 1")
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        con.execute("CREATE SCHEMA IF NOT EXISTS stg")
        con.execute("CREATE SCHEMA IF NOT EXISTS meta")
        for job in jobs:
            report = _load_job(con, job)
            reports.append(report)
            if progress is not None:
                progress(report)
        _write_meta(con, reports)
        if explode:
            reports.extend(explode_payloads(con, progress=progress))
        con.close()
        con = None
        # No unlink first: Path.replace overwrites on Windows, and unlinking opens
        # a window where a crash leaves no warehouse at all.
        tmp_path.replace(db_path)
    except Exception:
        if con is not None:
            con.close()
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return db_path, reports


_STRUCTURE_SAMPLE_ROWS = 5000
_RAW_SPINE = ("season", "week", "season_type")


def explode_payloads(
    db: str | Path | duckdb.DuckDBPyConnection,
    *,
    only: set[str] | None = None,
    progress: Callable[[TableLoad], None] | None = None,
) -> list[TableLoad]:
    """Create ``stg.*`` tables with JSON payload keys exploded into columns.

    Nested objects become prefixed columns (``offense.overall`` → ``offense_overall``).
    Arrays stay lists (row grain unchanged). ``raw`` stays as JSON.
    Load filename is kept as ``_source_file``.
    """
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    reports: list[TableLoad] = []
    try:
        con.execute("SET preserve_insertion_order = false")
        con.execute("SET threads = 1")
        con.execute("CREATE SCHEMA IF NOT EXISTS stg")
        con.execute("CREATE SCHEMA IF NOT EXISTS stg_gql")
        sources = con.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.columns
            WHERE column_name = 'payload'
              AND table_schema IN ('raw', 'graphql')
            GROUP BY 1, 2
            ORDER BY table_schema DESC, table_name
            """
        ).fetchall()
        # No `taken` set and no REST-first sort: destinations are disjoint by
        # construction now, so load order cannot change which table wins a name.
        for schema, name in sources:
            if only is not None and name not in only:
                continue
            dest_schema, dest = stg_destination(name)
            report = _explode_table(con, schema, name, dest_schema, dest)
            reports.append(report)
            if progress is not None:
                progress(report)
            con.execute("CHECKPOINT")
        for report in explode_an_children(con, progress=progress):
            reports.append(report)
        extra = backfill_gamelines_from_actionnetwork(con)
        if extra is not None:
            reports.append(extra)
            if progress is not None:
                progress(extra)
            con.execute("CHECKPOINT")
        for report in explode_stg_lists(con, only=only, progress=progress):
            reports.append(report)
        con.execute("CHECKPOINT")
        for report in promote_timestamp_columns(con, progress=progress):
            reports.append(report)
        con.execute("CHECKPOINT")
        for report in drop_dead_spine_columns(con, progress=progress):
            reports.append(report)
        con.execute("CHECKPOINT")
    finally:
        if owns_connection:
            con.close()
    return reports


# Action Network book_id → CFBD linesProvider.id when the book already exists.
_AN_BOOK_PROVIDER = {15: 888888, 71: 38}  # DraftKings, Caesars
_AN_PROVIDER_NAMES = {
    30: "Circa",
    49: "Pinnacle",
    68: "FanDuel",
    69: "BetMGM",
    75: "Bet365",
}
_AN_SCHOOL_ALIAS = {
    "Miami (FL)": "Miami",
    "San Jose State": "San José State",
    "Appalachian State": "App State",
    "Louisiana-Monroe": "UL Monroe",
    "UMass": "Massachusetts",
    "University at Albany": "UAlbany",
}


def backfill_gamelines_from_actionnetwork(
    db: str | Path | duckdb.DuckDBPyConnection,
) -> TableLoad | None:
    """Merge Action Network period + extra-book lines into ``stg_gql.game_lines``.

    CFBD ``gameLines`` is full-game only. AN history is 1H/1Q; scoreboard
    ``markets`` is full-game per book. Existing CFBD numbers win; AN fills
    nulls and inserts missing ``(gameId, linesProviderId, period)`` rows.
    """
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    try:
        stg_tables = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'stg'"
            ).fetchall()
        }
        gql_tables = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'stg_gql'"
            ).fetchall()
        }
        if not (
            "game_lines" in gql_tables
            and "games" in stg_tables
            and "an_market" in stg_tables
        ):
            return None
        return _backfill_gamelines(con, stg_tables, gql_tables)
    except Exception as exc:
        detail = str(exc).split("\n", 1)[0]
        return TableLoad(
            "stg_gql", "game_lines", 0, 0, error=f"{type(exc).__name__}: {detail}"
        )
    finally:
        if owns_connection:
            con.close()


def _backfill_gamelines(
    con: duckdb.DuckDBPyConnection, stg_tables: set[str], gql_tables: set[str]
) -> TableLoad:
    game_cols = {row[0] for row in con.execute("DESCRIBE stg.games").fetchall()}
    game_id = "gameId" if "gameId" in game_cols else "id"
    gl_types = {
        row[0]: row[1] for row in con.execute("DESCRIBE stg_gql.game_lines").fetchall()
    }
    gid_type = gl_types.get("gameId", "BIGINT")
    prov_type = gl_types.get("linesProviderId", "BIGINT")
    has_history = "an_history" in stg_tables
    has_provider = "lines_provider" in gql_tables
    alias_sql = " ".join(
        f"WHEN '{src.replace(chr(39), chr(39) + chr(39))}' THEN '{dst.replace(chr(39), chr(39) + chr(39))}'"
        for src, dst in _AN_SCHOOL_ALIAS.items()
    )
    book_sql = " ".join(
        f"WHEN {an_id} THEN {cfbd_id}" for an_id, cfbd_id in _AN_BOOK_PROVIDER.items()
    )
    loc = """list_first(list_transform(list_filter(
              TRY_CAST(teams AS JSON[]),
              t -> TRY_CAST(json_extract(t, '$.id') AS BIGINT) = {tid}
            ), t -> json_extract_string(t, '$.location')))"""
    home_loc = loc.format(tid="home_team_id")
    away_loc = loc.format(tid="away_team_id")

    history_sql = (
        """
        SELECT event_id, book_id, period, market_type, side, line, odds, _source_file
        FROM stg.an_history
        WHERE market_type IN ('spread', 'total', 'moneyline')
        """
        if has_history
        else """
        SELECT NULL::BIGINT AS event_id, NULL::INTEGER AS book_id,
               NULL::VARCHAR AS period, NULL::VARCHAR AS market_type,
               NULL::VARCHAR AS side, NULL::DOUBLE AS line, NULL::BIGINT AS odds,
               NULL::VARCHAR AS _source_file
        WHERE FALSE
        """
    )

    con.execute("DROP TABLE IF EXISTS stg_gql.game_lines__backfill")
    con.execute(
        f"""
        CREATE TABLE stg_gql.game_lines__backfill AS
        WITH map AS (
          SELECT
            sb.event_id,
            g.{_ident(game_id)} AS game_id,
            sb._source_file
          FROM stg.an_scoreboard sb
          JOIN stg.games g
            ON g.season = sb.season
           AND g.week = sb.week
           AND g.homeTeam = CASE {home_loc} {alias_sql} ELSE {home_loc} END
           AND g.awayTeam = CASE {away_loc} {alias_sql} ELSE {away_loc} END
        ),
        sb_long AS (
          -- stg.an_market already is this unnest; reading it keeps one
          -- definition of "an Action Network offering" instead of two.
          SELECT event_id, book_id, period, market_type, side, line, odds,
                 _source_file
          FROM stg.an_market
        ),
        an_long AS (
          SELECT * FROM sb_long
          WHERE market_type IN ('spread', 'total', 'moneyline')
          UNION ALL
          {history_sql}
        ),
        an_wide AS (
          SELECT
            CAST(m.game_id AS {gid_type}) AS gameId,
            CAST(
              (CASE book_id {book_sql} ELSE book_id END) AS {prov_type}
            ) AS linesProviderId,
            CASE
              WHEN period IN ('event', 'game') THEN 'game'
              ELSE period
            END AS period,
            MAX(CASE WHEN market_type = 'spread' AND side = 'home'
                     THEN line END) AS spread,
            MAX(CASE WHEN market_type = 'total' AND side IN ('over', 'under')
                     THEN line END) AS overUnder,
            MAX(CASE WHEN market_type = 'moneyline' AND side = 'home'
                     THEN odds END) AS moneylineHome,
            MAX(CASE WHEN market_type = 'moneyline' AND side = 'away'
                     THEN odds END) AS moneylineAway,
            ANY_VALUE(an_long._source_file) AS _source_file
          FROM an_long
          JOIN map m USING (event_id)
          GROUP BY 1, 2, 3
        ),
        cfbd AS (
          SELECT
            gameId,
            linesProviderId,
            'game' AS period,
            TRY_CAST(spread AS DOUBLE) AS spread,
            spreadOpen,
            TRY_CAST(overUnder AS DOUBLE) AS overUnder,
            overUnderOpen,
            moneylineHome,
            moneylineAway,
            _source_file
          FROM stg_gql.game_lines
        )
        SELECT
          COALESCE(c.gameId, a.gameId) AS gameId,
          COALESCE(c.linesProviderId, a.linesProviderId) AS linesProviderId,
          COALESCE(c.period, a.period) AS period,
          COALESCE(c.spread, a.spread) AS spread,
          c.spreadOpen,
          COALESCE(c.overUnder, a.overUnder) AS overUnder,
          c.overUnderOpen,
          COALESCE(c.moneylineHome, a.moneylineHome) AS moneylineHome,
          COALESCE(c.moneylineAway, a.moneylineAway) AS moneylineAway,
          CASE
            WHEN c.gameId IS NOT NULL AND a.gameId IS NOT NULL THEN 'cfbd+an'
            WHEN c.gameId IS NOT NULL THEN 'cfbd'
            ELSE 'actionnetwork'
          END AS line_source,
          COALESCE(c._source_file, a._source_file) AS _source_file
        FROM cfbd c
        FULL OUTER JOIN an_wide a
          ON c.gameId = a.gameId
         AND c.linesProviderId = a.linesProviderId
         AND c.period = a.period
        """
    )
    con.execute("DROP TABLE stg_gql.game_lines")
    con.execute("ALTER TABLE stg_gql.game_lines__backfill RENAME TO game_lines")

    if has_provider:
        prov_cols = {
            row[0] for row in con.execute("DESCRIBE stg_gql.lines_provider").fetchall()
        }
        pid_col = "linesProviderId" if "linesProviderId" in prov_cols else "id"
        name_rows = ", ".join(
            f"({pid}, '{name.replace(chr(39), chr(39) + chr(39))}', 'actionnetwork')"
            for pid, name in _AN_PROVIDER_NAMES.items()
        )
        con.execute(
            f"""
            INSERT INTO stg_gql.lines_provider ({_ident(pid_col)}, name, _source_file)
            SELECT v.id, v.name, v.src
            FROM (VALUES {name_rows}) v(id, name, src)
            WHERE v.id NOT IN (SELECT {_ident(pid_col)} FROM stg_gql.lines_provider)
            """
        )

    return _finish_stg_table(con, "stg_gql", "game_lines", _qualify("stg_gql", "game_lines"))

# Kickoff strings land in three shapes: REST "2023-09-02 16:00:00+00:00",
# GraphQL naive "2023-09-02T16:00:00", Action Network "...T23:30:00.000Z".
# Naive values are UTC at the source, so stamp the zone instead of letting the
# session timezone decide.
_TS_OFFSET_RE = "(Z|[+-][0-9]{2}:?[0-9]{2})$"


def _timestamp_expr(column: str) -> str:
    col = _ident(column)
    return (
        f"TRY_CAST(CASE WHEN regexp_matches({col}, '{_TS_OFFSET_RE}')"
        f" THEN {col} ELSE {col} || '+00:00' END AS TIMESTAMPTZ)"
    )


def promote_timestamp_columns(
    db: str | Path | duckdb.DuckDBPyConnection,
    *,
    progress: Callable[[TableLoad], None] | None = None,
) -> list[TableLoad]:
    """Retype ``stg.*`` VARCHAR date/time columns as ``TIMESTAMPTZ``.

    ``json_group_structure`` sees a kickoff timestamp as a JSON string, so the
    shred lands it as VARCHAR and every downstream date comparison becomes
    string math. A column is promoted only when every non-null value parses,
    which leaves name-alikes such as ``location_timezone`` (an IANA zone name)
    and ``venues.timezone`` alone without needing a deny-list. Idempotent:
    already-typed columns no longer match the VARCHAR filter.
    """
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    reports: list[TableLoad] = []
    try:
        candidates = con.execute(
            """
            SELECT table_schema, table_name, column_name
            FROM information_schema.columns
            WHERE table_schema IN ('stg', 'stg_gql')
              AND data_type = 'VARCHAR'
              AND (lower(column_name) LIKE '%date%' OR lower(column_name) LIKE '%time%')
            ORDER BY table_schema, table_name, column_name
            """
        ).fetchall()
        for schema, table, column in candidates:
            target = _qualify(schema, table)
            expr = _timestamp_expr(column)
            label = f"{table}.{column}"
            try:
                parsed, unparsed = con.execute(
                    f"""
                    SELECT
                      count(*) FILTER (WHERE {_ident(column)} IS NOT NULL),
                      count(*) FILTER (WHERE {_ident(column)} IS NOT NULL AND {expr} IS NULL)
                    FROM {target}
                    """
                ).fetchone()
                if not parsed or unparsed:
                    continue
                con.execute(
                    f"ALTER TABLE {target} ALTER COLUMN {_ident(column)} "
                    f"TYPE TIMESTAMPTZ USING {expr}"
                )
            except Exception as exc:
                detail = str(exc).splitlines()[0] if str(exc) else ""
                report = TableLoad(
                    schema, label, 0, 0, error=f"{type(exc).__name__}: {detail}"
                )
            else:
                report = TableLoad(schema, label, 1, int(parsed))
            reports.append(report)
            if progress is not None:
                progress(report)
    finally:
        if owns_connection:
            con.close()
    return reports


def drop_dead_spine_columns(
    db: str | Path | duckdb.DuckDBPyConnection,
    *,
    progress: Callable[[TableLoad], None] | None = None,
) -> list[TableLoad]:
    """Drop ``stg.*`` spine columns that are 100% NULL.

    ``season``/``week``/``season_type`` are derived from the source *filename*.
    A dataset scraped as one whole-corpus file has no season in its name, so the
    column lands entirely NULL while the API payload's own ``year``/``seasonType``
    carries the value. Leaving the empty column in place is the worst outcome:
    ``WHERE season_type = 'postseason'`` on ``stg.games`` returns zero rows with
    no error. Dropping it makes that same query fail loudly on a missing column.

    ``raw`` is left alone -- there the spine columns are load provenance, not a
    query surface. Idempotent: a dropped column no longer matches.
    """
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    reports: list[TableLoad] = []
    try:
        candidates = con.execute(
            f"""
            SELECT table_schema, table_name, column_name
            FROM information_schema.columns
            WHERE table_schema IN ('stg', 'stg_gql')
              AND column_name IN ({", ".join("'%s'" % c for c in _RAW_SPINE)})
            ORDER BY table_schema, table_name, column_name
            """
        ).fetchall()
        for schema, table, column in candidates:
            target = _qualify(schema, table)
            label = f"{table}.{column}"
            try:
                (populated,) = con.execute(
                    f"SELECT count({_ident(column)}) FROM {target}"
                ).fetchone()
                if populated:
                    continue
                con.execute(f"ALTER TABLE {target} DROP COLUMN {_ident(column)}")
            except Exception as exc:
                detail = str(exc).splitlines()[0] if str(exc) else ""
                report = TableLoad(
                    schema, label, 0, 0, error=f"{type(exc).__name__}: {detail}"
                )
            else:
                report = TableLoad(schema, label, 1, 0)
            reports.append(report)
            if progress is not None:
                progress(report)
    finally:
        if owns_connection:
            con.close()
    return reports


def flatten_stg_nested(
    db: str | Path | duckdb.DuckDBPyConnection,
    *,
    progress: Callable[[TableLoad], None] | None = None,
) -> list[TableLoad]:
    """Flatten leftover STRUCT columns on existing ``stg.*`` tables.

    Same naming as ``explode_payloads``: dotted paths become underscores.
    Tables with no STRUCT columns are skipped.
    """
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    reports: list[TableLoad] = []
    try:
        con.execute("SET preserve_insertion_order = false")
        con.execute("SET threads = 1")
        tables = con.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('stg', 'stg_gql')
            ORDER BY table_schema, table_name
            """
        ).fetchall()
        for schema, name in tables:
            report = _flatten_struct_columns(con, schema, name)
            if report is None:
                continue
            reports.append(report)
            if progress is not None:
                progress(report)
            con.execute("CHECKPOINT")
    finally:
        if owns_connection:
            con.close()
    return reports


_EXPLODE_MAX_DEPTH = 6
_CHILD_SEP = "__"
_STG_SCHEMAS = ("stg", "stg_gql")


def explode_stg_lists(
    db: str | Path | duckdb.DuckDBPyConnection,
    *,
    only: set[str] | None = None,
    progress: Callable[[TableLoad], None] | None = None,
) -> list[TableLoad]:
    """Explode leftover nested ``stg.*`` columns into child tables.

    ``explode_payloads`` flattens objects but leaves arrays as lists so parents
    keep their row grain. Each remaining LIST column becomes
    ``stg.<parent>__<column>`` at one row per element -- parent scalars carried
    down, ``<column>_idx`` holding the 1-based position -- and each JSON column
    is typed through ``json_group_structure`` first. Children are built one
    level at a time and then recursed on, so a four-deep nest such as
    ``game_player_stats.teams`` yields a table per level instead of one
    cross-producted leaf. Parents are never touched: ``_backfill_gamelines``
    still reads ``actionnetwork_scoreboard.teams`` and ``markets`` as JSON.
    """
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    reports: list[TableLoad] = []
    try:
        con.execute("SET preserve_insertion_order = false")
        con.execute("SET threads = 1")
        for schema in _STG_SCHEMAS:
            for (stale,) in con.execute(
                f"""
                SELECT table_name FROM duckdb_tables()
                WHERE schema_name = '{schema}'
                  AND contains(table_name, '{_CHILD_SEP}')
                  AND NOT ends_with(table_name, '{_CHILD_SEP}backfill')
                ORDER BY table_name
                """
            ).fetchall():
                # Scoped to the selected roots: an --only run must not drop the
                # children of every table it is not rebuilding.
                if only is not None and stale.split(_CHILD_SEP, 1)[0] not in only:
                    continue
                con.execute(f"DROP TABLE IF EXISTS {_qualify(schema, stale)}")
            roots = [
                row[0]
                for row in con.execute(
                    f"SELECT table_name FROM duckdb_tables()"
                    f" WHERE schema_name = '{schema}' ORDER BY table_name"
                ).fetchall()
            ]
            for name in roots:
                if only is not None and name not in only:
                    continue
                # explode_an_children already built this one by hand.
                if name == "an_scoreboard" or name in _AN_CHILDREN:
                    continue
                _explode_nested_columns(con, schema, name, 0, reports, progress)
    finally:
        if owns_connection:
            con.close()
    return reports


def _is_nested_type(dtype: object) -> str | None:
    text = str(dtype).strip()
    if text.endswith("[]"):
        return "list"
    if text.upper() == "JSON":
        return "json"
    return None


def _explode_nested_columns(
    con: duckdb.DuckDBPyConnection,
    schema: str,
    table: str,
    depth: int,
    reports: list[TableLoad],
    progress: Callable[[TableLoad], None] | None,
) -> None:
    if depth >= _EXPLODE_MAX_DEPTH:
        return
    nested = []
    for row in con.execute(f"DESCRIBE {_qualify(schema, table)}").fetchall():
        kind = _is_nested_type(row[1])
        if kind is not None:
            nested.append((row[0], kind))
    siblings = [col for col, _ in nested]
    for col, kind in nested:
        dest = f"{table}{_CHILD_SEP}{col}"
        report = _explode_nested_column(con, schema, table, col, kind, dest, siblings)
        reports.append(report)
        if progress is not None:
            progress(report)
        con.execute("CHECKPOINT")
        if report.error is None and report.rows:
            _explode_nested_columns(con, schema, dest, depth + 1, reports, progress)


def _explode_nested_column(
    con: duckdb.DuckDBPyConnection,
    schema: str,
    parent: str,
    col: str,
    kind: str,
    dest: str,
    siblings: list[str],
) -> TableLoad:
    source = _qualify(schema, parent)
    target = _qualify(schema, dest)
    exclude = ", ".join(_ident(name) for name in siblings)
    col_id = _ident(col)
    idx_id = _ident(f"{col}_idx")
    try:
        con.execute(f"DROP TABLE IF EXISTS {target}")
        if kind == "json":
            if not _explode_json_column(con, source, target, col, exclude):
                return TableLoad(
                    schema, dest, 0, 0, error="scalar JSON; nothing to explode"
                )
        else:
            con.execute(
                f"""
                CREATE TABLE {target} AS
                SELECT * EXCLUDE ({exclude}),
                  unnest(range(1, len({col_id}) + 1)) AS {idx_id},
                  unnest({col_id}) AS {col_id}
                FROM {source}
                WHERE {col_id} IS NOT NULL AND len({col_id}) > 0
                """
            )
        leftover = _flatten_struct_columns(con, schema, dest)
        if leftover is not None and leftover.error:
            return leftover
        rows = con.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0]
        return TableLoad(schema, dest, 1, int(rows))
    except Exception as exc:
        return _explode_failed(con, schema, target, dest, exc)


def _explode_json_column(
    con: duckdb.DuckDBPyConnection,
    source: str,
    target: str,
    col: str,
    exclude: str,
) -> bool:
    """Type a JSON column, then explode it. False when it holds only scalars."""
    col_id = _ident(col)
    idx_id = _ident(f"{col}_idx")
    key_id = _ident(f"{col}_key")
    kinds = {
        row[0]
        for row in con.execute(
            f"SELECT DISTINCT json_type({col_id}) FROM {source}"
            f" WHERE {col_id} IS NOT NULL"
        ).fetchall()
        if row[0] is not None
    }
    if kinds == {"ARRAY"}:
        keep = f"{col_id} IS NOT NULL AND json_array_length({col_id}) > 0"
        structure = con.execute(
            f"SELECT json_group_structure({col_id}) FROM {source} WHERE {keep}"
        ).fetchone()[0]
        if structure is None:
            return False
        con.execute(
            f"""
            CREATE TABLE {target} AS
            SELECT * EXCLUDE ({exclude}),
              unnest(range(1, CAST(json_array_length({col_id}) AS BIGINT) + 1)) AS {idx_id},
              unnest(json_transform({col_id}, ?)) AS {col_id}
            FROM {source}
            WHERE {keep}
            """,
            [structure],
        )
        return True
    if kinds != {"OBJECT"}:
        return False
    if _json_keys_are_numeric(con, source, col_id):
        # Action Network `markets` is keyed by book_id, so those keys are data,
        # not a schema. Unnest them into a column instead of into column names.
        value = "json_extract(p." + col_id + ", '$.\"' || t.k || '\"')"
        frm = f"FROM {source} p, unnest(json_keys(p.{col_id})) AS t(k)"
        structure = con.execute(
            f"SELECT json_group_structure({value}) {frm}"
            f" WHERE p.{col_id} IS NOT NULL"
        ).fetchone()[0]
        if structure is None:
            return False
        con.execute(
            f"""
            CREATE TABLE {target} AS
            SELECT p.* EXCLUDE ({exclude}),
              t.k AS {key_id},
              json_transform({value}, ?) AS {col_id}
            {frm}
            WHERE p.{col_id} IS NOT NULL
            """,
            [structure],
        )
        return True
    structure = con.execute(
        f"SELECT json_group_structure({col_id}) FROM {source}"
        f" WHERE {col_id} IS NOT NULL"
    ).fetchone()[0]
    if structure is None:
        return False
    con.execute(
        f"""
        CREATE TABLE {target} AS
        SELECT * EXCLUDE ({exclude}),
          json_transform({col_id}, ?) AS {col_id}
        FROM {source}
        WHERE {col_id} IS NOT NULL
        """,
        [structure],
    )
    return True


def _json_keys_are_numeric(
    con: duckdb.DuckDBPyConnection, source: str, col_id: str
) -> bool:
    row = con.execute(
        f"SELECT bool_and(regexp_full_match(k, '[0-9]+')) FROM ("
        f" SELECT DISTINCT unnest(json_keys({col_id})) AS k FROM {source}"
        f" WHERE {col_id} IS NOT NULL)"
    ).fetchone()
    return bool(row and row[0])


def stg_destination(name: str) -> tuple[str, str]:
    """``(schema, name)`` in `stg`/`stg_gql` for a raw table name.

    Pure function of the raw table name alone. A GraphQL raw table (named through
    `GQL_ENTITY_TO_RAW`, e.g. `gql_game`) resolves through `GQL_RAW_TO_ENTITY` back to
    its entity, then through `GQL_ENTITY_TO_STG` to its bare `stg_gql` destination.
    Anything else is a REST raw table name and passes through unchanged into `stg`.
    """
    entity = GQL_RAW_TO_ENTITY.get(name)
    if entity is None:
        return "stg", name
    return "stg_gql", GQL_ENTITY_TO_STG[entity]


def _null_typed_paths(structure: str) -> list[str]:
    """JSONPaths that ``json_group_structure`` typed ``"NULL"``, at any depth.

    That is what it returns for a key whose every *sampled* value was null, and
    the struct built from such a type silently discards the real values in every
    row outside the sample. `lines.spreadOpen`, `overUnderOpen` and both
    moneylines were lost warehouse-wide this way, as were `plays.wallclock` and
    the two timeout counts -- see docs/duckdb-audit-2026-09-02.md S9.

    Array levels come back as ``[*]``: ``$."lines"[*]."spreadOpen"``.
    """
    found: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, str):
            if node == "NULL":
                found.append(path)
        elif isinstance(node, dict):
            for key, value in node.items():
                walk(value, f'{path}."{key}"')
        elif isinstance(node, list):
            for value in node:
                walk(value, f"{path}[*]")

    try:
        walk(json.loads(structure), "$")
    except json.JSONDecodeError:
        return []
    return found


def _has_null_typed_key(structure: str) -> bool:
    return bool(_null_typed_paths(structure))


def _path_populated_predicate(path: str) -> str:
    """SQL that is true for rows where ``path`` holds a real (non-null) value."""
    if "[*]" in path:
        # json_extract on a wildcard path yields a JSON array of the matches;
        # keep rows where at least one element is not JSON null.
        return (
            f"json_extract(payload, '{path}') IS NOT NULL"
            f" AND len(list_filter(json_extract(payload, '{path}')::JSON[],"
            f" x -> json_type(x) <> 'NULL')) > 0"
        )
    return f"json_type(payload, '{path}') <> 'NULL'"


def _payload_structure(con: duckdb.DuckDBPyConnection, source: str) -> str | None:
    # LIMIT must wrap the scan. json_group_structure is an aggregate, so a top-level
    # LIMIT still unions every row and OOMs on plays / gamePlayerStat.
    base = (
        f"SELECT payload FROM {source} WHERE payload IS NOT NULL"
        f" LIMIT {_STRUCTURE_SAMPLE_ROWS}"
    )
    row = con.execute(f"SELECT json_group_structure(payload) FROM ({base})").fetchone()
    structure = None if row is None else row[0]
    if structure is None:
        return None

    paths = _null_typed_paths(structure)
    if not paths:
        return structure

    # Those keys were null through the whole sample, so the sample cannot type
    # them. Widening the sample only narrows the window; scanning the full column
    # OOMs on plays (measured). Instead add a targeted sample per lost path --
    # rows where THAT path is populated -- and let json_group_structure merge the
    # types across the union. Bounded, and exact for any key that appears at all.
    selects = [base]
    for path in paths:
        try:
            predicate = _path_populated_predicate(path)
            con.execute(
                f"SELECT 1 FROM {source} WHERE {predicate} LIMIT 1"
            ).fetchone()
        except duckdb.Error:
            continue  # unsupported path shape; keep the sampled type for it
        selects.append(
            f"SELECT payload FROM {source} WHERE payload IS NOT NULL AND {predicate}"
            f" LIMIT {_STRUCTURE_SAMPLE_ROWS}"
        )
    if len(selects) == 1:
        return structure

    union = " UNION ALL ".join(f"({s})" for s in selects)
    try:
        merged = con.execute(
            f"SELECT json_group_structure(payload) FROM ({union})"
        ).fetchone()
    except (duckdb.Error, MemoryError):
        return structure
    return structure if merged is None or merged[0] is None else merged[0]


def _structure_top_keys(structure: str) -> set[str]:
    try:
        parsed = json.loads(structure)
    except json.JSONDecodeError:
        return set()
    return set(parsed) if isinstance(parsed, dict) else set()


def _spine_select(con: duckdb.DuckDBPyConnection, source: str, structure: str) -> str:
    raw_cols = {row[0] for row in con.execute(f"DESCRIBE {source}").fetchall()}
    payload_keys = _structure_top_keys(structure)
    pieces = []
    for col in _RAW_SPINE:
        if col in raw_cols and col not in payload_keys:
            pieces.append(_ident(col))
    pieces.append("source_file AS _source_file")
    return ",\n              ".join(pieces)


# An Action Network offering is one price for one (book, period, market, side).
# The object is byte-identical in a history file and in the scoreboard's
# ``markets`` map, so both exploders emit these columns from ``o.value``.
_AN_OFFERING_COLS = """
              TRY_CAST(b.key AS INTEGER) AS book_id,
              {period} AS period,
              CASE {market}
                WHEN 'core_bet_type_6_team_score' THEN 'team_total'
                ELSE {market}
              END AS market_type,
              json_extract_string(o.value, '$.side') AS side,
              TRY_CAST(json_extract(o.value, '$.team_id') AS BIGINT) AS team_id,
              TRY_CAST(json_extract(o.value, '$.value') AS DOUBLE) AS line,
              TRY_CAST(json_extract(o.value, '$.odds') AS BIGINT) AS odds,
              json_extract_string(o.value, '$.market_id') AS market_id,
              json_extract_string(o.value, '$.outcome_id') AS outcome_id,
              TRY_CAST(json_extract(o.value, '$.is_live') AS BOOLEAN) AS is_live,
              json_extract_string(o.value, '$.line_status') AS line_status,
              TRY_CAST(
                json_extract(o.value, '$.odds_coefficient_score') AS DOUBLE
              ) AS odds_coefficient_score,
              TRY_CAST(
                json_extract(o.value, '$.option_type_id') AS INTEGER
              ) AS option_type_id,
              TRY_CAST(
                json_extract(o.value, '$.bet_info.money.percent') AS INTEGER
              ) AS money_pct,
              TRY_CAST(json_extract(o.value, '$.bet_info.money.value') AS BIGINT) AS money,
              TRY_CAST(
                json_extract(o.value, '$.bet_info.tickets.percent') AS INTEGER
              ) AS tickets_pct,
              TRY_CAST(
                json_extract(o.value, '$.bet_info.tickets.value') AS BIGINT
              ) AS tickets,
"""

_AN_OFFERING_JOIN = """
              json_each({src}) AS b,
              json_each(b.value) AS p,
              json_each(p.value) AS m,
              json_each(m.value) AS o
"""


def _explode_an_history(
    con: duckdb.DuckDBPyConnection, source: str, target: str, dest: str
) -> TableLoad:
    """Unpivot book->period->market maps into one row per offering.

    Generic explode turns dynamic book ids into sparse LIST columns
    (``15_firsthalf_spread``). History files are one event each; empty ``{}``
    payloads produce no rows -- which is most of them, since the scraper writes
    an empty file for an event with no history and resumes past it.
    """
    cols = _AN_OFFERING_COLS.format(
        period="p.key",
        market="COALESCE(json_extract_string(o.value, '$.type'), m.key)",
    )
    try:
        con.execute(f"DROP TABLE IF EXISTS {target}")
        con.execute(
            f"""
            CREATE TABLE {target} AS
            SELECT
              COALESCE(
                TRY_CAST(json_extract(o.value, '$.event_id') AS BIGINT),
                TRY_CAST(regexp_extract(t.source_file, 'history_(\\d+)', 1) AS BIGINT)
              ) AS event_id,
              {cols}
              t.source_file AS _source_file
            FROM {source} AS t,
              {_AN_OFFERING_JOIN.format(src="t.payload")}
            WHERE json_type(t.payload) = 'OBJECT'
              AND json_array_length(json_keys(t.payload)) > 0
            """
        )
        return _finish_stg_table(con, "stg", dest, target)
    except Exception as exc:
        return _explode_failed(con, "stg", target, dest, exc)


def _explode_an_scoreboard(
    con: duckdb.DuckDBPyConnection, source: str, target: str, dest: str
) -> TableLoad:
    """Unnest ``games[]`` to one row per event; drop league-calendar noise.

    Generic explode keeps one row per weekly file with a STRUCT[] of every
    game plus 20 ``league_*`` columns. Nested book maps stay JSON.
    """
    try:
        cols = {row[0] for row in con.execute(f"DESCRIBE {source}").fetchall()}
        season_type = (
            "t.season_type" if "season_type" in cols else "NULL::VARCHAR AS season_type"
        )
        con.execute(f"DROP TABLE IF EXISTS {target}")
        con.execute(
            f"""
            CREATE TABLE {target} AS
            SELECT
              COALESCE(
                TRY_CAST(json_extract(g, '$.id') AS BIGINT),
                TRY_CAST(json_extract(g, '$.core_id') AS BIGINT)
              ) AS event_id,
              TRY_CAST(json_extract(g, '$.core_id') AS BIGINT) AS core_id,
              COALESCE(
                TRY_CAST(json_extract(g, '$.season') AS INTEGER),
                t.season
              ) AS season,
              COALESCE(
                TRY_CAST(json_extract(g, '$.week') AS INTEGER),
                t.week
              ) AS week,
              {season_type},
              json_extract_string(g, '$.start_time') AS start_time,
              json_extract_string(g, '$.status') AS status,
              json_extract_string(g, '$.status_display') AS status_display,
              json_extract_string(g, '$.real_status') AS real_status,
              TRY_CAST(json_extract(g, '$.home_team_id') AS BIGINT) AS home_team_id,
              TRY_CAST(json_extract(g, '$.away_team_id') AS BIGINT) AS away_team_id,
              TRY_CAST(
                json_extract(g, '$.home_rotation_number') AS INTEGER
              ) AS home_rotation_number,
              TRY_CAST(
                json_extract(g, '$.away_rotation_number') AS INTEGER
              ) AS away_rotation_number,
              TRY_CAST(
                json_extract(g, '$.winning_team_id') AS BIGINT
              ) AS winning_team_id,
              TRY_CAST(json_extract(g, '$.attendance') AS INTEGER) AS attendance,
              TRY_CAST(json_extract(g, '$.num_bets') AS INTEGER) AS num_bets,
              json_extract_string(g, '$.coverage') AS coverage,
              TRY_CAST(json_extract(g, '$.league_id') AS INTEGER) AS league_id,
              json_extract_string(g, '$.league_name') AS league_name,
              json_extract_string(g, '$.broadcast.network') AS broadcast_network,
              json_extract_string(
                g, '$.broadcast.network_short'
              ) AS broadcast_network_short,
              json_extract_string(g, '$.boxscore.clock') AS clock,
              TRY_CAST(json_extract(g, '$.boxscore.period') AS INTEGER) AS period,
              TRY_CAST(
                json_extract(g, '$.boxscore.total_home_points') AS INTEGER
              ) AS home_points,
              TRY_CAST(
                json_extract(g, '$.boxscore.total_away_points') AS INTEGER
              ) AS away_points,
              TRY_CAST(
                json_extract(g, '$.boxscore.total_home_firsthalf_points') AS INTEGER
              ) AS home_firsthalf_points,
              TRY_CAST(
                json_extract(g, '$.boxscore.total_away_firsthalf_points') AS INTEGER
              ) AS away_firsthalf_points,
              TRY_CAST(
                json_extract(g, '$.boxscore.total_home_secondhalf_points') AS INTEGER
              ) AS home_secondhalf_points,
              TRY_CAST(
                json_extract(g, '$.boxscore.total_away_secondhalf_points') AS INTEGER
              ) AS away_secondhalf_points,
              TRY_CAST(
                json_extract(g, '$.boxscore.home_timeouts') AS INTEGER
              ) AS home_timeouts,
              TRY_CAST(
                json_extract(g, '$.boxscore.away_timeouts') AS INTEGER
              ) AS away_timeouts,
              json_extract_string(g, '$.boxscore.situation.display') AS situation,
              TRY_CAST(
                json_extract(g, '$.boxscore.situation.down') AS INTEGER
              ) AS "down",
              TRY_CAST(
                json_extract(g, '$.boxscore.situation.distance') AS INTEGER
              ) AS distance,
              json_extract(g, '$.boxscore.latest_odds') AS latest_odds,
              json_extract(g, '$.teams') AS teams,
              json_extract(g, '$.markets') AS markets,
              json_extract(g, '$.ranks') AS ranks,
              json_extract(g, '$.last_play') AS last_play,
              json_extract(g, '$.boxscore.linescore') AS linescore,
              t.source_file AS _source_file
            FROM {source} AS t,
              UNNEST(
                json_transform(json_extract(t.payload, '$.games'), '["JSON"]')
              ) AS u(g)
            WHERE json_extract(t.payload, '$.games') IS NOT NULL
            """
        )
        return _finish_stg_table(con, "stg", dest, target)
    except Exception as exc:
        return _explode_failed(con, "stg", target, dest, exc)


# The scoreboard's nested columns, hand-written like ``an_history`` rather than
# left to the generic recursion. The generic path names a child for the whole
# path it walked (``actionnetwork_scoreboard__markets__markets_event_spread``)
# and repeats that path on every column, so one spread price arrived as a
# 62-character column inside a 62-column table. See
# ``docs/warehouse-schema-recommendation.md`` §8.
_AN_CHILDREN = ("an_market", "an_team", "an_linescore")


def explode_an_children(
    con: duckdb.DuckDBPyConnection,
    *,
    progress: Callable[[TableLoad], None] | None = None,
) -> list[TableLoad]:
    """Build ``stg.an_market`` / ``an_team`` / ``an_linescore``.

    ``latest_odds``, ``ranks`` and ``last_play`` stay unexploded JSON on
    ``stg.an_scoreboard``: the first duplicates ``an_market``, the second
    duplicates CFBD rankings, and the third is live in-game state.
    """
    have = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'stg'"
        ).fetchall()
    }
    if "an_scoreboard" not in have:
        return []
    reports = []
    for dest, sql in (
        ("an_market", _AN_MARKET_SQL),
        ("an_team", _AN_TEAM_SQL),
        ("an_linescore", _AN_LINESCORE_SQL),
    ):
        target = _qualify("stg", dest)
        try:
            con.execute(f"DROP TABLE IF EXISTS {target}")
            con.execute(f"CREATE TABLE {target} AS {sql}")
            rows = con.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0]
            report = TableLoad("stg", dest, 1, int(rows))
        except Exception as exc:
            report = _explode_failed(con, "stg", target, dest, exc)
        reports.append(report)
        if progress is not None:
            progress(report)
        con.execute("CHECKPOINT")
    return reports


_AN_MARKET_SQL = f"""
            SELECT
              t.event_id,
              t.season,
              t.week,
              {_AN_OFFERING_COLS.format(
                  period="COALESCE(json_extract_string(o.value, '$.period'), p.key)",
                  market="COALESCE(json_extract_string(o.value, '$.type'), m.key)",
              )}
              t._source_file
            FROM stg.an_scoreboard AS t,
              {_AN_OFFERING_JOIN.format(src="t.markets")}
            WHERE t.markets IS NOT NULL
              AND json_type(t.markets) = 'OBJECT'
              AND json_array_length(json_keys(t.markets)) > 0
"""

# Logo and colour columns are dropped: presentation assets, not data.
_AN_TEAM_SQL = """
            SELECT
              t.event_id,
              t.season,
              t.week,
              TRY_CAST(json_extract(x, '$.id') AS BIGINT) AS team_id,
              TRY_CAST(json_extract(x, '$.core_id') AS BIGINT) AS core_id,
              json_extract_string(x, '$.abbr') AS abbr,
              json_extract_string(x, '$.location') AS location,
              json_extract_string(x, '$.display_name') AS display_name,
              json_extract_string(x, '$.full_name') AS full_name,
              json_extract_string(x, '$.short_name') AS short_name,
              json_extract_string(x, '$.url_slug') AS url_slug,
              json_extract_string(x, '$.conference_type') AS conference_type,
              json_extract_string(x, '$.division_type') AS division_type,
              TRY_CAST(json_extract(x, '$.standings.win') AS INTEGER) AS wins,
              TRY_CAST(json_extract(x, '$.standings.loss') AS INTEGER) AS losses,
              TRY_CAST(json_extract(x, '$.standings.ties') AS INTEGER) AS ties,
              TRY_CAST(json_extract(x, '$.standings.draw') AS INTEGER) AS draws,
              TRY_CAST(
                json_extract(x, '$.standings.overtime_losses') AS INTEGER
              ) AS overtime_losses,
              t._source_file
            FROM stg.an_scoreboard AS t,
              UNNEST(json_transform(t.teams, '["JSON"]')) AS u(x)
            WHERE t.teams IS NOT NULL
"""

_AN_LINESCORE_SQL = """
            SELECT
              t.event_id,
              t.season,
              t.week,
              TRY_CAST(json_extract(x, '$.id') AS INTEGER) AS period_id,
              json_extract_string(x, '$.abbr') AS abbr,
              json_extract_string(x, '$.display_name') AS display_name,
              json_extract_string(x, '$.full_name') AS full_name,
              TRY_CAST(json_extract(x, '$.home_points') AS INTEGER) AS home_points,
              TRY_CAST(json_extract(x, '$.away_points') AS INTEGER) AS away_points,
              t._source_file
            FROM stg.an_scoreboard AS t,
              UNNEST(json_transform(t.linescore, '["JSON"]')) AS u(x)
            WHERE t.linescore IS NOT NULL
"""


def _finish_stg_table(
    con: duckdb.DuckDBPyConnection, schema: str, dest: str, target: str
) -> TableLoad:
    _rename_stg_table_ids(con, schema, dest)
    ordered = _reorder_stg_table(con, schema, dest)
    if ordered.error:
        return ordered
    rows = con.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0]
    return TableLoad(schema, dest, 1, int(rows))


def _explode_failed(
    con: duckdb.DuckDBPyConnection, schema: str, target: str, dest: str, exc: Exception
) -> TableLoad:
    try:
        con.execute(f"DROP TABLE IF EXISTS {target}")
    except Exception:
        pass
    detail = str(exc).split("\n", 1)[0]
    return TableLoad(schema, dest, 0, 0, error=f"{type(exc).__name__}: {detail}")


def _explode_table(
    con: duckdb.DuckDBPyConnection, schema: str, name: str, dest_schema: str, dest: str
) -> TableLoad:
    source = _qualify(schema, name)
    target = _qualify(dest_schema, dest)
    if name == "an_history":
        return _explode_an_history(con, source, target, dest)
    if name == "an_scoreboard":
        return _explode_an_scoreboard(con, source, target, dest)
    try:
        structure = _payload_structure(con, source)
        if structure is None:
            return TableLoad(dest_schema, dest, 0, 0, error="empty payload")
        spine = _spine_select(con, source, structure)
        con.execute(f"DROP TABLE IF EXISTS {target}")
        con.execute(
            f"""
            CREATE TABLE {target} AS
            SELECT
              {spine},
              unnest(
                json_transform(payload, ?),
                recursive := true,
                keep_parent_names := true
              )
            FROM {source}
            """,
            [structure],
        )
        _rename_dotted_columns(con, target)
        leftover = _flatten_struct_columns(con, dest_schema, dest)
        if leftover is not None and leftover.error:
            return leftover
        _rename_stg_table_ids(con, dest_schema, dest)
        ordered = _reorder_stg_table(con, dest_schema, dest)
        if ordered.error:
            return ordered
        rows = con.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0]
        return TableLoad(dest_schema, dest, 1, int(rows))
    except Exception as exc:
        try:
            con.execute(f"DROP TABLE IF EXISTS {target}")
        except Exception:
            pass
        detail = str(exc).split("\n", 1)[0]
        return TableLoad(dest_schema, dest, 0, 0, error=f"{type(exc).__name__}: {detail}")


def _flatten_struct_columns(
    con: duckdb.DuckDBPyConnection, schema: str, name: str
) -> TableLoad | None:
    table = _qualify(schema, name)
    tmp_name = name + "__flattening"
    tmp = _qualify(schema, tmp_name)
    rewrote = False
    try:
        previous: list[str] | None = None
        for _ in range(12):
            struct_cols = [
                row[0]
                for row in con.execute(f"DESCRIBE {table}").fetchall()
                if _is_struct_type(row[1])
            ]
            if not struct_cols or struct_cols == previous:
                break
            previous = struct_cols
            con.execute(f"DROP TABLE IF EXISTS {tmp}")
            exclude = ", ".join(_ident(col) for col in struct_cols)
            packed = ", ".join(f"{_ident(col)} := {_ident(col)}" for col in struct_cols)
            con.execute(
                f"""
                CREATE TABLE {tmp} AS
                SELECT
                  * EXCLUDE ({exclude}),
                  unnest(
                    struct_pack({packed}),
                    recursive := true,
                    keep_parent_names := true
                  )
                FROM {table}
                """
            )
            con.execute(f"DROP TABLE {table}")
            con.execute(f"ALTER TABLE {tmp} RENAME TO {_ident(name)}")
            _rename_dotted_columns(con, table)
            rewrote = True
        if not rewrote:
            return None
        _rename_stg_table_ids(con, schema, name)
        ordered = _reorder_stg_table(con, schema, name)
        if ordered.error:
            return ordered
        rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return TableLoad(schema, name, 1, int(rows))
    except Exception as exc:
        try:
            con.execute(f"DROP TABLE IF EXISTS {tmp}")
        except Exception:
            pass
        detail = str(exc).split("\n", 1)[0]
        return TableLoad(schema, name, 0, 0, error=f"{type(exc).__name__}: {detail}")


def _rename_dotted_columns(con: duckdb.DuckDBPyConnection, table: str) -> None:
    cols = [row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()]
    taken = {col.lower() for col in cols}
    for col in cols:
        if "." not in col:
            continue
        dest = col.replace(".", "_")
        base = dest
        suffix = 2
        while dest.lower() in taken:
            dest = f"{base}_{suffix}"
            suffix += 1
        con.execute(
            f"ALTER TABLE {table} RENAME COLUMN {_ident(col)} TO {_ident(dest)}"
        )
        taken.discard(col.lower())
        taken.add(dest.lower())


def _is_struct_type(dtype: object) -> bool:
    text = str(dtype).strip()
    upper = text.upper()
    return upper.startswith("STRUCT") and not upper.endswith("[]")


# Written by scripts/massey_flatten.py. Ordered small-to-large so a failure
# shows up on a 137-row table before a 5M-row one.
_MASSEY_TABLES = ("massey_teams", "massey_systems", "massey_editions", "massey_ranks")

# Action Network line movement. `raw.an_history` keeps one row per offering -- its
# closing price -- because that is all the offer's own columns carry. The tick
# series lives in a nested `history[]` the exploder cannot reach without changing
# an_history's grain, so `scripts/actionnetwork_flatten.py` walks it into a flat
# CSV instead. Already flat and already using this module's market vocabulary, so
# it loads straight to `stg` like massey, no raw twin.
_AN_TICK_TABLE = "an_history_tick"

# Pinned rather than sniffed. `read_csv_auto` would type the id columns from
# whatever happens to be in the file -- BIGINT while every id parses, VARCHAR the
# first time one does not -- and the flatten regenerates this CSV on every
# `refresh_cfbd.py` run. `stg.an_history` and `stg.an_market` come out of
# `_AN_OFFERING_COLS`, where market_id/outcome_id are `json_extract_string` and
# book_id is an INTEGER cast; matching them here is what lets the three AN tables
# join without a cast on either side.
_AN_TICK_COLUMNS = {
    "event_id": "BIGINT",
    "book_id": "INTEGER",
    "period": "VARCHAR",
    "market_type": "VARCHAR",
    "side": "VARCHAR",
    "team_id": "BIGINT",
    "market_id": "VARCHAR",
    "outcome_id": "VARCHAR",
    "is_alt_market": "BOOLEAN",
    "is_live": "BOOLEAN",
    "updated_at": "TIMESTAMP WITH TIME ZONE",
    "line": "DOUBLE",
    "odds": "BIGINT",
    "line_status": "VARCHAR",
    "_source_file": "VARCHAR",
}


def _plan_loads(
    data_dir: Path,
    *,
    only: set[str] | None,
    include_actionnetwork: bool,
) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    raw_groups: dict[str, list[Path]] = {}
    raw_dir = data_dir / "raw"
    if raw_dir.is_dir():
        for path in sorted(raw_dir.glob("*.json")):
            if path.stem in _SKIP_STEMS or path.stem.startswith("_"):
                continue
            name, _, _, _ = parse_dump_stem(path.stem)
            raw_groups.setdefault(name, []).append(path)
        for name, paths in sorted(raw_groups.items()):
            if only is not None and name not in only:
                continue
            jobs.append(
                {"schema": "raw", "name": name, "paths": paths, "format": "array"}
            )

        csv_path = raw_dir / "actionnetwork_odds.csv"
        if csv_path.exists() and (only is None or "an_odds" in only):
            jobs.append(
                {
                    "schema": "raw",
                    "name": "an_odds",
                    "paths": [csv_path],
                    "format": "csv",
                }
            )

    # Massey lands already flat: `massey_flatten` maps its ids to CFBD schools and
    # writes long-format CSVs. There is no payload to explode, so these load
    # straight into `stg` rather than passing through `raw`, which is the JSON
    # mirror. `ingest/massey/` -- the scraped editions -- stays out of the glob.
    massey_dir = data_dir / "processed" / "massey"
    if massey_dir.is_dir():
        for name in _MASSEY_TABLES:
            path = massey_dir / f"{name}.csv"
            if path.exists() and (only is None or name in only):
                jobs.append(
                    {"schema": "stg", "name": name, "paths": [path], "format": "csv"}
                )

    # Same deal for the tick CSV, but gated on --skip-actionnetwork with the rest
    # of Action Network rather than loading when the AN JSON is excluded.
    if include_actionnetwork:
        tick_path = data_dir / "processed" / "actionnetwork" / f"{_AN_TICK_TABLE}.csv"
        if tick_path.exists() and (only is None or _AN_TICK_TABLE in only):
            jobs.append(
                {
                    "schema": "stg",
                    "name": _AN_TICK_TABLE,
                    "paths": [tick_path],
                    "format": "csv",
                    "columns": _AN_TICK_COLUMNS,
                }
            )

    # PFF, same deal again: `scripts/pff_flatten.py` unpivots the weekly leaderboard
    # exports and maps every franchise to its CFBD team, so these arrive flat and load
    # straight to `stg` with no raw twin. `data/raw/pff/` is not under the loader's glob --
    # it is not recursive -- so the exports never mint tables on their own.
    #
    # The types are pinned for the reason `_AN_TICK_COLUMNS` is: `read_csv_auto` would
    # type a column from whichever file it read first, and PFF declares one column
    # `integer` on a whole value and `number` otherwise. Twenty-one tables of ~30 columns
    # is too many to enumerate twice without drifting, so the table list is pinned here and
    # the types come from the rule both sides import.
    pff_dir = data_dir / "processed" / "pff"
    if pff_dir.is_dir():
        for name in PFF_TABLES:
            path = pff_dir / f"{name}.csv"
            if not path.exists() or (only is not None and name not in only):
                continue
            with path.open(encoding="utf-8", newline="") as handle:
                header = next(csv.reader(handle), [])
            jobs.append(
                {
                    "schema": "stg",
                    "name": name,
                    "paths": [path],
                    "format": "csv",
                    "columns": pff_column_types(header),
                }
            )

    # the-odds-api, the same shape again: `scripts/oddsapi_flatten.py` turns the snapshots
    # in `data/ingest/oddsapi/` into two flat CSVs, and `cfb_paths` deliberately does not
    # glob that directory, so the snapshots never mint tables on their own.
    #
    # Types pinned for a reason `read_csv_auto` cannot see: `line` is empty on every `h2h`
    # row, so a snapshot carrying only moneylines would sniff it VARCHAR and the next load
    # would refuse the file. The quota columns are nullable the same way.
    oa_dir = data_dir / "processed" / "oddsapi"
    if oa_dir.is_dir():
        for name in OA_TABLES:
            path = oa_dir / f"{name}.csv"
            if not path.exists() or (only is not None and name not in only):
                continue
            with path.open(encoding="utf-8", newline="") as handle:
                header = next(csv.reader(handle), [])
            jobs.append(
                {
                    "schema": "stg",
                    "name": name,
                    "paths": [path],
                    "format": "csv",
                    "columns": oa_column_types(header),
                }
            )

    gql_dir = data_dir / "graphql"
    if gql_dir.is_dir():
        gql_groups: dict[str, list[Path]] = {}
        for path in sorted(gql_dir.glob("*.json")):
            name, _, _, _ = parse_dump_stem(path.stem)
            gql_groups.setdefault(name, []).append(path)
        for name, paths in sorted(gql_groups.items()):
            dest = GQL_ENTITY_TO_RAW.get(name, name)
            if only is not None and name not in only and dest not in only:
                continue
            jobs.append(
                {"schema": "raw", "name": dest, "paths": paths, "format": "array"}
            )

    if include_actionnetwork:
        an_dir = data_dir / "raw" / "actionnetwork"
        if an_dir.is_dir():
            boards = sorted(an_dir.glob("scoreboard_*.json"))
            if boards and (only is None or "an_scoreboard" in only):
                jobs.append(
                    {
                        "schema": "raw",
                        "name": "an_scoreboard",
                        "paths": boards,
                        "format": "object",
                    }
                )
            histories = sorted(an_dir.glob("history_*.json"))
            if histories and (only is None or "an_history" in only):
                jobs.append(
                    {
                        "schema": "raw",
                        "name": "an_history",
                        "paths": histories,
                        "format": "object",
                    }
                )
    return jobs


def _load_job(con: duckdb.DuckDBPyConnection, job: dict[str, Any]) -> TableLoad:
    table = _qualify(job["schema"], job["name"])
    paths: list[Path] = [p for p in job["paths"] if p.stat().st_size > 0]
    if not paths:
        return TableLoad(job["schema"], job["name"], 0, 0, error="no non-empty files")
    try:
        if job["format"] == "csv":
            con.execute(
                f"CREATE TABLE {table} AS SELECT * FROM {_csv_source(job, paths)}"
            )
        else:
            con.execute(_JSON_TABLE_SQL.format(table=table))
            for path in paths:
                _insert_json_file(con, table, path)
        con.execute("CHECKPOINT")
        rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return TableLoad(job["schema"], job["name"], len(paths), int(rows))
    except Exception as exc:
        try:
            con.execute(f"DROP TABLE IF EXISTS {table}")
            con.execute("CHECKPOINT")
        except Exception:
            pass
        detail = str(exc).split("\n", 1)[0]
        return TableLoad(
            job["schema"],
            job["name"],
            len(paths),
            0,
            error=f"{type(exc).__name__}: {detail}",
        )


def _csv_source(job: dict[str, Any], paths: list[Path]) -> str:
    """`read_csv` with the job's pinned schema, else sniff it."""
    columns = job.get("columns")
    if not columns:
        return f"read_csv_auto({_sql_path_list(paths)})"
    spec = ", ".join(f"'{name}': '{dtype}'" for name, dtype in columns.items())
    return f"read_csv({_sql_path_list(paths)}, header = true, columns = {{{spec}}})"


def _insert_json_file(con: duckdb.DuckDBPyConnection, table: str, path: Path) -> None:
    json_format = _json_root_format(path)
    object_size = max(_DEFAULT_OBJECT_SIZE, path.stat().st_size + _OBJECT_SIZE_SLACK)
    _, season, week, season_type = parse_dump_stem(path.stem)
    # Bind season/week/type from the stem parser (one source of truth) — do not
    # re-parse filenames with a second in-SQL regex that can drift from grouping.
    con.execute(
        f"""
        INSERT INTO {table}
        SELECT
          json AS payload,
          filename AS source_file,
          ?::INTEGER AS season,
          ?::INTEGER AS week,
          ?::VARCHAR AS season_type
        FROM read_json_objects(
          {_sql_path_list([path])},
          format='{json_format}',
          filename=true,
          maximum_object_size={object_size}
        )
        """,
        [season, week, season_type],
    )


def _json_root_format(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        while True:
            char = handle.read(1)
            if not char:
                return "array"
            if not char.isspace():
                return "unstructured" if char == "{" else "array"


def _write_meta(con: duckdb.DuckDBPyConnection, reports: Iterable[TableLoad]) -> None:
    con.execute(
        """
        CREATE TABLE meta.load_report (
          schema VARCHAR,
          name VARCHAR,
          files INTEGER,
          rows BIGINT,
          error VARCHAR,
          loaded_at TIMESTAMP
        )
        """
    )
    loaded_at = datetime.now(timezone.utc).replace(tzinfo=None)
    for report in reports:
        con.execute(
            "INSERT INTO meta.load_report VALUES (?, ?, ?, ?, ?, ?)",
            [
                report.schema,
                report.name,
                report.files,
                report.rows,
                report.error,
                loaded_at,
            ],
        )


def _qualify(schema: str, name: str) -> str:
    return f"{_ident(schema)}.{_ident(name)}"


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _sql_path_list(paths: list[Path]) -> str:
    return "[" + ", ".join(_sql_str(p.resolve().as_posix()) for p in paths) + "]"


def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
