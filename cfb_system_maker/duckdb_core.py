"""Build ``core.*`` Kimball tables from an existing raw/stg DuckDB warehouse.

Phase 1a–1c: dims, fact_game, fact_game_line, fact_game_team.
See docs/duckdb-core-ddl.md and docs/duckdb-warehouse-plan.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from cfb_system_maker.models import GameRecord
from cfb_system_maker.normalize import (
    _first,
    _optional_float,
    _optional_int,
    _select_line,
    _select_total,
)
from cfb_system_maker.running_stats import compute_running_stats

# CFBD seasonType values seen on disk (stg.games), including spring slate.
_SEASON_TYPES = ("regular", "postseason", "spring_regular", "spring_postseason")


def build_core(
    db: str | Path,
    *,
    provider: str = "consensus",
) -> list[str]:
    """Create/replace Phase 1a–1c ``core`` tables in ``db``. Returns table names built."""
    path = Path(db)
    if not path.exists():
        raise FileNotFoundError(f"No DuckDB file at {path}")
    con = duckdb.connect(str(path))
    try:
        con.execute("SET preserve_insertion_order = false")
        con.execute("CREATE SCHEMA IF NOT EXISTS core")
        built: list[str] = []
        _build_dim_week(con)
        built.append("dim_week")
        _build_dim_conference(con)
        built.append("dim_conference")
        _build_dim_team(con)
        built.append("dim_team")
        _build_dim_venue(con)
        built.append("dim_venue")
        _build_fact_game(con, provider=provider)
        built.append("fact_game")
        _build_fact_game_line(con)
        built.append("fact_game_line")
        _build_dim_lines_provider(con)
        built.append("dim_lines_provider")
        _build_fact_game_team(con)
        built.append("fact_game_team")
        if _build_fact_game_odds(con):
            built.append("fact_game_odds")
        _add_phase_1_indexes(con)
        con.execute("CHECKPOINT")
        return built
    finally:
        con.close()


def _build_dim_week(con: duckdb.DuckDBPyConnection) -> None:
    """Week spine, sourced from ``raw.calendar``'s JSON payload.

    Not ``stg.calendar``: the REST calendar is never exploded into ``stg``, and
    the only staged calendar (``stg_gql.calendar``) keeps its season in ``year``
    with the ``season`` column entirely NULL. ``raw.calendar``'s payload carries
    ``season``/``seasonType``/``week``/``startDate``/``endDate`` outright, so read
    it with ``json_extract`` the way ``_build_dim_team`` reads ``raw.teams``.

    This is what bounds ``core`` to 2012+ (see ``CORE_MIN_SEASON``).
    """
    season_in = ", ".join(repr(s) for s in _SEASON_TYPES)
    con.execute("DROP TABLE IF EXISTS core.dim_week")
    con.execute(
        f"""
        CREATE TABLE core.dim_week AS
        SELECT season, week, season_type, start_date, end_date
        FROM (
          SELECT
            CAST(json_extract(payload, '$.season') AS INTEGER) AS season,
            CAST(json_extract(payload, '$.week') AS INTEGER) AS week,
            json_extract_string(payload, '$.seasonType') AS season_type,
            TRY_CAST(json_extract_string(payload, '$.startDate') AS TIMESTAMPTZ)
              AS start_date,
            TRY_CAST(json_extract_string(payload, '$.endDate') AS TIMESTAMPTZ)
              AS end_date,
            ROW_NUMBER() OVER (
              PARTITION BY
                CAST(json_extract(payload, '$.season') AS INTEGER),
                CAST(json_extract(payload, '$.week') AS INTEGER),
                json_extract_string(payload, '$.seasonType')
              ORDER BY TRY_CAST(
                json_extract_string(payload, '$.startDate') AS TIMESTAMPTZ
              ) NULLS LAST
            ) AS rn
          FROM raw.calendar
          WHERE json_extract(payload, '$.season') IS NOT NULL
            AND json_extract(payload, '$.week') IS NOT NULL
            AND json_extract_string(payload, '$.seasonType') IN ({season_in})
        )
        WHERE rn = 1
        """
    )
    con.execute(
        """
        ALTER TABLE core.dim_week
        ADD PRIMARY KEY (season, week, season_type)
        """
    )


def _build_dim_conference(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DROP TABLE IF EXISTS core.dim_conference")
    con.execute(
        """
        CREATE TABLE core.dim_conference AS
        SELECT
          CAST(conferenceId AS INTEGER) AS conference_id,
          CAST(name AS VARCHAR) AS name,
          CAST(abbreviation AS VARCHAR) AS abbreviation,
          CAST(shortName AS VARCHAR) AS short_name,
          CAST(classification AS VARCHAR) AS classification
        FROM stg.conferences
        WHERE conferenceId IS NOT NULL AND name IS NOT NULL
        """
    )
    con.execute("ALTER TABLE core.dim_conference ADD PRIMARY KEY (conference_id)")


def _build_dim_team(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DROP TABLE IF EXISTS core.dim_team")
    con.execute(
        """
        CREATE TABLE core.dim_team AS
        WITH ranked AS (
          SELECT
            CAST(json_extract(payload, '$.id') AS INTEGER) AS team_id,
            json_extract_string(payload, '$.school') AS school,
            json_extract_string(payload, '$.abbreviation') AS abbreviation,
            json_extract_string(payload, '$.classification') AS classification,
            season,
            ROW_NUMBER() OVER (
              PARTITION BY CAST(json_extract(payload, '$.id') AS INTEGER)
              ORDER BY season DESC NULLS LAST
            ) AS rn
          FROM raw.teams
          WHERE json_extract(payload, '$.id') IS NOT NULL
            AND json_extract_string(payload, '$.school') IS NOT NULL
        ),
        fbs_latest AS (
          SELECT DISTINCT CAST(json_extract(payload, '$.id') AS INTEGER) AS team_id
          FROM raw.fbs_teams
          WHERE season = (SELECT MAX(season) FROM raw.fbs_teams WHERE season IS NOT NULL)
        )
        SELECT
          r.team_id,
          r.school,
          r.abbreviation,
          r.classification,
          (f.team_id IS NOT NULL) AS is_fbs
        FROM ranked r
        LEFT JOIN fbs_latest f USING (team_id)
        WHERE r.rn = 1
        """
    )
    con.execute("ALTER TABLE core.dim_team ADD PRIMARY KEY (team_id)")


def _build_dim_venue(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DROP TABLE IF EXISTS core.dim_venue")
    con.execute(
        """
        CREATE TABLE core.dim_venue AS
        SELECT
          CAST(venueId AS INTEGER) AS venue_id,
          CAST(name AS VARCHAR) AS name,
          CAST(city AS VARCHAR) AS city,
          CAST(state AS VARCHAR) AS state,
          CAST(dome AS BOOLEAN) AS dome,
          CAST(grass AS BOOLEAN) AS grass,
          CAST(capacity AS INTEGER) AS capacity,
          TRY_CAST(elevation AS DOUBLE) AS elevation
        FROM stg.venues
        WHERE venueId IS NOT NULL
        """
    )
    con.execute("ALTER TABLE core.dim_venue ADD PRIMARY KEY (venue_id)")


def _provider_key(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _lines_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, (list, tuple)):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            out.append(item)
        else:
            # DuckDB STRUCT → dict via mapping
            try:
                out.append(dict(item))
            except Exception:
                continue
    return out


def _build_fact_game(con: duckdb.DuckDBPyConnection, *, provider: str) -> None:
    """All REST games + has_line; selected books clone normalize._select_line/_select_total."""
    con.execute("DROP TABLE IF EXISTS core.fact_game")
    con.execute(
        f"""
        CREATE TABLE core.fact_game (
          game_id INTEGER,
          season INTEGER NOT NULL,
          week INTEGER NOT NULL,
          season_type VARCHAR NOT NULL,
          start_date TIMESTAMPTZ,
          completed BOOLEAN,
          has_line BOOLEAN NOT NULL,
          venue_id INTEGER,
          home_team_id INTEGER NOT NULL,
          away_team_id INTEGER NOT NULL,
          home_conference_id INTEGER,
          away_conference_id INTEGER,
          home_team VARCHAR NOT NULL,
          away_team VARCHAR NOT NULL,
          home_conference VARCHAR,
          away_conference VARCHAR,
          home_points INTEGER,
          away_points INTEGER,
          selected_spread_provider_key VARCHAR,
          selected_total_provider_key VARCHAR,
          selected_spread DOUBLE,
          selected_total DOUBLE,
          CHECK (season_type IN ({", ".join(repr(s) for s in _SEASON_TYPES)})),
          CHECK (home_team_id <> away_team_id),
          CHECK (
            NOT has_line
            OR selected_spread IS NOT NULL
            OR selected_total IS NOT NULL
          )
        )
        """
    )

    lines_by_id: dict[int, list[dict[str, Any]]] = {}
    for game_id, lines_val in con.execute("SELECT gameId, lines FROM stg.lines").fetchall():
        if game_id is None:
            continue
        lines_by_id[int(game_id)] = _lines_list(lines_val)

    conf_rows = con.execute(
        "SELECT conference_id, name FROM core.dim_conference"
    ).fetchall()
    conf_by_name = {str(name): int(cid) for cid, name in conf_rows if name is not None}

    # `core` is an explicit 2012+ layer: the REST calendar that feeds dim_week only
    # goes back to 2012, while stg.games reaches 1992. Bounding here keeps every
    # fact row joinable to a week; the alternative (letting 1992-2011 games in with
    # no dim_week partner) makes an inner join silently drop them instead.
    games = con.execute(
        """
        SELECT
          gameId, season, week, seasonType, startDate, completed, venueId,
          homeTeamId, awayTeamId, homeTeam, awayTeam, homeConference, awayConference,
          homePoints, awayPoints
        FROM stg.games
        WHERE season >= (SELECT min(season) FROM core.dim_week)
        """
    ).fetchall()

    insert_sql = """
        INSERT INTO core.fact_game VALUES (
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """
    batch: list[list[Any]] = []
    for row in games:
        (
            game_id,
            season,
            week,
            season_type,
            start_date,
            completed,
            venue_id,
            home_id,
            away_id,
            home_team,
            away_team,
            home_conference,
            away_conference,
            home_points,
            away_points,
        ) = row
        if game_id is None or home_id is None or away_id is None:
            continue
        if home_team is None or away_team is None:
            continue
        if season is None or week is None or season_type is None:
            continue
        if season_type not in _SEASON_TYPES:
            continue
        if int(home_id) == int(away_id):
            continue

        lines = lines_by_id.get(int(game_id), [])
        selected = _select_line(lines, provider)
        has_line = selected is not None
        spread_provider = total_provider = None
        spread = total = None
        if selected is not None:
            spread_provider = _provider_key(_first(selected, "provider"))
            spread = _optional_float(_first(selected, "spread"))
            total_row = _select_total(lines, selected)
            total_provider = _provider_key(_first(total_row, "provider"))
            total = _optional_float(_first(total_row, "overUnder", "over_under", "total"))
            if spread is None and total is None:
                has_line = False
                spread_provider = total_provider = None

        home_conf_id = conf_by_name.get(str(home_conference)) if home_conference else None
        away_conf_id = conf_by_name.get(str(away_conference)) if away_conference else None

        batch.append(
            [
                int(game_id),
                int(season),
                int(week),
                str(season_type),
                start_date,
                completed,
                has_line,
                int(venue_id) if venue_id is not None else None,
                int(home_id),
                int(away_id),
                home_conf_id,
                away_conf_id,
                str(home_team),
                str(away_team),
                str(home_conference) if home_conference is not None else None,
                str(away_conference) if away_conference is not None else None,
                int(home_points) if home_points is not None else None,
                int(away_points) if away_points is not None else None,
                spread_provider,
                total_provider,
                spread,
                total,
            ]
        )
        if len(batch) >= 2000:
            con.executemany(insert_sql, batch)
            batch.clear()
    if batch:
        con.executemany(insert_sql, batch)

    con.execute("ALTER TABLE core.fact_game ADD PRIMARY KEY (game_id)")


def _build_fact_game_line(con: duckdb.DuckDBPyConnection) -> None:
    """Unnest REST ``stg.lines.lines`` → grain ``(game_id, provider_key)``.

    Open nulls stay null (fail-closed). Home-relative spread matches GameRecord.
    Duplicate provider rows for the same game keep the first occurrence.
    """
    con.execute("DROP TABLE IF EXISTS core.fact_game_line")
    con.execute(
        """
        CREATE TABLE core.fact_game_line (
          game_id INTEGER NOT NULL,
          provider_key VARCHAR NOT NULL,
          spread_close DOUBLE,
          spread_open DOUBLE,
          total_close DOUBLE,
          total_open DOUBLE,
          moneyline_home INTEGER,
          moneyline_away INTEGER,
          formatted_spread VARCHAR
        )
        """
    )

    insert_sql = """
        INSERT INTO core.fact_game_line VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    batch: list[list[Any]] = []
    seen: set[tuple[int, str]] = set()
    # Same 2012+ bound as fact_game, inherited rather than restated: a line row for
    # a game the spine excluded would be an orphan.
    for game_id, lines_val in con.execute(
        "SELECT gameId, lines FROM stg.lines"
        " WHERE gameId IN (SELECT game_id FROM core.fact_game)"
    ).fetchall():
        if game_id is None:
            continue
        gid = int(game_id)
        for line in _lines_list(lines_val):
            key = _provider_key(_first(line, "provider"))
            if key is None:
                continue
            pk = (gid, key)
            if pk in seen:
                continue
            seen.add(pk)
            formatted = _first(line, "formattedSpread", "formatted_spread")
            batch.append(
                [
                    gid,
                    key,
                    _optional_float(_first(line, "spread")),
                    _optional_float(_first(line, "spreadOpen", "spread_open")),
                    _optional_float(_first(line, "overUnder", "over_under", "total")),
                    _optional_float(
                        _first(line, "overUnderOpen", "over_under_open", "total_open")
                    ),
                    _optional_int(_first(line, "homeMoneyline", "home_moneyline")),
                    _optional_int(_first(line, "awayMoneyline", "away_moneyline")),
                    str(formatted) if formatted is not None else None,
                ]
            )
            if len(batch) >= 2000:
                con.executemany(insert_sql, batch)
                batch.clear()
    if batch:
        con.executemany(insert_sql, batch)

    con.execute(
        "ALTER TABLE core.fact_game_line ADD PRIMARY KEY (game_id, provider_key)"
    )


def _build_dim_lines_provider(con: duckdb.DuckDBPyConnection) -> None:
    """Distinct books on the full line tape (+ selected close keys)."""
    con.execute("DROP TABLE IF EXISTS core.dim_lines_provider")
    con.execute(
        """
        CREATE TABLE core.dim_lines_provider AS
        SELECT DISTINCT provider_key
        FROM (
          SELECT provider_key FROM core.fact_game_line
          UNION
          SELECT selected_spread_provider_key AS provider_key FROM core.fact_game
          UNION
          SELECT selected_total_provider_key FROM core.fact_game
        )
        WHERE provider_key IS NOT NULL
        """
    )
    con.execute("ALTER TABLE core.dim_lines_provider ADD PRIMARY KEY (provider_key)")


def _build_fact_game_team(con: duckdb.DuckDBPyConnection) -> None:
    """Entering-game stats at ``(game_id, team_id)`` — clones ``running_stats.py``."""
    con.execute("DROP TABLE IF EXISTS core.fact_game_team")
    con.execute(
        """
        CREATE TABLE core.fact_game_team (
          game_id INTEGER NOT NULL,
          team_id INTEGER NOT NULL,
          home_away VARCHAR NOT NULL,
          games_played INTEGER NOT NULL,
          win_pct DOUBLE,
          ats_pct DOUBLE,
          streak INTEGER,
          ats_streak INTEGER,
          PRIMARY KEY (game_id, team_id),
          UNIQUE (game_id, home_away),
          CHECK (home_away IN ('home', 'away')),
          CHECK (games_played >= 0)
        )
        """
    )

    rows = con.execute(
        """
        SELECT
          game_id, season, week, season_type, start_date,
          home_team_id, away_team_id, home_team, away_team,
          home_conference, away_conference, home_points, away_points,
          selected_spread_provider_key, selected_spread, selected_total
        FROM core.fact_game
        """
    ).fetchall()

    games: list[GameRecord] = []
    start_dates: dict[int, str] = {}
    side_ids: dict[tuple[int, str], tuple[int, str]] = {}
    for row in rows:
        (
            game_id,
            season,
            week,
            season_type,
            start_date,
            home_team_id,
            away_team_id,
            home_team,
            away_team,
            home_conference,
            away_conference,
            home_points,
            away_points,
            provider_key,
            spread,
            total,
        ) = row
        gid = int(game_id)
        games.append(
            GameRecord(
                game_id=gid,
                season=int(season),
                week=int(week),
                home_team=str(home_team),
                away_team=str(away_team),
                home_conference=home_conference,
                away_conference=away_conference,
                home_points=int(home_points) if home_points is not None else None,
                away_points=int(away_points) if away_points is not None else None,
                provider=provider_key,
                spread=spread,
                total=total,
                season_type=str(season_type),
            )
        )
        if start_date is not None:
            start_dates[gid] = str(start_date)
        side_ids[(gid, str(home_team))] = (int(home_team_id), "home")
        side_ids[(gid, str(away_team))] = (int(away_team_id), "away")

    stats = compute_running_stats(games, start_dates=start_dates)
    insert_sql = """
        INSERT INTO core.fact_game_team VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    batch: list[list[Any]] = []
    for (game_id, team), measures in stats.items():
        ids = side_ids.get((game_id, team))
        if ids is None:
            continue
        team_id, home_away = ids
        batch.append(
            [
                game_id,
                team_id,
                home_away,
                int(measures["games_played"]),
                measures["win_pct"],
                measures["ats_pct"],
                int(measures["streak"]),
                int(measures["ats_streak"]),
            ]
        )
        if len(batch) >= 2000:
            con.executemany(insert_sql, batch)
            batch.clear()
    if batch:
        con.executemany(insert_sql, batch)


def _build_fact_game_odds(con: duckdb.DuckDBPyConnection) -> bool:
    """the-odds-api ticks, resolved onto ``game_id``. Returns False if nothing is loaded.

    The resolution lives here rather than in the flatten because ``refresh_cfbd.py`` runs
    every flatten *before* the rebuild -- a flatten that joined games would read the
    previous run's ``stg.games``, and this week's kickoffs are exactly what goes stale.

    Names are **not** re-resolved here. ``oddsapi_flatten.py`` already wrote the CFBD school
    string it matched into ``home_school``/``away_school``, so this joins on exact equality.
    Re-implementing the mascot strip and the alias list in SQL would be a second copy of a
    rule that lives in ``cfb_system_maker/oddsapi_schema.py``, and the two would drift -- the
    SQL version would not know about the three aliases at all.

    **Pair first, kickoff only to split.** Measured 2026-09-10 over the snapshots on disk
    (docs/oddsapi-game-join-2026-09-10.md): the unordered team pair identifies the game for
    98 of 98 events, none ambiguously, while ``commence_time`` disagrees with ``startDate``
    by a full day on one -- the vendors hold different dates for it. A join keyed on kickoff
    within any sub-24h tolerance would drop real games. The pair is not unique in 0.65% of
    FBS pair-seasons since 2015, all conference-title or playoff rematches weeks apart, and
    there the nearest kickoff picks correctly.

    A name the flatten could not resolve leaves ``game_id`` NULL rather than guessing.
    """
    tables = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'stg'"
    ).fetchall()}
    if "oa_odds_tick" not in tables:
        return False

    con.execute("DROP TABLE IF EXISTS core.fact_game_odds")
    con.execute(
        """
        CREATE TABLE core.fact_game_odds AS
        WITH resolved AS (
          SELECT t.*, h.team_id AS home_team_id, a.team_id AS away_team_id
          FROM stg.oa_odds_tick t
          LEFT JOIN core.dim_team h ON h.school = t.home_school
          LEFT JOIN core.dim_team a ON a.school = t.away_school
        ),
        paired AS (
          SELECT r.*, g."gameId" AS game_id, g."startDate" AS start_date,
                 row_number() OVER (
                   PARTITION BY r.pulled_at, r.event_id, r.book, r.market, r.side
                   ORDER BY abs(epoch(r.commence_time) - epoch(g."startDate"))
                 ) AS rn
          FROM resolved r
          LEFT JOIN stg.games g
            ON least(g."homeTeamId", g."awayTeamId")
                 = least(r.home_team_id, r.away_team_id)
           AND greatest(g."homeTeamId", g."awayTeamId")
                 = greatest(r.home_team_id, r.away_team_id)
           AND g.season = CAST(strftime(r.commence_time, '%Y') AS INTEGER)
        )
        SELECT game_id, event_id, pulled_at, commence_time, start_date,
               home_team_id, away_team_id, home_team, away_team, home_school, away_school,
               book, book_title, last_update, market, side, outcome_name, line, odds
        FROM paired WHERE rn = 1
        """
    )
    return True


def _add_phase_1_indexes(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_fact_game_slate
        ON core.fact_game (season, season_type, week, has_line)
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_fact_game_home_team_id ON core.fact_game (home_team_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_fact_game_away_team_id ON core.fact_game (away_team_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_dim_team_school ON core.dim_team (school)"
    )
    con.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_fact_game_team_team_id
        ON core.fact_game_team (team_id)
        """
    )
