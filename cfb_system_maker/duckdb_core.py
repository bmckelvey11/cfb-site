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
    PROVIDER_ALIASES,
    provider_key,
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
        if _merge_game_lines(con):
            built.append("fact_game_line_conflicts")
        _build_dim_lines_provider(con)
        built.append("dim_lines_provider")
        _build_fact_game_team(con)
        built.append("fact_game_team")
        if _build_fact_game_odds(con):
            built.append("fact_game_odds")
        # Bucket C/B merges (rationalization plan step 3). Each is guarded and skipped when
        # its sources are absent, so a partial warehouse still rebuilds.
        if _build_dim_coach(con):
            built += ["dim_coach", "coach_name_conflicts"]
        if _build_dim_draft_pick(con):
            built.append("dim_draft_pick")
        if _build_dim_recruit(con):
            built.append("dim_recruit")
        if _build_fact_team_talent(con):
            built.append("fact_team_talent")
        if _build_fact_coach_season(con):
            built += ["fact_coach_season", "coach_season_unmatched"]
        if _build_fact_game_historical(con):
            built.append("fact_game_historical")
        _add_phase_1_indexes(con)
        con.execute("CHECKPOINT")
        return built
    finally:
        con.close()


def _build_dim_week(con: duckdb.DuckDBPyConnection) -> None:
    """Week spine, sourced from ``raw.calendar``'s JSON payload.

    Not ``stg.calendar``: the REST calendar is never exploded into ``stg``, and
    the only staged calendar (``stg.calendar_gql``) keeps its season in ``year``
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
    # GraphQL's only column REST lacks that is worth carrying. It is also what
    # disambiguates the duplicate names -- four rows are named 'Big Sky', four
    # 'Southland' -- which is why _build_fact_game below cannot resolve a conference
    # by name. `srName` fills 1 of 256 rows and is deliberately not carried.
    # Measured 2026-09-10: 256 of 256 ids match and no name disagrees, so this is a
    # column-only join; the row count is unchanged either way (ADR-0001).
    if _has(con, "stg", "conference"):
        con.execute("ALTER TABLE core.dim_conference ADD COLUMN division VARCHAR")
        con.execute(
            """
            UPDATE core.dim_conference c
            SET division = g.division
            FROM stg.conference g
            WHERE g."conferenceId" = c.conference_id
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


def _populated(row: list[Any]) -> int:
    """How many line values a row carries, ignoring the two key columns."""
    return sum(1 for value in row[2:] if value is not None)


def _provider_key(value: Any) -> str | None:
    """Delegates to `normalize.provider_key`, which owns the alias map.

    Two definitions of "what is this book called" is how `core.fact_game_line` and
    `games.csv` end up disagreeing about whether a game has a DraftKings row.
    """
    return provider_key(value)


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

    # `conf_by_name` above resolves a conference *name*, and dim_conference names are
    # not unique, so the dict build picks arbitrarily among the same-named rows.
    # GraphQL carries the FK outright. Measured 2026-09-10: 3,714 home and 3,985 away
    # ids disagreed with it while resolving to the *same conference name* -- the map was
    # non-injective, not wrong about the conference. coalesce keeps what we already had
    # for the 4 games GraphQL has no row for.
    #
    # This *changes existing column values*, which ADR-0001 does not cover -- it governs
    # rows vs columns. See docs/core-merge-bucket-c-2026-09-10.md.
    if _has(con, "stg", "game"):
        con.execute(
            """
            UPDATE core.fact_game f
            SET home_conference_id = coalesce(g."homeConferenceId", f.home_conference_id),
                away_conference_id = coalesce(g."awayConferenceId", f.away_conference_id)
            FROM stg.game g
            WHERE g."gameId" = f.game_id
            """
        )
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
          formatted_spread VARCHAR,
          -- Every row here is REST until `_merge_game_lines` runs and rewrites the table.
          -- Declared unconditionally so the column does not depend on whether an optional
          -- source was present: a table with two possible shapes is a trap for any
          -- consumer that selects `_source` and only sometimes finds it.
          _source VARCHAR NOT NULL DEFAULT 'rest'
        )
        """
    )

    insert_sql = """
        INSERT INTO core.fact_game_line (
          game_id, provider_key, spread_close, spread_open, total_close, total_open,
          moneyline_home, moneyline_away, formatted_spread
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    rows: dict[tuple[int, str], list[Any]] = {}
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
            formatted = _first(line, "formattedSpread", "formatted_spread")
            row = [
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
            # Was "keep the first occurrence", which is array order and so arbitrary.
            # Since `Draft Kings` aliases onto `draftkings`, 215 games now present the
            # same key twice, and the two differ on 31 spreads and 21 totals -- the same
            # book captured at two moments inside one payload. The more populated row
            # wins: it is the one carrying the opens and moneylines, and on a tie this is
            # still first-wins. Held in a dict rather than appended, because replacing a
            # row already in a list means finding it first.
            prior = rows.get(pk)
            if prior is None or _populated(row) > _populated(prior):
                rows[pk] = row

    batch = list(rows.values())
    for start in range(0, len(batch), 2000):
        con.executemany(insert_sql, batch[start:start + 2000])

    con.execute(
        "ALTER TABLE core.fact_game_line ADD PRIMARY KEY (game_id, provider_key)"
    )


def _merge_game_lines(con: duckdb.DuckDBPyConnection) -> bool:
    """Union ``stg.game_lines`` (``period='game'``) into ``core.fact_game_line``.

    ``game_lines`` is **not** a GraphQL scrape. Its ``line_source`` reads cfbd 37,048 /
    actionnetwork 8,656 / cfbd+an 1,599 -- it is already a merged tape, and the
    ActionNetwork half is where five books live that the REST unnest above has never
    seen: circa, fanduel, betmgm, bet365, pinnacle.

    **Full outer on ``(game_id, provider_key)``, ``coalesce(rest, gql)`` on every value.**
    A straight repoint was measured and rejected: it drops 278 REST offers ``game_lines``
    has no row for (all 2026, on 'draft kings' / 'bovada' / 'draftkings') and overwrites
    ~700 values where both sides are populated and differ. Preferring the REST side on a
    conflict means **no value already in ``core`` changes** -- the table today *is* the
    CFBD values -- so this is purely additive: +8,575 rows, +5 providers, and 3,424
    ``total_close`` NULLs filled. ``game_lines`` spells a missing number NaN rather than
    NULL, which coalesce would happily carry, so those are nulled out first.
    The conflicts are preserved in
    ``core.fact_game_line_conflicts`` rather than discarded, so the rule is inspectable
    and reversible.

    ``has_line`` on ``core.fact_game`` stays REST-defined. It is computed by
    ``_select_line`` over ``stg.lines`` and drives ``selected_spread``/``selected_total``,
    which the spread model reads; redefining it here would move the model's inputs. The
    consequence is named rather than hidden: after this merge 90 line rows on 16 games sit
    under ``has_line = false``, so that flag means "no REST line the selector accepted",
    not "no line row exists".

    Measured 2026-09-10, `python scripts/audit_core_merges.py --merge lines`. See
    docs/core-merge-bucket-c-2026-09-10.md.
    """
    if not (_has(con, "stg", "game_lines") and _has(con, "stg", "lines_provider")):
        return False
    # Same bound the REST unnest applies: a line row for a game the spine excluded is an
    # orphan. Measured at 0 today; restated so it stays 0 when game_lines moves.
    # `game_lines` spells a missing number **NaN, not NULL** -- 3,414 `overUnder` and 65
    # `spread` rows. coalesce treats NaN as a value, so without this the merge fills REST
    # NULLs with NaN and every downstream comparison silently becomes false. Nulled out
    # in an outer layer so each cast is written once.
    # Built from the same dict, so the two sides cannot drift apart.
    aliases = "CASE lower(p.name) " + " ".join(
        f"WHEN '{src}' THEN '{dst}'" for src, dst in PROVIDER_ALIASES.items()
    ) + " END"
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW _gql_game_line AS
        SELECT
          game_id, provider_key, line_source,
          spread_close, spread_open, total_close, total_open,
          moneyline_home, moneyline_away
        FROM (
          SELECT
            game_id, provider_key, line_source, provider_id,
            CASE WHEN isnan(spread_close) THEN NULL ELSE spread_close END AS spread_close,
            CASE WHEN isnan(spread_open)  THEN NULL ELSE spread_open  END AS spread_open,
            CASE WHEN isnan(total_close)  THEN NULL ELSE total_close  END AS total_close,
            CASE WHEN isnan(total_open)   THEN NULL ELSE total_open   END AS total_open,
            moneyline_home, moneyline_away
          FROM (
          SELECT
            CAST(l."gameId" AS INTEGER) AS game_id,
            -- Same alias `_provider_key` applies to the REST side. Without it the AN tape
            -- re-splits the key this merge just collapsed, and `stg.lines_provider` holds
            -- both spellings under separate ids (100 and a synthetic 888888).
            coalesce({aliases}, lower(p.name)) AS provider_key,
            TRY_CAST(l.spread AS DOUBLE)          AS spread_close,
            TRY_CAST(l."spreadOpen" AS DOUBLE)    AS spread_open,
            TRY_CAST(l."overUnder" AS DOUBLE)     AS total_close,
            TRY_CAST(l."overUnderOpen" AS DOUBLE) AS total_open,
            TRY_CAST(l."moneylineHome" AS INTEGER) AS moneyline_home,
            TRY_CAST(l."moneylineAway" AS INTEGER) AS moneyline_away,
            l.line_source,
            l."linesProviderId" AS provider_id
          FROM stg.game_lines l
          JOIN stg.lines_provider p USING ("linesProviderId")
          WHERE l.period = 'game'
            AND l."gameId" IN (SELECT game_id FROM core.fact_game)
            AND p.name IS NOT NULL
          )
        )
        -- `game_lines` is unique on (gameId, linesProviderId), but the alias above maps
        -- two provider ids onto one key -- `stg.lines_provider` carries DraftKings under
        -- both CFBD's 100 and the synthetic 888888 that `_AN_BOOK_PROVIDER` assigned the
        -- ActionNetwork feed. So the grain has to be re-established here or the full outer
        -- join below fans out. Same rule as the REST unnest: the more populated row wins,
        -- tie broken on the lower provider id so a rebuild is reproducible.
        QUALIFY row_number() OVER (
          PARTITION BY game_id, provider_key
          ORDER BY (CASE WHEN spread_close IS NOT NULL THEN 1 ELSE 0 END
                  + CASE WHEN spread_open  IS NOT NULL THEN 1 ELSE 0 END
                  + CASE WHEN total_close  IS NOT NULL THEN 1 ELSE 0 END
                  + CASE WHEN total_open   IS NOT NULL THEN 1 ELSE 0 END
                  + CASE WHEN moneyline_home IS NOT NULL THEN 1 ELSE 0 END
                  + CASE WHEN moneyline_away IS NOT NULL THEN 1 ELSE 0 END) DESC,
                   provider_id
        ) = 1
        """
    )

    con.execute("DROP TABLE IF EXISTS core.fact_game_line_conflicts")
    con.execute(
        """
        CREATE TABLE core.fact_game_line_conflicts AS
        SELECT game_id, provider_key, line_source, column_name, rest_value, gql_value
        FROM (
          SELECT r.game_id, r.provider_key, g.line_source, u.column_name,
                 u.rest_value, u.gql_value
          FROM core.fact_game_line r
          JOIN _gql_game_line g USING (game_id, provider_key),
          UNNEST([
            {'column_name': 'spread_close',
             'rest_value': r.spread_close,   'gql_value': g.spread_close},
            {'column_name': 'total_close',
             'rest_value': r.total_close,    'gql_value': g.total_close},
            {'column_name': 'moneyline_home',
             'rest_value': CAST(r.moneyline_home AS DOUBLE),
             'gql_value':  CAST(g.moneyline_home AS DOUBLE)},
            {'column_name': 'moneyline_away',
             'rest_value': CAST(r.moneyline_away AS DOUBLE),
             'gql_value':  CAST(g.moneyline_away AS DOUBLE)}
          ]) AS t(u)
        )
        WHERE rest_value IS NOT NULL AND gql_value IS NOT NULL
          AND rest_value <> gql_value
        """
    )

    # Staged in TEMP, not under `core`: a build that dies between the DROP and the
    # rebuild would otherwise leave an orphan table in the live catalog.
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE _fact_game_line_merged AS
        SELECT
          coalesce(r.game_id, g.game_id)           AS game_id,
          coalesce(r.provider_key, g.provider_key) AS provider_key,
          coalesce(r.spread_close, g.spread_close)     AS spread_close,
          coalesce(r.spread_open, g.spread_open)       AS spread_open,
          coalesce(r.total_close, g.total_close)       AS total_close,
          coalesce(r.total_open, g.total_open)         AS total_open,
          coalesce(r.moneyline_home, g.moneyline_home) AS moneyline_home,
          coalesce(r.moneyline_away, g.moneyline_away) AS moneyline_away,
          r.formatted_spread,
          CASE WHEN r.game_id IS NOT NULL AND g.game_id IS NOT NULL THEN 'both'
               WHEN r.game_id IS NOT NULL THEN 'rest' ELSE 'gql' END AS _source
        FROM core.fact_game_line r
        FULL OUTER JOIN _gql_game_line g USING (game_id, provider_key)
        """
    )
    con.execute("DROP TABLE core.fact_game_line")
    con.execute(
        "CREATE TABLE core.fact_game_line AS SELECT * FROM _fact_game_line_merged")
    con.execute(
        "ALTER TABLE core.fact_game_line ADD PRIMARY KEY (game_id, provider_key)"
    )
    return True


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


# ------------------------------------------------------------------ Bucket C/B merges
#
# Section 3 of docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md: the two
# transports are complementary rather than duplicates, so these are **full outer joins on the
# key, one row per key**, with `_source` recording which side supplied it -- 'both', 'gql' or
# 'rest'. A left join anchored on REST would silently truncate: GraphQL out-rows REST on
# every pair (draft_picks 13,080 to 3,584, recruit 93,363 to 45,927).
#
# Deliberately not a UNION of both sides' rows. coach_season matches 1,961 of 1,961 REST
# rows, and a union would carry every one of those twice.
#
# Every builder returns False when a source is missing rather than raising: build_core runs
# on every refresh_cfbd pass, and a missing GraphQL-side table must not break the whole rebuild.


def _has(con: duckdb.DuckDBPyConnection, schema: str, table: str) -> bool:
    return bool(con.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_schema = ? AND table_name = ?", [schema, table]).fetchone()[0])


def _build_dim_coach(con: duckdb.DuckDBPyConnection) -> bool:
    """Coach identity, GraphQL only -- REST has no ``coachId`` (section 6).

    Also builds ``core.coach_name_conflicts``: names carried by more than one id. The third
    coach-season source resolves coaches *by name*, so a name in this table cannot be
    resolved that way and its seasons land in ``core.coach_season_unmatched`` instead.
    """
    if not _has(con, "stg", "coach"):
        return False
    con.execute("DROP TABLE IF EXISTS core.dim_coach")
    con.execute("""
        CREATE TABLE core.dim_coach AS
        SELECT "coachId" AS coach_id, "firstName" AS first_name, "lastName" AS last_name
        FROM stg.coach WHERE "coachId" IS NOT NULL
    """)
    con.execute("ALTER TABLE core.dim_coach ADD PRIMARY KEY (coach_id)")
    con.execute("DROP TABLE IF EXISTS core.coach_name_conflicts")
    con.execute("""
        CREATE TABLE core.coach_name_conflicts AS
        SELECT first_name, last_name, count(*) AS coach_count,
               list(coach_id ORDER BY coach_id) AS coach_ids
        FROM core.dim_coach GROUP BY 1, 2 HAVING count(*) > 1
    """)
    return True


def _build_dim_draft_pick(con: duckdb.DuckDBPyConnection) -> bool:
    """``(year, round, pick)`` -- unique on both sides, and REST is fully contained in GraphQL."""
    if not (_has(con, "stg", "draft_picks_gql") and _has(con, "stg", "draft_picks")):
        return False
    con.execute("DROP TABLE IF EXISTS core.dim_draft_pick")
    con.execute("""
        CREATE TABLE core.dim_draft_pick AS
        SELECT
          coalesce(g.year, r.year)   AS year,
          coalesce(g.round, r.round) AS round,
          coalesce(g.pick, r.pick)   AS pick,
          coalesce(g.name, r.name)   AS name,
          g.overall, g.grade, g."collegeTeamId" AS college_team_id,
          g."nflTeamId" AS nfl_team_id, g."positionId" AS position_id,
          r."collegeAthleteId" AS college_athlete_id, r."collegeTeam" AS college_team,
          r."collegeConference" AS college_conference,
          CASE WHEN g.year IS NOT NULL AND r.year IS NOT NULL THEN 'both'
               WHEN g.year IS NOT NULL THEN 'gql' ELSE 'rest' END AS _source
        FROM stg.draft_picks_gql g
        FULL OUTER JOIN stg.draft_picks r
          ON g.year = r.year AND g.round = r.round AND g.pick = r.pick
    """)
    return True


def _build_dim_recruit(con: duckdb.DuckDBPyConnection) -> bool:
    """``recruitId``. REST is fully contained; GraphQL adds 14 seasons (2000-2027 vs 2012-2025).

    ``overallRank``/``positionRank`` are 0.00 filled on the GraphQL side across all 93,363
    rows (section 5's drop list) and are deliberately not carried; REST's are.

    **The key is typed differently on the two sides** -- ``UBIGINT`` on GraphQL, ``VARCHAR``
    on REST -- so it is cast explicitly rather than left to coercion. All 45,927 REST values
    are numeric and non-NULL, and containment still holds under the cast (checked
    2026-09-10), but an implicit cast in a join is the kind of thing that works until one
    non-numeric id arrives and then fails, or silently matches nothing.
    """
    if not (_has(con, "stg", "recruit") and _has(con, "stg", "recruits")):
        return False
    con.execute("DROP TABLE IF EXISTS core.dim_recruit")
    con.execute("""
        CREATE TABLE core.dim_recruit AS
        WITH rest AS (
          SELECT * REPLACE (TRY_CAST("recruitId" AS UBIGINT) AS "recruitId") FROM stg.recruits
        )
        SELECT
          coalesce(g."recruitId", r."recruitId")     AS recruit_id,
          coalesce(g.year, r.year)                   AS year,
          coalesce(g.name, r.name)                   AS name,
          coalesce(g.stars, r.stars)                 AS stars,
          coalesce(g.rating, r.rating)               AS rating,
          coalesce(g."recruitType", r."recruitType") AS recruit_type,
          g.ranking AS gql_ranking,
          r."athleteId" AS athlete_id, r."committedTo" AS committed_to, r.school,
          r.city, r.country,
          CASE WHEN g."recruitId" IS NOT NULL AND r."recruitId" IS NOT NULL THEN 'both'
               WHEN g."recruitId" IS NOT NULL THEN 'gql' ELSE 'rest' END AS _source
        FROM stg.recruit g
        FULL OUTER JOIN rest r ON g."recruitId" = r."recruitId"
    """)
    con.execute("ALTER TABLE core.dim_recruit ADD PRIMARY KEY (recruit_id)")
    return True


def _build_fact_team_talent(con: duckdb.DuckDBPyConnection) -> bool:
    """``(season, school)``, not ``(teamId, season)``.

    Section 6 expected the relation-key repair to make this a join on ``(teamId, season)``.
    It half did: GraphQL now carries ``team_teamId``, but REST carries only a school *name*,
    so the key stays the name. 17 REST rows have no GraphQL twin -- Jacksonville and
    St. Francis (PA), absent from GraphQL's ``currentTeams`` source -- which is why REST is
    still not droppable. See docs/warehouse-containment-remeasure-2026-09-10.md.
    """
    if not (_has(con, "stg", "team_talent") and _has(con, "stg", "talent")):
        return False
    con.execute("DROP TABLE IF EXISTS core.fact_team_talent")
    con.execute("""
        CREATE TABLE core.fact_team_talent AS
        WITH rest AS (
          -- `stg.talent` is NOT unique on its own key: 2,278 rows over 2,275 distinct
          -- (season, team). The three repeats -- Sam Houston 2018, Bethune-Cookman 2023,
          -- Bryant 2023 -- are byte-identical including the talent value, so DISTINCT is
          -- lossless. Left in, the join fans them out and the table comes back three rows
          -- long, which is how this was caught.
          SELECT DISTINCT season, team, talent FROM stg.talent
        )
        SELECT
          coalesce(g.year, r.season)         AS season,
          coalesce(g."team_school", r.team)  AS school,
          g."team_teamId"     AS team_id,
          g."team_conference" AS conference,
          coalesce(g.talent, r.talent) AS talent,
          CASE WHEN g.year IS NOT NULL AND r.season IS NOT NULL THEN 'both'
               WHEN g.year IS NOT NULL THEN 'gql' ELSE 'rest' END AS _source
        FROM stg.team_talent g
        FULL OUTER JOIN rest r
          ON g.year = r.season AND g."team_school" = r.team
    """)
    return True


def _build_fact_coach_season(con: duckdb.DuckDBPyConnection) -> bool:
    """``(coach_id, team_id, season)`` -- a clean join since the relation-key repair.

    Measured 2026-09-10: the key is unique on both sides (12,564 and 1,961) and matches
    1,961 of 1,961 REST rows with none unmatched, so this is a join, not a union.

    ``core.coach_season_unmatched`` holds the rows of the *third* source,
    ``stg.coaches__seasons``, that cannot be resolved to that key. Its bridge is
    one-directional: it carries ``(name, seasons_school, seasons_year)``, and 118
    school-seasons have two or three coaches, so a school-season does not identify a coach.
    A row whose name resolves to more than one ``coach_id`` is preserved here rather than
    guessed into the fact.
    """
    if not (_has(con, "stg", "coach_season") and _has(con, "stg", "coach_seasons")):
        return False
    con.execute("DROP TABLE IF EXISTS core.fact_coach_season")
    con.execute("""
        CREATE TABLE core.fact_coach_season AS
        SELECT
          coalesce(g."coach_id", r."coach_id")   AS coach_id,
          coalesce(g."team_teamId", r."team_id") AS team_id,
          coalesce(g.year, r.season)             AS season,
          g."team_school"     AS school,
          g."coach_firstName" AS first_name,
          g."coach_lastName"  AS last_name,
          coalesce(g.games, r.games)   AS games,
          coalesce(g.wins, r.wins)     AS wins,
          coalesce(g.losses, r.losses) AS losses,
          coalesce(g.ties, r.ties)     AS ties,
          coalesce(g."preseasonRank", r."preseasonRank")   AS preseason_rank,
          coalesce(g."postseasonRank", r."postseasonRank") AS postseason_rank,
          r."spOverall" AS sp_overall, r.srs, r."winPercentage" AS win_percentage,
          CASE WHEN g.year IS NOT NULL AND r.season IS NOT NULL THEN 'both'
               WHEN g.year IS NOT NULL THEN 'gql' ELSE 'rest' END AS _source
        FROM stg.coach_season g
        FULL OUTER JOIN stg.coach_seasons r
          ON g."coach_id" = r."coach_id" AND g."team_teamId" = r."team_id"
         AND g.year = r.season
    """)

    if not (_has(con, "stg", "coaches__seasons") and _has(con, "core", "dim_team")):
        return True
    con.execute("DROP TABLE IF EXISTS core.coach_season_unmatched")
    con.execute("""
        CREATE TABLE core.coach_season_unmatched AS
        WITH named AS (
          SELECT s."firstName" AS first_name, s."lastName" AS last_name,
                 s."seasons_year" AS season, s."seasons_school" AS school,
                 (SELECT count(*) FROM core.dim_coach c
                   WHERE c.first_name = s."firstName" AND c.last_name = s."lastName")
                   AS coach_matches,
                 (SELECT min(c.coach_id) FROM core.dim_coach c
                   WHERE c.first_name = s."firstName" AND c.last_name = s."lastName")
                   AS coach_id,
                 (SELECT min(d.team_id) FROM core.dim_team d
                   WHERE d.school = s."seasons_school") AS team_id
          FROM stg."coaches__seasons" s
        )
        SELECT first_name, last_name, season, school, coach_id, team_id, coach_matches,
               CASE WHEN coach_matches = 0 THEN 'no coach of that name'
                    WHEN coach_matches > 1 THEN 'name maps to several coaches'
                    WHEN team_id IS NULL   THEN 'school has no dim_team row'
                    ELSE 'resolved but absent from the fact' END AS reason
        FROM named
        WHERE coach_matches <> 1 OR team_id IS NULL
           OR NOT EXISTS (
                SELECT 1 FROM core.fact_coach_season f
                WHERE f.coach_id = named.coach_id AND f.team_id = named.team_id
                  AND f.season = named.season)
    """)
    return True


def _build_fact_game_historical(con: duckdb.DuckDBPyConnection) -> bool:
    """GraphQL's games from *before* ``core``'s span, kept out of ``core.fact_game``.

    ADR-0001: ``fact_game`` gains columns, not rows. GraphQL reaches back to 1869 and
    ``core`` starts at ``min(core.dim_week.season)`` -- 2012, because that is where the
    REST calendar that feeds ``dim_week`` starts. Letting those 78,030 games into the
    fact would leave every one of them with no week to join to.

    **This table is not classification-accurate for its own era.** ``homeClassification``
    and the conference FKs are the values GraphQL reports today, and divisions,
    conferences and classifications were reorganized repeatedly across the span. Use it
    for identity and scores; do not use it to decide what division a 1930 team was in.
    """
    if not (_has(con, "stg", "game") and _has(con, "core", "dim_week")):
        return False
    con.execute("DROP TABLE IF EXISTS core.fact_game_historical")
    con.execute(
        """
        CREATE TABLE core.fact_game_historical AS
        SELECT
          "gameId" AS game_id, season, week, "seasonType" AS season_type,
          "startDate" AS start_date, status,
          "venueId" AS venue_id, "neutralSite" AS neutral_site,
          "conferenceGame" AS conference_game, attendance,
          "homeTeamId" AS home_team_id, "awayTeamId" AS away_team_id,
          "homeTeam" AS home_team, "awayTeam" AS away_team,
          "homeConferenceId" AS home_conference_id,
          "awayConferenceId" AS away_conference_id,
          "homeConference" AS home_conference, "awayConference" AS away_conference,
          "homeClassification" AS home_classification,
          "awayClassification" AS away_classification,
          "homePoints" AS home_points, "awayPoints" AS away_points
        FROM stg.game
        WHERE season < (SELECT min(season) FROM core.dim_week)
          AND "gameId" IS NOT NULL
        """
    )
    con.execute("ALTER TABLE core.fact_game_historical ADD PRIMARY KEY (game_id)")
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
