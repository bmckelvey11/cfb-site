# DuckDB `core` DDL contract (Phase 1)

Physical contract for the Phase 1 warehouse tables described in
[`duckdb-warehouse-plan.md`](duckdb-warehouse-plan.md). Grains, sequencing, and
dual-SoT policy live in that plan. **This file is columns, keys, CHECKs, and
indexes only.**

**Status (2026-08-28):** Phase 1a–1c implemented in `cfb_system_maker/duckdb_core.py`
(`build_core` / CLI `--core-only`). Agreement gates in `tests/test_core_agreement.py`.

Load pattern: full rebuild → CTAS or `CREATE TABLE` + `INSERT` →
`ALTER TABLE … ADD PRIMARY KEY` (and uniques) if CTAS was used. DuckDB FKs are soft;
agreement tests are the gate.

## Locked defaults (2026-08-28)

| Decision | Choice |
|---|---|
| `fact_game` population | All REST `games` rows + `has_line` / `completed` flags. `upcoming` stays a separate stream. |
| Close-book rule | Clone `normalize._select_line` / `_select_total` (split-book totals allowed). |
| Selected providers on `fact_game` | **Two** keys: `selected_spread_provider_key`, `selected_total_provider_key` (may differ). |
| `provider_key` | Canonical **lowercase** string (`lower(trim(provider))`). |
| `dim_week` vs fact | Week attrs **degenerate on the fact** always; `dim_week` is a filter spine. **No hard FK** from `fact_game` → `dim_week` (calendar gaps must not block load). |
| Types for lines | `DOUBLE` (match Python `float` / `GameRecord`). |
| Spread sign | Home-relative (same as `GameRecord.spread`). |
| `season_type` CHECK | Include CFBD spring slate: `regular`, `postseason`, `spring_regular`, `spring_postseason`. |

## Provider canonicalization

```sql
-- At load time, not as a view-only convention:
lower(trim(cast(provider AS VARCHAR)))
```

Agreement tests compare against `GameRecord.provider` using the same lower/trim
rule (CSV may retain display casing; SQL keys are lower).

## DDL (Phase 1a–1c)

```sql
CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE core.dim_week (
    season       INTEGER NOT NULL,
    week         INTEGER NOT NULL,
    season_type  VARCHAR NOT NULL,
    start_date   TIMESTAMPTZ,
    end_date     TIMESTAMPTZ,
    PRIMARY KEY (season, week, season_type),
    CHECK (season_type IN ('regular', 'postseason', 'spring_regular', 'spring_postseason'))
);

CREATE TABLE core.dim_conference (
    conference_id   INTEGER PRIMARY KEY,
    name            VARCHAR NOT NULL,
    abbreviation    VARCHAR,
    short_name      VARCHAR,
    classification  VARCHAR
);

-- Type-1 identity. Conference-as-of-game lives on fact_game, not here.
-- school is indexed for name→id crosswalk; NOT UNIQUE (renames / collisions).
CREATE TABLE core.dim_team (
    team_id         INTEGER PRIMARY KEY,
    school          VARCHAR NOT NULL,
    abbreviation    VARCHAR,
    classification  VARCHAR,
    is_fbs          BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE core.dim_venue (
    venue_id   INTEGER PRIMARY KEY,
    name       VARCHAR,
    city       VARCHAR,
    state      VARCHAR,
    dome       BOOLEAN,
    grass      BOOLEAN,
    capacity   INTEGER,
    elevation  DOUBLE   -- cast from REST string at load
);

CREATE TABLE core.dim_lines_provider (
    provider_key  VARCHAR PRIMARY KEY   -- lowercase canonical
);

CREATE TABLE core.fact_game (
    game_id                         INTEGER PRIMARY KEY,
    season                          INTEGER NOT NULL,
    week                            INTEGER NOT NULL,
    season_type                     VARCHAR NOT NULL,
    start_date                      TIMESTAMPTZ,
    completed                       BOOLEAN,
    has_line                        BOOLEAN NOT NULL,
    venue_id                        INTEGER,  -- soft → dim_venue
    home_team_id                    INTEGER NOT NULL,  -- soft → dim_team
    away_team_id                    INTEGER NOT NULL,
    home_conference_id              INTEGER,  -- as-of kickoff; soft → dim_conference
    away_conference_id              INTEGER,
    -- Degenerate names for CSV agreement (GameRecord is name-keyed today)
    home_team                       VARCHAR NOT NULL,
    away_team                       VARCHAR NOT NULL,
    home_conference                 VARCHAR,
    away_conference                 VARCHAR,
    home_points                     INTEGER,
    away_points                     INTEGER,
    -- Degenerate selected book(s); null when has_line = false
    selected_spread_provider_key    VARCHAR,  -- soft → dim_lines_provider
    selected_total_provider_key     VARCHAR,
    selected_spread                 DOUBLE,   -- home-relative close
    selected_total                  DOUBLE,
    CHECK (season_type IN ('regular', 'postseason', 'spring_regular', 'spring_postseason')),
    CHECK (home_team_id <> away_team_id),
    CHECK (
        NOT has_line
        OR selected_spread IS NOT NULL
        OR selected_total IS NOT NULL
    )
);

CREATE TABLE core.fact_game_line (
    game_id            INTEGER NOT NULL,  -- soft → fact_game
    provider_key       VARCHAR NOT NULL,  -- lowercase; soft → dim_lines_provider
    spread_close       DOUBLE,            -- home-relative
    spread_open        DOUBLE,            -- null = fail-closed (never 0 default)
    total_close        DOUBLE,
    total_open         DOUBLE,
    moneyline_home     INTEGER,
    moneyline_away     INTEGER,
    formatted_spread   VARCHAR,
    PRIMARY KEY (game_id, provider_key)
);

-- Entering-game measures. Grain matches running_stats.py: (game_id, team).
CREATE TABLE core.fact_game_team (
    game_id         INTEGER NOT NULL,
    team_id         INTEGER NOT NULL,
    home_away       VARCHAR NOT NULL,
    games_played    INTEGER NOT NULL,
    win_pct         DOUBLE,   -- null when no decided prior games
    ats_pct         DOUBLE,
    streak          INTEGER,
    ats_streak      INTEGER,
    PRIMARY KEY (game_id, team_id),
    UNIQUE (game_id, home_away),
    CHECK (home_away IN ('home', 'away')),
    CHECK (games_played >= 0)
);
```

### Type-1 `dim_team` collapse rule

REST `teams` is season-stacked (many rows per `id`). Load:

```sql
-- Pseudocode: one row per team_id from the latest season file present
QUALIFY row_number() OVER (
    PARTITION BY team_id ORDER BY season DESC NULLS LAST
) = 1
```

Set `is_fbs` from membership in the latest `fbs_teams` set for that season (or any
season if only one dump exists). Do not union `historicalTeam` into this table.

## Indexes (after PKs exist)

```sql
CREATE INDEX idx_fact_game_slate
    ON core.fact_game (season, season_type, week, has_line);

CREATE INDEX idx_fact_game_home_team_id ON core.fact_game (home_team_id);
CREATE INDEX idx_fact_game_away_team_id ON core.fact_game (away_team_id);

CREATE INDEX idx_dim_team_school ON core.dim_team (school);

CREATE INDEX idx_fact_game_team_team_id ON core.fact_game_team (team_id);
```

Do **not** add indexes that duplicate primary keys (`game_id`,
`(game_id, provider_key)`, `(game_id, team_id)`).

## Result-informed tables: the `_postgame` suffix

Suffix a `core` table `_postgame` when **every** column in it is result-informed. A mixed
table does not get the suffix: `fact_game` carries schedule, venue and teams (pre-game)
alongside points (not), and correctly has no suffix. Today the suffix is on
`fact_team_season_rating_postgame`, `fact_team_season_record_postgame`,
`fact_team_ats_postgame` and `fact_drive_postgame`.

`fact_game_weather` is the case that tempts the suffix and does not take it: weather is a
condition, not an outcome.

`_final` is deliberately **not** used. `core_ratings` carries `throughWeek` because it is an
as-of snapshot; the current season's rows are partial and move on every refresh. Carry the
as-of column (`cr_through_week`) and let the suffix claim only what is true.

Pinned by `tests/test_warehouse_dictionary.py`.

## Team-season grain

`(season, team_id)`, PK on all five: `fact_team_season_rating_postgame`,
`fact_team_season_record_postgame`, `fact_team_ats_postgame`, `fact_team_recruiting`,
`fact_team_returning_production`.

`fact_team_season_rating_postgame` merges eight rating systems side by side with per-source
prefixes (`sp_`, `srs_`, `elo_`, `fpi_`, `cr_`, `gql_`, `ppa_`, `adj_`) — `elo` exists in both
the REST and GraphQL sources and they are different numbers. Built on a **union spine**, not anchored on
one source: GraphQL `ratings` is the widest (1890+) but stops at 2025, while `sp`, `fpi` and
`core_ratings` carry 2026. Extend it by appending to `_RATING_SOURCES`.

Sources keyed by school name resolve through `dim_team.school`, which is safe only because no
school name maps to two `team_id`s. See
[core-expansion-2026-09-18.md](core-expansion-2026-09-18.md).

## Views

```sql
CREATE OR REPLACE VIEW core.v_game AS ...  -- see duckdb_core._build_core_views
```

`fact_game` with `dim_venue`, `dim_week` and the selected lines already joined. It joins
`fact_game_line` **twice**, on `selected_spread_provider_key` and
`selected_total_provider_key` separately: those differ on 2,943 games, so a single join
returns one market from the wrong book. It carries no derived result column
(`home_margin`, `total_points`) on purpose — see the no-lookahead rule.

## Referential integrity: `meta.relationship`, not `FOREIGN KEY`

DuckDB has no `ALTER TABLE ... ADD FOREIGN KEY`, and this DDL creates every table with
`CREATE TABLE AS`, so a declared FK would mean rewriting each table with an explicit column
list. It would also be *wrong*: `fact_game.home_team_id` has 91 orphans and
`away_team_id` 401, because `dim_team` deliberately omits opponents outside CFBD's team
table, and 154 postseason games do not join `dim_week`. A constraint that fails the 05:00
rebuild is worse than no constraint.

Instead `meta.relationship` records each known edge with its orphan and NULL-key counts
**measured on every build**, so `is_lossy` cannot go stale. Add an edge by appending to
`_EDGES` in `cfb_system_maker/warehouse_dictionary.py`; the counts take care of themselves.
Rationale and the full measurement:
[warehouse-discovery-layer-2026-09-18.md](warehouse-discovery-layer-2026-09-18.md).

## Out of scope here

- `ref` name-alias table
- ActionNetwork timestamped history fact
- `fact_team_week` / mart feature tables
- MotherDuck promote SQL
