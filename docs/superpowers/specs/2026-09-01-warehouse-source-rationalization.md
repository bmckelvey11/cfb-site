# Warehouse Source Rationalization — Spec

**Status:** draft
**Date:** 2026-09-01
**Origin:** follow-up to the external schema audit finding #5, after measurement contradicted its premise
**Sibling:** `docs/superpowers/specs/2026-08-31-warehouse-naming-rationalization.md` (naming only; independent)

## Summary

`stg` holds 13 concept pairs, each one GraphQL table and one REST table. The working
hypothesis was that GraphQL is a superset and REST could be dropped from the scraper.
**Measurement refutes it for 10 of 13 pairs**, and for 3 pairs the REST side is the superset.

Underneath that sits a scraper defect: two GraphQL entities are pulled without the relation
that carries their identity, producing tables that cannot be joined to anything and whose
pagination is not provably stable.

## The refuted hypothesis

Bidirectional column diff with fill rates, live warehouse, 2026-09-01. "Exclusive" means a
populated column the other side lacks.

### Bucket A — GraphQL is the superset; REST side is droppable (3 pairs)

| Pair | GQL-only (fill) | REST-only |
|---|---|---|
| `draftPosition` / `draft_positions` | `draftPositionId` (1.00) | none |
| `draftTeam` / `draft_teams` | `draftTeamId` (1.00), `mascot` (0.97), `shortDisplayName` (1.00) | none |
| `predictedPoints` / `predicted_points` | `distance` (1.00), `down` (1.00) | none |

Small lookup tables. The win is tidiness, not data volume.

### Bucket B — REST is the superset; GraphQL side is droppable (3 pairs)

| Pair | GQL-only | REST-only |
|---|---|---|
| `coachSeason` / `coach_seasons` | **none** | **61 columns** incl. `coach_id`, `team_id`, `cfp_*`, `pollResume_*`, `draftFollowingSeason_*` |
| `teamTalent` / `talent` | **none** | `team` (1.00) |
| `recruit` / `recruits` | `overallRank` (**0.00**), `positionRank` (**0.00**) — all NULL | 10 populated incl. `athleteId`, `committedTo`, `position`, `school`, hometown geo |

The drop direction here is the **opposite** of the hypothesis. `recruit`'s two exclusive
columns contain no data at all, so the GraphQL table adds nothing.

Bucket B is provisional — see "Sequencing" below.

### Bucket C — genuinely complementary; merge, do not drop (7 pairs)

| Pair | GQL-only highlights | REST-only highlights |
|---|---|---|
| `game` / `games` | `awayEndElo` 0.59, `homeEndElo` 0.60, `*ConferenceId` 0.92–0.97 | `completed` 1.00, `highlights` 1.00, `venue`, `awayPregameElo` 0.44 |
| `gameLines` / `lines` | `linesProviderId`, `period`, `spread` 0.995, `overUnder` 0.994 | `homeTeam`/`awayTeam`, `homeScore` 0.94, `season`, conference/classification |
| `draftPicks` / `draft_picks` | `collegeTeamId`, `grade` 0.43, `overallRank` 0.37 | `collegeAthleteId` 0.99, `nflTeam`, `position`, hometown geo |
| `coach` / `coaches` | `coachId` 1.00 | `hireDate` 0.96, `seasons` 1.00 |
| `conference` / `conferences` | `division` 1.00, `srName` 0.004 | `classification` 1.00, `memberCount` 1.00 |
| `recruitingTeam` / `recruiting_teams` | `recruitingTeamId` 1.00 | `team` 1.00 |
| `calendar_gql` / `calendar` | `year` 1.00 | `firstGameStart`, `lastGameStart` 1.00 |

Note `game`/`games` carry Elo under different names *and different coverage* — GraphQL
`awayEndElo` is 0.59 filled against REST `awayPostgameElo` at 0.43. They are not the same
column twice; neither dominates.

## The scraper defect

`GQL_RELATION_KEYS` (`cfb_system_maker/graphql_client.py:44`) contains exactly one entry,
`pollRank`. `docs/graphql-schema-draft.md:119` already documents the general problem:

> `pollRank.poll`/`pollRank.team`, `coachSeason.coach`/`coachSeason.team`, and
> `teamTalent.team` expose the **relation only**. To materialize these as normal FK columns
> you must nest-select the id […] the flat `data/graphql/*.json` dumps (scalars-only) are
> missing these columns entirely.

`coachSeason` and `teamTalent` were never given entries. The observable result:

- `stg.coachSeason` — 12,564 rows, columns `season, year, week, season_type, games, losses, postseasonRank, preseasonRank, ties, wins, _source_file`. **No coach. No team.** Unjoinable.
- `stg.teamTalent` — 2,413 rows, columns `season, year, week, season_type, talent, _source_file`. **No team.** Unjoinable.

`GQL_EXCLUDED` already excludes `gameMedia` for precisely this reason ("no join key exists on
this root — a dump of it cannot be tied back to a game"). These two have the same disease and
were not caught.

### It is also a pagination-correctness bug

Relation keys are used for **both** selection and ordering
(`graphql_client.py:156-180`). The code's own comment states the sort must be a total order or
"an unsorted paginated pull can skip or repeat rows between pages." Neither `coachSeason` nor
`teamTalent` has an `id`, so both currently sort on scalars alone — for `teamTalent` that is
`(season, year, week, season_type, talent)`, which ties across every team sharing a talent
value. **The existing row counts may already be short.** Fixing the relation keys repairs
identity and pagination in one change.

## Dead columns

332 columns in `stg` are 100% NULL. They are not 332 separate problems:

- **308 are loader scaffolding.** `_insert_raw_file` (`duckdb_load.py:1565-1585`) binds `season`, `week`, `season_type` from `parse_dump_stem(path.stem)`. A GraphQL dump (`coachSeason.json`) has no season or week in its stem, so all three bind NULL; a REST dump (`games_2023.json`) has a season but no week. Those NULLs propagate into `stg`. Distribution: `season_type` NULL in 146 tables, `week` in 114, `season` in 48.
- **12 are future-dated and must be kept.** `lines_2026_week1*` / `lines_2026_week2*` `homeScore`/`awayScore` — those games have not been played.
- **12 are genuinely dead** and are the real drop list:

```
stg.plays.defenseTimeouts
stg.plays.offenseTimeouts
stg.plays.wallclock
stg.gameWeather.windGust
stg.pollType.abbreviation
stg.recruit.overallRank
stg.recruit.positionRank
stg.team_stats.statValue_anyof_schema_1_validator
stg.team_stats__statValue_any_of_schemas.statValue_anyof_schema_1_validator
stg.actionnetwork_scoreboard__teams.teams_standings_overtime_losses
stg.actionnetwork_scoreboard__markets__markets_event_moneyline.markets_event_moneyline_odds_coefficient_score
stg.actionnetwork_scoreboard__markets__markets_event_core_bet_type_6_team_score.markets_event_core_bet_type_6_team_score_odds_coefficient_score
```

## Merge keys

Merging is per-pair, not one mechanism applied 13 times.

| Pair | Join key | Status |
|---|---|---|
| `game` / `games` | `gameId` | direct |
| `gameLines` / `lines` | `gameId` | direct; `gameLines` is per-provider/period, `lines` is per-game — one-to-many |
| `draftPicks` / `draft_picks` | `(year, round, pick)` — neither side has an id (`graphql-schema-draft.md:126`) | natural key |
| `conference` / `conferences` | `conferenceId` | direct |
| `calendar_gql` / `calendar` | `(season, week)` — 16/16 weeks overlap | direct |
| `coach` / `coaches` | `(firstName, lastName)` — REST has no `coachId` | **name join, collision risk** |
| `recruitingTeam` / `recruiting_teams` | `recruitingTeamId` vs `team` (a name) | **needs `core.dim_team` to bridge** |

The last two cannot be merged on a scalar key alone and are called out as such.

## Sequencing

The order matters and is not arbitrary:

1. **Fix relation keys, re-scrape `coachSeason` and `teamTalent`.** Until this lands, Bucket B's verdict on those two is measured against a table that is missing its identity columns *and* may be missing rows.
2. **Fix scaffolding columns.** Independent of everything else; one loader change removes 308 dead columns.
3. **Re-measure containment.** Bucket assignments for `coachSeason` and `teamTalent` are recomputed from the re-scraped data. This gates step 5.
4. **Merge Bucket C.**
5. **Drop** — Bucket A's REST sides, Bucket B's GraphQL sides as re-confirmed by step 3, and the 12 dead columns.

Dropping before step 3 risks deleting a table that the scraper fix would have made the better source.

## Requirements

**R1** — `coachSeason` and `teamTalent` gain relation keys that materialize their FK columns and provide a total sort order.

**R2** — Re-scraped `stg.coachSeason` carries a coach identifier and a team identifier; `stg.teamTalent` carries a team identifier.

**R3** — Scaffolding columns (`season`, `week`, `season_type`) are not materialized in a `stg` table when they are entirely NULL for that table. Payload-derived columns are never auto-dropped by this rule.

**R4** — Containment is re-measured after R2 and the result recorded before any table is dropped.

**R5** — Bucket C pairs are merged into one table per concept, preserving every populated column from both sides, with a `_source` column recording provenance per row where the merge is a union rather than a join.

**R6** — Drops are proof-gated: a table is dropped only when the surviving table demonstrably contains every populated column and at least as many distinct keys.

**R7** — Scraper entries are removed only for sources whose tables were dropped under R6.

## Out of scope

- Table renaming — already done, and not by the scheme this plan first assumed. The
  `gql_<snake_case>` prefix was superseded by schema separation on 2026-09-01: GraphQL tables
  live in `stg_gql` under bare snake_case, REST stays in `stg`, and `raw` keeps its `gql_`
  prefix. Both migrations landed before this plan runs, so it uses **current live names**:
  `stg_gql.<bare>` and `stg.<rest>`.
- Column *casing* (984 camelCase columns) — deferred in the sibling spec, still deferred.
- `core` layer changes. `core.fact_game` etc. are built downstream; rebuilding them is a follow-up once `stg` settles.

## Global constraints

- `CFB_DATA_ROOT` required; local `data/cfb.duckdb` is source of truth, `md:cfb` is a manual mirror.
- Data is never committed.
- Do not edit `cfbd-python/`.
- Run commands from repository root.
- Default verification: `python -m pytest`.
- Re-scraping hits the live CFBD GraphQL API and needs a token; it is user-run, never automatic.
