"""In-database discovery layer: ``meta.table_dictionary`` and ``meta.relationship``.

The warehouse is 300+ tables across four flat schemas with no view, comment or
foreign key to tell them apart, so the only way to learn that ``stg.game`` is
GraphQL-with-postseason while ``stg.games`` is REST-regular-season is to read
``cfb_system_maker/docs/data-flow-guide.md`` or open the generated HTML catalog.
Neither is reachable from a SQL prompt. This module puts that knowledge *in* the
database, as data, so it can be queried where the question is actually asked::

    SELECT * FROM meta.table_dictionary WHERE source_system = 'gql';
    SELECT * FROM meta.relationship WHERE is_lossy;

Two tables plus ``COMMENT ON TABLE``, rebuilt with ``core``:

``meta.table_dictionary``
    One row per table: which upstream system it came from, whether it is an
    exploded child and of what, and -- for the tables whose grain is genuinely
    ambiguous -- a hand-written note. Row counts live in ``meta.load_report``
    and ``duckdb_tables()``; they are deliberately not repeated here.

``meta.relationship``
    The join map, with orphan counts *measured at build time*. DuckDB has no
    ``ALTER TABLE ... ADD FOREIGN KEY``, and half these edges could not be
    foreign keys anyway: ``dim_team`` is knowingly incomplete for non-CFBD
    opponents and ``dim_week`` carries one ``postseason`` row per season, so
    real rows do not join. Recording the measured loss is more honest than a
    constraint that would fail the 05:00 rebuild.
"""

from __future__ import annotations

import duckdb

from cfb_system_maker.graphql_client import GQL_ENTITY_TO_RAW, GQL_ENTITY_TO_STG

# Vendor tables are named by prefix at flatten time, before the loader sees them.
_VENDOR_PREFIXES = (
    ("an_", "actionnetwork"),
    ("pff_", "pff"),
    ("oa_", "oddsapi"),
    ("massey_", "massey"),
)

_GQL_DESTINATIONS = {
    "raw": frozenset(GQL_ENTITY_TO_RAW.values()),
    "stg": frozenset(GQL_ENTITY_TO_STG.values()),
}


def source_system_of(schema: str, name: str) -> str:
    """Which upstream system a table came from.

    Finer than the catalog's four-way ``origin_of``: that one folds every vendor
    into ``rest``, which is wrong for the 34 ``pff_``/``oa_``/``massey_`` tables
    that never touched the CFBD REST API. ``build_warehouse_catalog.py`` keeps
    its own coarser version because its rendered HTML is pinned by tests.
    """
    if schema in ("core", "meta"):
        return schema
    for prefix, system in _VENDOR_PREFIXES:
        if name.startswith(prefix):
            return system
    if name in _GQL_DESTINATIONS.get(schema, frozenset()):
        return "gql"
    return "rest"


# Grain and disambiguation prose. Hand-written on purpose, and only for the
# tables where the name does not already answer the question: the whole Kimball
# core, and the `stg` pairs that are routinely confused for each other. The
# other ~290 tables get a NULL note rather than a generated restatement of their
# own name.
TABLE_NOTES: dict[tuple[str, str], str] = {
    # -- core dims ------------------------------------------------------------
    ("core", "dim_team"): (
        "One row per CFBD team. INCOMPLETE: opponents outside CFBD's team table "
        "get name-derived ids and are absent here. Always LEFT JOIN."
    ),
    ("core", "dim_conference"): "One row per conference.",
    ("core", "dim_venue"): "One row per venue: city, dome, grass, capacity, elevation.",
    ("core", "dim_week"): (
        "One row per season x week x season_type. Carries a single 'postseason' "
        "row per season, so postseason games do not join to a week."
    ),
    ("core", "dim_lines_provider"): (
        "One row per sportsbook on the merged line tape. DraftKings aliases "
        "collapse to one key."
    ),
    ("core", "dim_coach"): "One row per coach: id, first and last name.",
    ("core", "dim_recruit"): "One row per recruit (GraphQL).",
    ("core", "dim_draft_pick"): "One row per NFL draft pick: year x round x pick.",
    # -- core facts -----------------------------------------------------------
    ("core", "fact_game"): (
        "One row per game, 2012+, REST-sourced. The grain every other fact hangs "
        "off. has_line / selected_spread / selected_total are REST-defined. "
        "Teams and conferences are already denormalised onto the row."
    ),
    ("core", "fact_game_historical"): (
        "One row per game BEFORE 2012, from GraphQL stg.game. Disjoint from "
        "fact_game by season; union the two for a full history."
    ),
    ("core", "fact_game_line"): (
        "One row per game x sportsbook. _source marks rest / gql / both; where "
        "the two disagree REST wins and the loser is kept in "
        "fact_game_line_conflicts."
    ),
    ("core", "fact_game_line_conflicts"): (
        "Rows where the REST and GraphQL line tapes disagreed for a game x book. "
        "Audit trail, not a join target."
    ),
    ("core", "fact_game_team"): (
        "Two rows per game, one per side, carrying running (pre-game) stats. "
        "Same code path as the app's running_stats."
    ),
    ("core", "fact_game_odds"): (
        "One row per event x book x market x side x pulled_at snapshot, from "
        "the-odds-api. Starts 2026-09-09; nothing earlier exists. pulled_at is "
        "second-resolution and shared by every row of a snapshot run. game_id is "
        "NULL where the odds event did not match a CFBD game."
    ),
    ("core", "fact_coach_season"): (
        "One row per coach x season x team. team_id is NULL where the school did "
        "not resolve; unmatched coaches land in coach_season_unmatched."
    ),
    ("core", "fact_team_talent"): (
        "One row per season x school. team_id is NULL for schools outside "
        "dim_team, so season x team_id is NOT unique."
    ),
    ("core", "coach_name_conflicts"): "Coaches whose name resolved to more than one id.",
    ("core", "coach_season_unmatched"): (
        "Coach seasons whose school did not resolve to a team."
    ),
    ("core", "v_game"): (
        "VIEW. fact_game with venue, week bounds and the selected spread and "
        "total lines already joined. The two lines are joined separately: their "
        "provider keys differ on 2,943 games, so one join returns the wrong "
        "book's number for one market. Carries no derived result column."
    ),
    # -- meta -----------------------------------------------------------------
    ("meta", "load_report"): (
        "One row per load job of the last rebuild: schema, name, files, rows, "
        "error, loaded_at. Start here when a table looks empty."
    ),
    ("meta", "table_dictionary"): "One row per table in this warehouse. You are here.",
    ("meta", "relationship"): (
        "One row per known join between core tables, with the orphan count "
        "measured at build time. Stands in for foreign keys, which DuckDB cannot "
        "add via ALTER TABLE."
    ),
    # -- stg colliders: the pairs that get confused ---------------------------
    ("stg", "games"): (
        "REST games, REGULAR SEASON ONLY. For postseason completeness use "
        "stg.game (GraphQL). These two are not the same set."
    ),
    ("stg", "game"): (
        "GraphQL games, INCLUDES POSTSEASON, and the source of record for "
        "season-type completeness. Not to be confused with REST stg.games."
    ),
    ("stg", "calendar"): "REST calendar. stg.calendar_gql is the GraphQL twin.",
    ("stg", "calendar_gql"): (
        "GraphQL calendar. Keeps its season in `year` with `season` entirely "
        "NULL -- which is why dim_week is built from raw.calendar instead."
    ),
    ("stg", "conferences"): "REST conferences. stg.conference is the GraphQL twin.",
    ("stg", "conference"): "GraphQL conferences. stg.conferences is the REST twin.",
    ("stg", "draft_picks"): "REST draft picks. stg.draft_picks_gql is the GraphQL twin.",
    ("stg", "draft_picks_gql"): (
        "GraphQL draft picks; wider and deeper than the REST twin. Source for "
        "core.dim_draft_pick."
    ),
    ("stg", "predicted_points"): (
        "REST predicted points. stg.predicted_points_gql is the GraphQL twin."
    ),
    ("stg", "predicted_points_gql"): "GraphQL predicted points.",
    ("stg", "recruits"): "REST recruits. stg.recruit is the GraphQL twin.",
    ("stg", "recruit"): "GraphQL recruits; the source for core.dim_recruit.",
    ("stg", "coaches"): (
        "REST coaches, one row per coach with seasons nested (see "
        "stg.coaches__seasons)."
    ),
    ("stg", "coach"): "GraphQL coaches, flat. The source for core.dim_coach.",
    ("stg", "coach_season"): (
        "GraphQL coach seasons; the source for core.fact_coach_season."
    ),
    ("stg", "coach_seasons"): (
        "REST coach seasons. NOT the source of core.fact_coach_season."
    ),
    ("stg", "lines"): (
        "REST betting lines, one row per game with the books nested. The books "
        "themselves are in stg.lines__lines."
    ),
    ("stg", "lines__lines"): "One row per game x book, unnested from stg.lines.",
    ("stg", "game_lines"): (
        "GraphQL line tape, widened by the loader with `period` and `line_source` "
        "and merged with the Action Network 1H/1Q and extra-book lines. Filter "
        "period='game' for full-game lines."
    ),
    ("stg", "an_history_tick"): (
        "Action Network line-movement tape, one row per observed tick. The only "
        "line movement before 2026-09-09. Schema pinned by "
        "scripts/check_an_tick_pin.py."
    ),
    ("stg", "teams"): (
        "REST teams, all classifications. stg.fbs_teams is the FBS-only pull."
    ),
    ("stg", "fbs_teams"): (
        "REST FBS teams only. Together with stg.teams this builds core.dim_team."
    ),
}

# Known joins between core tables. Hand-listed -- this is the set that is
# actually written, not an attempt at completeness. `orphan_rows` is measured on
# every build and `is_lossy` derives from it, so neither can go stale.
_EDGES: tuple[tuple[str, str, str, str, str], ...] = (
    ("fact_game", "venue_id", "dim_venue", "venue_id", ""),
    (
        "fact_game",
        "season,week,season_type",
        "dim_week",
        "season,week,season_type",
        "Postseason games do not join: dim_week has one 'postseason' row per season.",
    ),
    (
        "fact_game",
        "home_team_id",
        "dim_team",
        "team_id",
        "Opponents outside CFBD's team table are absent from dim_team.",
    ),
    (
        "fact_game",
        "away_team_id",
        "dim_team",
        "team_id",
        "Opponents outside CFBD's team table are absent from dim_team.",
    ),
    ("fact_game_line", "game_id", "fact_game", "game_id", ""),
    ("fact_game_line", "provider_key", "dim_lines_provider", "provider_key", ""),
    ("fact_game_team", "game_id", "fact_game", "game_id", ""),
    (
        "fact_game_team",
        "team_id",
        "dim_team",
        "team_id",
        "Opponents outside CFBD's team table are absent from dim_team.",
    ),
    ("fact_game_odds", "game_id", "fact_game", "game_id", ""),
    ("fact_coach_season", "coach_id", "dim_coach", "coach_id", ""),
    ("fact_team_talent", "team_id", "dim_team", "team_id", ""),
)


def _table_exists(con: duckdb.DuckDBPyConnection, schema: str, name: str) -> bool:
    return bool(
        con.execute(
            "SELECT 1 FROM duckdb_tables() WHERE schema_name = ? AND table_name = ?",
            [schema, name],
        ).fetchone()
    )


def _view_exists(con: duckdb.DuckDBPyConnection, schema: str, name: str) -> bool:
    return bool(
        con.execute(
            "SELECT 1 FROM duckdb_views()"
            " WHERE schema_name = ? AND view_name = ? AND NOT internal",
            [schema, name],
        ).fetchone()
    )


def _columns(con: duckdb.DuckDBPyConnection, schema: str, name: str) -> set[str]:
    return {
        r[0]
        for r in con.execute(
            "SELECT column_name FROM duckdb_columns()"
            " WHERE schema_name = ? AND table_name = ?",
            [schema, name],
        ).fetchall()
    }


def _measure_edge(
    con: duckdb.DuckDBPyConnection,
    child: str,
    child_cols: str,
    parent: str,
    parent_cols: str,
) -> tuple[int, int] | None:
    """Return (orphan_rows, null_key_rows) for one edge, or None if a side is missing.

    An orphan is a row whose key is fully populated but matches no parent. Rows
    with a NULL key are counted separately: they are unjoinable but not broken,
    which is the distinction a foreign key would blur.

    Missing means missing *columns* as well as missing tables: ``build_core``
    skips a merge whose ``stg`` source is absent, so ``core`` can be partial or a
    table can arrive narrower than usual. Measuring must degrade the same way the
    build does, or the dictionary turns a degraded build into a failed one.
    """
    if not (_table_exists(con, "core", child) and _table_exists(con, "core", parent)):
        return None
    cc = [c.strip() for c in child_cols.split(",")]
    pc = [c.strip() for c in parent_cols.split(",")]
    if not set(cc) <= _columns(con, "core", child):
        return None
    if not set(pc) <= _columns(con, "core", parent):
        return None
    on = " AND ".join(f'c."{a}" = p."{b}"' for a, b in zip(cc, pc))
    populated = " AND ".join(f'c."{a}" IS NOT NULL' for a in cc)
    orphans = con.execute(
        f"""
        SELECT count(*) FROM core.{child} c
        LEFT JOIN core.{parent} p ON {on}
        WHERE {populated} AND p."{pc[0]}" IS NULL
        """
    ).fetchone()[0]
    nulls = con.execute(
        f"SELECT count(*) FROM core.{child} c WHERE NOT ({populated})"
    ).fetchone()[0]
    return int(orphans), int(nulls)


def build_dictionary(con: duckdb.DuckDBPyConnection) -> None:
    """Rebuild ``meta.table_dictionary`` / ``meta.relationship`` and re-apply comments.

    Both tables are created before the census is taken, so the dictionary always
    describes itself and the relationship map. Populating first and creating
    second makes the two rows appear only when a *previous* build happened to
    leave the tables behind, which is a census that depends on history rather
    than on the warehouse in front of you.
    """
    con.execute("CREATE SCHEMA IF NOT EXISTS meta")
    _create_meta_tables(con)
    _fill_table_dictionary(con)
    _fill_relationship(con)
    _apply_comments(con)


def _create_meta_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DROP TABLE IF EXISTS meta.table_dictionary")
    con.execute(
        """
        CREATE TABLE meta.table_dictionary (
          schema_name       VARCHAR NOT NULL,
          table_name        VARCHAR NOT NULL,
          object_type       VARCHAR NOT NULL,
          source_system     VARCHAR NOT NULL,
          is_exploded_child BOOLEAN NOT NULL,
          parent_table      VARCHAR,
          column_count      INTEGER NOT NULL,
          note              VARCHAR,
          PRIMARY KEY (schema_name, table_name)
        )
        """
    )
    con.execute("DROP TABLE IF EXISTS meta.relationship")
    con.execute(
        """
        CREATE TABLE meta.relationship (
          child_table     VARCHAR NOT NULL,
          child_columns   VARCHAR NOT NULL,
          parent_table    VARCHAR NOT NULL,
          parent_columns  VARCHAR NOT NULL,
          orphan_rows     BIGINT  NOT NULL,
          null_key_rows   BIGINT  NOT NULL,
          is_lossy        BOOLEAN NOT NULL,
          note            VARCHAR,
          PRIMARY KEY (child_table, child_columns, parent_table)
        )
        """
    )


def _fill_table_dictionary(con: duckdb.DuckDBPyConnection) -> None:
    """Views are listed alongside tables.

    A table of contents that omits ``core.v_game`` -- the one object built
    specifically to be queried directly -- sends people back to the raw facts it
    exists to spare them. The generated HTML catalog reads ``duckdb_tables()``
    only and so does not show it; this is the surface that does.
    """
    objects = con.execute(
        """
        SELECT schema_name, table_name AS name, 'table' AS object_type, column_count
        FROM duckdb_tables()
        WHERE schema_name IN ('raw', 'stg', 'core', 'meta')
        UNION ALL
        SELECT v.schema_name, v.view_name, 'view', count(c.column_name)
        FROM duckdb_views() v
        LEFT JOIN duckdb_columns() c
          ON c.schema_name = v.schema_name AND c.table_name = v.view_name
        WHERE v.schema_name IN ('raw', 'stg', 'core', 'meta') AND NOT v.internal
        GROUP BY 1, 2, 3
        ORDER BY 1, 2
        """
    ).fetchall()
    rows = [
        (
            schema,
            name,
            object_type,
            source_system_of(schema, name),
            "__" in name,
            name.split("__", 1)[0] if "__" in name else None,
            int(column_count),
            TABLE_NOTES.get((schema, name)),
        )
        for schema, name, object_type, column_count in objects
    ]
    if rows:
        con.executemany(
            "INSERT INTO meta.table_dictionary VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows
        )


def _fill_relationship(con: duckdb.DuckDBPyConnection) -> None:
    rows = []
    for child, child_cols, parent, parent_cols, note in _EDGES:
        measured = _measure_edge(con, child, child_cols, parent, parent_cols)
        if measured is None:
            continue
        orphans, nulls = measured
        rows.append(
            (
                child,
                child_cols,
                parent,
                parent_cols,
                orphans,
                nulls,
                orphans > 0,
                note or None,
            )
        )
    if rows:
        con.executemany(
            "INSERT INTO meta.relationship VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows
        )


def _apply_comments(con: duckdb.DuckDBPyConnection) -> None:
    """Mirror the notes onto the tables themselves, so ``duckdb_tables().comment``
    and any client's object browser show them without knowing about the dictionary.

    ``COMMENT ON`` takes no bind parameter in DuckDB, so the note is inlined as a
    quoted literal. Every note in ``TABLE_NOTES`` is ours, but escape the quote
    anyway rather than rely on that staying true.
    """
    for (schema, name), note in TABLE_NOTES.items():
        if _table_exists(con, schema, name):
            kind = "TABLE"
        elif _view_exists(con, schema, name):
            kind = "VIEW"
        else:
            continue
        literal = note.replace("'", "''")
        con.execute(f"COMMENT ON {kind} {schema}.{name} IS '{literal}'")
