# Giving `coachSeason` and `teamTalent` their relation keys

**2026-09-10.** Reproduce the pull with
`python -c "from cfb_system_maker.graphql_client import graphql_scrape; graphql_scrape(only={'coachSeason','teamTalent'})"`.

## The question

`stg_gql.coach_season` was 12,564 rows of `(year, games, wins, losses, ties, preseasonRank,
postseasonRank)` — **no coach and no team**. `stg_gql.team_talent` was 2,413 rows of
`(year, talent)` — **no team**. Both were unjoinable to anything, which made them the only
gate on the whole source-rationalization chain.

Two things needed answering: which relations to lift, and whether the old dumps were also
*short*. `GQL_RELATION_KEYS` entries are selected **and** sorted on, and a table sorted only
on small repeating integers can drop rows between pages — `teamTalent` was ordered on
`(year, talent)`, which ties wherever two teams share a talent score.

## Method

Introspected both types live. The GraphQL type names are `CoachSeason` and `TeamTalent`
(capitalized), not the root field names — querying `__type(name: "coachSeason")` returns
null, which is what a first attempt looks like.

| Type | Relation | Target |
|---|---|---|
| `CoachSeason` | `coach` | `Coach` (`id`, `firstName`, `lastName`) |
| `CoachSeason` | `team` | `currentTeams` |
| `TeamTalent` | `team` | `currentTeams` |

`currentTeams` carries `teamId`, which is the FK both were missing. Added to
`GQL_RELATION_KEYS` following the `pollRank` precedent — enough columns to join and to
break ties, not the whole related row.

## Result

Both re-scraped clean, and the relations materialize:

| Table | Rows before | Rows after | Columns gained |
|---|---:|---:|---|
| `stg_gql.coach_season` | 12,564 | 12,564 | `coach_id`, `coach_firstName`, `coach_lastName`, `team_teamId`, `team_school`, `team_conference` |
| `stg_gql.team_talent` | 2,413 | 2,413 | `team_teamId`, `team_school`, `team_conference` |

**The row counts are identical, so the old dumps were not short.** The plan flagged that
they might be — sorting on scalars alone can drop rows across page boundaries — and on this
data it did not happen. That is worth recording because it means no *other* table's counts
are suspect on those grounds either; the defect was joinability, not completeness.

Residual nulls are real, not a mapping failure: 252 `coach_season` rows and 8 `team_talent`
rows have no `team.teamId`, i.e. the season's team is absent from `currentTeams`.

## What this does not support

- **It does not re-measure containment.** That is `#warehouse-remeasure-containment`, which
  this unblocks: the bucket assignments for these two entities were made against unjoinable
  dumps and have to be recomputed.
- **It does not verify the other 32 GraphQL tables.** Only these two were re-scraped. Any
  other table whose scalars do not identify a row has the same latent defect, and nothing
  here surveys for that.
- **It says nothing about whether the REST sides are droppable.** That is R6's proof gate,
  downstream of the re-measurement.

## Operational note: `duckdb --only` is not additive

Loading the two re-scraped tables with
`python -m cfb_system_maker duckdb --data-dir data --only coachSeason teamTalent`
**rebuilt `cfb.duckdb` containing only those two tables**, destroying every other `stg`,
`core` and `raw` table in the file. The flag scopes what gets *loaded*, not what gets
*kept*, and the command reports "2 table(s) loaded, 0 failed" either way.

Nothing was lost permanently — the warehouse is derived from `data/raw/`, `data/graphql/`
and `data/processed/`, all of which are intact — but the recovery is a full rebuild. Use
`scripts/refresh_cfbd.py`, or its post-scrape half (the three flattens, then
`build_duckdb(..., explode=True)`, then `build_core`). Treat `--only` as a full-rebuild
flag with a filter, never as an incremental load.
