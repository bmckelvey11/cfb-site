# Expanding `core`: lookup dims, team-season and game-grain facts — 2026-09-18

**Question.** `core` held 18 objects: a game grain, a game-line grain, and six dims. Two of
its own columns — `dim_draft_pick.position_id` and `.nfl_team_id` — pointed at nothing.
Information a betting model wants — SP+, SRS, Elo, FPI, records, recruiting, returning
production, ATS, plus weather, polls and drives — sat in `stg` across a dozen tables with
three different team keys. Which of those can be promoted into `core` with a real key, and
what does that cost?

**Method.** Read-only probe of every candidate for grain, season coverage, key uniqueness and
orphans against `core.dim_team`, on `data/cfb.duckdb` (built 2026-09-18). Built against a
byte-identical copy and verified there before touching the live file. Builders are in
[`cfb_system_maker/duckdb_core.py`](../cfb_system_maker/duckdb_core.py); notes and join edges
in [`warehouse_dictionary.py`](../cfb_system_maker/warehouse_dictionary.py).

Supersedes nothing. Builds on
[warehouse-discovery-layer-2026-09-18.md](warehouse-discovery-layer-2026-09-18.md).

## What was added — 18 objects, `core` 18 → 36

**Nine lookup dims**, promoted verbatim from vendor code tables, each with a verified PK:
`dim_position` (28), `dim_recruit_position` (28), `dim_draft_position` (31), `dim_draft_team`
(32), `dim_play_type` (49), `dim_play_stat_type` (26), `dim_poll_type` (8),
`dim_weather_condition` (27), `dim_stat_category` (38).

**`dim_athlete`** (158,932, PK `athlete_id`).

**Five team-season facts**, all PK `(season, team_id)`:

| Table | Rows | Span | Pre-game safe? |
|---|---:|---|---|
| `fact_team_season_rating_postgame` | 15,383 | 1890–2026 | no |
| `fact_team_season_record_postgame` | 6,454 | 2012–2026 | no |
| `fact_team_ats_postgame` | 1,750 | 2019–2026 | no |
| `fact_team_recruiting` | 3,160 | 2012–2026 | yes |
| `fact_team_returning_production` | 1,691 | 2014–2026 | yes |

## Game-grain facts

| Table | Rows | Span | Grain |
|---|---:|---|---|
| `fact_game_weather` | 28,402 | 2001–2026 | one row per game |
| `fact_poll_rank` | 49,507 | 1936–2026 | season × week × season_type × poll × team |
| `fact_drive_postgame` | 371,564 | 2012–2026 | one row per drive |

**`fact_game_weather` merges two feeds, because neither is a superset.** GraphQL
`game_weather` covers 6,413 games REST lacks; REST `weather` covers 545 GraphQL lacks;
21,444 overlap. Same shape as `_merge_game_lines`: FULL OUTER on the game id, REST wins a
conflict, `_source` marks `gql` / `rest` / `both`. `game_indoors` and `weather_condition`
are REST-only and are NULL on the 6,413 GraphQL-only rows.

It is **not** suffixed `_postgame` — weather is a condition, not an outcome. Two edges from
it are lossy, both for stated reasons rather than defects:

- 6,413 rows have no `fact_game` parent. They are **2001–2011** games, below `core`'s 2012
  floor; their parent is `fact_game_historical`.
- 7,347 rows carry `weather_condition_code = 0`, which has **no row** in the vendor's
  condition table (`dim_weather_condition` starts at 1 and runs to 27). The obvious guess is
  an off-by-one, and it is left unmapped rather than guessed at.

**`fact_poll_rank` uses `SELECT DISTINCT`, not a ROW_NUMBER pick.** The 150 duplicate keys
are all 2022, weeks 6 and 8, in the D2/D3/FCS polls — and the duplicate rows are
byte-identical (same rank, points, first-place votes, conference) from the same dump file.
The vendor emitted each record twice. There is nothing to choose between, so collapsing them
loses no information; a ROW_NUMBER would have implied there was a choice. 283 ballots with no
team name (all 1943–44 AP, wartime) and 291 whose school is outside `dim_team` cannot be
keyed and are excluded.

It is **not** suffixed: a week's poll is published before that week's games. But the vendor's
`week`-label convention is *not* verified here — confirm it before using a poll as a pre-game
feature.

**It is also stale, and that is not a defect of this change.** `stg.poll_rank` comes from the
hand-pulled GraphQL `pollRank` dump, which is not on the daily refresh path. As of 2026-09-18
it carries only **2026 week 1** (75 ballots), so the current season is effectively empty —
a query for a recent AP top 25 returns nothing. Re-pull the dump before using this in-season;
`scripts/audit_graphql_dump_age.py` measures which dumps have aged.

**`fact_drive_postgame`** is result-informed throughout (drive result, yards, plays, scores),
so it takes the suffix. `offense_team_id` / `defense_team_id` are LEFT JOINed from school
names, leaving 727 drives with a NULL id rather than dropping them; the names are kept
alongside. Indexed on `game_id`, as `fact_poll_rank` is on `(team_id, season)` — these are
the only `core` tables large enough for a scan to be felt.


## The ratings merge

Six rating systems — SP+, SRS, Elo, FPI, the GraphQL `ratings` table, and CFBD's own
`core_ratings` — collapse into one 67-column row per team-season, each source's columns
prefixed (`sp_`, `srs_`, `elo_`, `fpi_`, `cr_`, `gql_`). The prefixes are load-bearing: `elo`
exists in both the REST dump and the GraphQL one, and they are not the same number
(`elo_elo` vs `gql_elo`).

**It is built on a union spine, not off a single anchor.** The GraphQL `ratings` table is the
widest source by far (1890 onward, 14,730 rows) and is the obvious thing to anchor on — but
it stops at **2025**, while `sp`, `fpi` and `core_ratings` carry **2026**. Anchoring on it
would have silently dropped the season currently being bet. Coverage by season:

| Season | Teams | `sp_` | `fpi_` | `cr_` | `gql_` | `srs_` | `elo_` |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024 | 262 | 134 | 134 | 134 | 134 | 262 | 134 |
| 2025 | 264 | 136 | 136 | 136 | 136 | 264 | 136 |
| 2026 | 138 | 138 | 138 | 138 | **0** | **0** | **0** |

Columns are read from the catalog at build time rather than spelled out, so a vendor adding a
field lands in `core` on the next rebuild instead of being dropped without notice.

## The `_postgame` suffix, and why not `_final`

The user's no-lookahead rule requires result-informed values to be distinguishable. The
convention adopted: **suffix a table only when *every* column is result-informed.** `fact_game`
is mixed — schedule, venue and teams are knowable before kickoff, points are not — and
correctly carries no suffix, matching what it already did.

`_final` was rejected after measurement. `core_ratings` carries `throughWeek` precisely
because it is an as-of snapshot, and the 2026 rows are `throughWeek = 2` — the season is in
progress and those ratings move on every refresh. `records` and `teams_ats` are likewise
partial for the current season. Calling any of them "final" would be false, so
`cr_through_week` is carried as a column and the suffix says only what is true: these are
computed from games already played.

Pinned by `tests/test_warehouse_dictionary.py::test_postgame_suffix_is_reserved_for_wholly_result_informed_tables`.

## What was measured

**The two dangling keys now resolve, at zero orphans.** `dim_draft_pick.position_id →
dim_draft_position` and `.nfl_team_id → dim_draft_team` were columns pointing at nothing until
the lookup dims existed. Both are now edges in `meta.relationship`, as is
`dim_athlete.position_id → dim_position` (0 orphans, 18,733 NULL keys).

**Name-keyed sources are safe to resolve through `dim_team.school`**: no school name maps to
two `team_id`s. A pre-2012 row therefore resolves on the team's *current* name, per the Type-1
rule in [duckdb-core-ddl.md](duckdb-core-ddl.md).

**Rows excluded by that join, and why each is correct:**

- All 15 `stg.sp` non-matches are the string `nationalAverages` — a sentinel row, not a team.
  Excluding it is right; it stays readable in `stg.sp`.
- 23 `stg.recruiting_teams` non-matches are 7 non-FBS schools (Grand Valley State, Savannah
  St, St. Francis (PA), Southeastern Louisiana, UTRGV, Albany). They are outside `dim_team`
  and so have no `team_id` to key on.
- `stg.srs` contributes 2 duplicate `(season, team)` rows and `srs_expanded` 12; the merge
  takes one deterministically rather than letting the PK fail.

## What this does *not* support

- **No `dim_hometown`.** `stg.athlete` carries `hometownId` on 138,150 rows, but the GraphQL
  `hometown` dump ships **no id field at all** — confirmed against `raw.gql_hometown`'s payload
  structure, not just the exploded table. The key is carried on `dim_athlete` and dangles.
  It becomes joinable the moment the vendor ships an id; nothing here works around it.
- **`ppa_teams` and `adjusted_team_season` are not in the merge.** They are two more
  team-season rating sources (PPA splits; EPA and rushing line-yards) and were left out to
  keep this change to the six systems scoped. Adding them is a mechanical extension of
  `_RATING_SOURCES`.
- **No box-score facts.** `advanced_game_stats` (63 columns of postgame team box score),
  `player_season_stats` (1.4M) and `plays` (2.7M) remain in `stg` only.
- **`fact_poll_rank`'s week convention is unverified.** See above; it is the one claim in
  this change that rests on how the vendor labels a week rather than on a measurement.
- **`fact_team_season_rating_postgame` is not a pre-game feature source.** Every column in it
  is computed from games already played. Using a season's rating to predict that season's
  games is leakage. The pre-game-safe team-season tables are `fact_team_recruiting` and
  `fact_team_returning_production`.
- **Coverage is uneven by design.** SRS covers all divisions (~260 teams/season); SP+, FPI and
  the PPA-style ratings cover FBS only (~135). A row's NULLs are the vendor's coverage, not a
  load failure — check `meta.load_report` before assuming otherwise.
- **Nothing consumes these yet.** Like `fact_game_line` and `fact_game_team`, they are built
  and indexed but have no reader as of 2026-09-18.
