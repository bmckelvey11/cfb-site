# Warehouse Naming Rationalization — Spec

**Status:** draft
**Date:** 2026-08-31
**Origin:** external schema audit, findings #4 (inconsistent naming) and #5 (duplicate concepts)

## Summary

The audit is right about the symptoms and wrong about the cause. Both findings trace to a
single mechanism: `stg` is fed by two ingestion sources that name their destination tables
differently, and the code that resolves name clashes between them is order-dependent.

## What the audit claimed vs what is true

| Audit claim | Verdict | Evidence |
|---|---|---|
| Schema "mixes snake_case, camelCase, Pascal-style" | **Confirmed** | 34 camelCase/singular tables in `stg` |
| Mixing is a design flaw from unrationalized naming | **Wrong cause** | camelCase names are *GraphQL root field names*, copied verbatim from the CFBD GraphQL API |
| `game`/`games`, `coach`/`coaches`, `draftPicks`/`draft_picks` are duplicate concepts | **Wrong cause, real symptom** | Each pair is one GraphQL table and one REST table — different endpoints, different coverage, not redundant copies |
| "Authoritative tables have not been fully rationalized" | **Confirmed as symptom** | Nothing in the schema or docs records which source is canonical per concept |

### The actual mechanism

`cfb_system_maker/graphql_client.py:26-38` defines `GQL_DEFAULT_TABLES`, 34 GraphQL root
fields. Those names flow through unchanged and become `stg` table names. REST endpoints land
as snake_case/plural. So:

- camelCase in `stg` means GraphQL-sourced
- snake_case in `stg` means REST-sourced

The GraphQL field names are an **upstream API contract**. They are not ours to rename. Only
the *destination table name* is ours.

### The correctness bug

`_stg_dest_name` (`cfb_system_maker/duckdb_load.py:1086`) resolves a name clash by appending
`_gql` only if the name is already in a `taken` set that is populated as loads proceed:

    def _stg_dest_name(name: str, taken: set[str]) -> str:
        if name.lower() not in taken:
            return name
        suffix = name + "_gql"
        if suffix.lower() not in taken:
            return suffix
        return "gql_" + name

Which source wins the unsuffixed name therefore depends on load order. `duckdb_load.py:494`
already carries a comment acknowledging this and works around it by sorting REST first — a
workaround, not a fix. One clash has fired in the live warehouse: `stg.calendar` (258 rows)
and `stg.calendar_gql` (424 rows), with nothing recording which is which.

This can silently swap a table's provenance across a rebuild. It is the one finding here that
is a correctness defect rather than ergonomics, and it leads the plan.

## Evidence: paired concepts and coverage

Row counts for every GraphQL/REST pair in the live warehouse (`estimated_size`, 2026-08-31):

| Concept | GraphQL table | rows | REST table | rows |
|---|---|---|---|---|
| game | `game` | 112,672 | `games` | 54,264 |
| coach | `coach` | 1,842 | `coaches` | 1,936 |
| conference | `conference` | 256 | `conferences` | 256 |
| draft pick | `draftPicks` | 13,080 | `draft_picks` | 3,584 |
| draft position | `draftPosition` | 31 | `draft_positions` | 29 |
| draft team | `draftTeam` | 32 | `draft_teams` | 32 |
| recruit | `recruit` | 93,363 | `recruits` | 45,927 |
| recruiting team | `recruitingTeam` | 4,578 | `recruiting_teams` | 3,183 |
| coach season | `coachSeason` | 12,564 | `coach_seasons` | 1,961 |
| predicted points | `predictedPoints` | 19,800 | `predicted_points` | 10,140 |
| talent | `teamTalent` | 2,413 | `talent` | 2,278 |
| lines | `gameLines` | 63,293 | `lines` | 15,384 |
| calendar | `calendar_gql` | 424 | `calendar` | 258 |

GraphQL usually carries more rows, but not always (`coaches` > `coach`). **Row count alone does
not establish canonicity** — the counts reflect which seasons and filters were pulled, not
which source is authoritative. Designating a canonical source per concept requires an audit
against stated criteria and is scoped as its own task, deferring deprecation.

## Blast radius

Genuine `stg.<camelCase>` table references in the live tree (excluding `.claude/worktrees/`):

- `cfb_system_maker/duckdb_load.py` — 7 lines (`gameLines`, `linesProvider`)
- `tests/test_duckdb_load.py` — 8 lines (same two tables)

Everything else matching a camelCase name is a GraphQL field name, a JSON dump filename
(`data/graphql/gameTeam.json`, read by `enrich.py`), or prose in docs.

Verified to have **zero** references: `web.py` (Flask app), `scripts/promote_to_motherduck.py`,
`storage.py`, `describe.py`, `search.py`, `backtest.py`, `v1_model.py`, `upcoming.py`,
`models/`, `research/`.

Because no external consumer reads these names, backward-compatibility views are not
warranted; the 15 lines are updated directly.

## Requirements

**R1 — Destination naming is explicit and total.** Every GraphQL entity maps to a `stg` table
name through an explicit dict, not through clash detection. The mapping must be injective and
its value set disjoint from REST destination names.

**R2 — Naming convention.** GraphQL-sourced `stg` tables are named `gql_<snake_case_entity>`.
This satisfies snake_case standardization (finding #4) and makes provenance legible at the call
site (finding #5). The `gql_` prefix is verified disjoint from all 173 existing `stg` names, so
the mapping cannot collide by construction.

**R3 — GraphQL field names are unchanged.** `GQL_DEFAULT_TABLES`, `GQL_RELATION_KEYS`, query
text, and `data/graphql/*.json` filenames keep their camelCase. Only destination table names
change.

**R4 — Bookkeeping stays consistent.** `meta.load_report` keys on `(schema, name)`
(`duckdb_load.py:1304`, `_finish_stg_table`). Any rename of an existing table must update the
matching `meta.load_report` rows, or a reload must regenerate them.

**R5 — Canonical source is audited, not guessed.** Produce a per-concept designation with a
stated criterion (season span, column coverage, null density). Deprecation of the
non-canonical table is explicitly out of scope for this plan.

**R6 — `raw` is untouched.** `raw` preserves source fidelity by design; its names do not change.

## Rename map (verified injective, disjoint, zero collisions)

| GraphQL entity | `stg` destination | GraphQL entity | `stg` destination |
|---|---|---|---|
| `game` | `gql_game` | `poll` | `gql_poll` |
| `gameLines` | `gql_game_lines` | `pollRank` | `gql_poll_rank` |
| `gameTeam` | `gql_game_team` | `pollType` | `gql_poll_type` |
| `gameWeather` | `gql_game_weather` | `calendar` | `gql_calendar` |
| `recruit` | `gql_recruit` | `conference` | `gql_conference` |
| `recruitingTeam` | `gql_recruiting_team` | `currentTeams` | `gql_current_teams` |
| `ratings` | `gql_ratings` | `historicalTeam` | `gql_historical_team` |
| `teamTalent` | `gql_team_talent` | `predictedPoints` | `gql_predicted_points` |
| `athlete` | `gql_athlete` | `draftPosition` | `gql_draft_position` |
| `athleteTeam` | `gql_athlete_team` | `draftTeam` | `gql_draft_team` |
| `coach` | `gql_coach` | `hometown` | `gql_hometown` |
| `coachSeason` | `gql_coach_season` | `linesProvider` | `gql_lines_provider` |
| `transfer` | `gql_transfer` | `playerStatCategory` | `gql_player_stat_category` |
| `adjustedPlayerMetrics` | `gql_adjusted_player_metrics` | `playerStatType` | `gql_player_stat_type` |
| `adjustedTeamMetrics` | `gql_adjusted_team_metrics` | `position` | `gql_position` |
| `draftPicks` | `gql_draft_picks` | `recruitPosition` | `gql_recruit_position` |
| | | `recruitSchool` | `gql_recruit_school` |
| | | `weatherCondition` | `gql_weather_condition` |

The live `stg.calendar_gql` (the GraphQL calendar, 424 rows) becomes `gql_calendar`. The REST
`stg.calendar` (258 rows) keeps its name.

Child tables produced by `explode_stg_lists()` follow their parent:

| Current | New |
|---|---|
| `game__awayLineScores` | `gql_game__away_line_scores` |
| `game__homeLineScores` | `gql_game__home_line_scores` |
| `gameTeam__lineScores` | `gql_game_team__line_scores` |
| `historicalTeam__images` | `gql_historical_team__images` |

## Out of scope (follow-up plans)

**Column naming.** 984 camelCase columns across 143 `stg`/`core` tables. Most are not GraphQL
at all — `gameInfo_awayPoints`, `teams_cumulativePpa`, `epaAllowed_passing` are generated by
`explode_stg_lists()` flattening nested JSON keys. Renaming them means changing the exploder's
key-flattening rule, which regenerates the 54 child tables landed in 3c7945e / 79c4d82.
Different subsystem, different risk, separate plan.

**Deprecating non-canonical tables.** Depends on R5's audit output. Separate plan.

## Global constraints

- `CFB_DATA_ROOT` is required; paths resolve through root `cfb_paths.py`. Local
  `data/cfb.duckdb` is source of truth; `md:cfb` is a manual mirror.
- Data is never committed.
- Do not edit `cfbd-python/` (vendored upstream).
- Run commands from repository root.
- Default verification: `python -m pytest` (672 tests currently pass).
- No lookahead: pre-game features use only pre-kickoff information.
