# Plan: Warehouse source rationalization (merge, prune, drop)
_Locked via claudex-loop — by Claude + mckel_

## Goal

`stg` holds 13 concept pairs, each one GraphQL table and one REST table. Repair the two
GraphQL tables that are unjoinable because their identity was never pulled, remove the 308
dead scaffolding columns, conform the complementary pairs into `core`, and drop only what
measurement proves is superseded. The premise that GraphQL is a superset of REST is false and
this plan does not act on it.

## Approach

0. **Preflight.** Assert the naming migration is complete (every GraphQL entity resolves to its
   `gql_` name and no camelCase `stg` table remains) and record the resolved names. A partial
   rename state aborts the run. Snapshot `data/cfb.duckdb` and the `data/graphql/*.json`
   manifest; the snapshot is retained until step 9 validates.
1. **Probe the GraphQL schema.** Introspect the exact field paths for `coachSeason.coach`,
   `coachSeason.team`, and `teamTalent.team`. Each must be **to-one** (a to-many relation cannot
   produce a total order and is rejected outright), and the selected key must be non-null and
   unique within the relation. Confirm whether the team relation is named `team` or resolves via
   `currentTeams`. Gates step 2; failure stops the run rather than guessing.
2. **Add relation keys** for `coachSeason` and `teamTalent` to `GQL_RELATION_KEYS`, using only
   paths step 1 proved to-one. These feed both the selection (identity) and the sort (total
   order), repairing joinability and pagination stability in one change.
3. **Re-scrape** those two entities; reload; confirm the FK columns landed. Compare pulls by
   **identity-set diff**, not row count: record the API schema hash and pull timestamp, then
   report added keys, removed keys, duplicate keys, and a sample of changed rows. A pure
   pagination repair shows additions and no removals; removals or changed values on stable keys
   indicate upstream drift and stop the run.
4. **Prune scaffolding columns.** `prune_null_scaffolding` runs inside `_finish_stg_table`, so it
   is loader-level and survives rebuilds by construction. Rebuild `stg`, then rebuild a second
   time and assert the pruned set is identical — a rebuild that restores a pruned column means
   the rule is in the wrong place.
5. **Re-measure containment** on the repaired warehouse against the formal gate below, and record
   the verdicts. Hard gate on step 8.
6. **Prove the join before conforming.** For each pair bound for `core`, verify bidirectional key
   coverage: keys present on both sides, keys unique on each side, and a **value-conflict report**
   for every column both sides populate. No pair is conformed until its conflict report is empty
   or its per-column authority is declared.
7. **Conform into `core`.** `fact_game` keeps its REST spine and row count, gaining only the
   GraphQL-only columns on the pre-game allowlist; result-informed columns are tagged
   `result_lookahead` and excluded from model inputs. Rows are routed to
   `core.fact_game_historical` by **anti-join on validated `gameId`**, never by year boundary.
   Coach conforms on `coachId` with a published match-rate and an unmatched-rows report.
8. **Drop only what step 5 proves superseded**, within the bounds of D1 (see "What may be
   dropped"). Then drop the 12 named dead payload columns after a dependent-object check.
   Remove dropped sources from the scraper.
9. **Validate and document** — agreement gates re-run, snapshot released, `CONTEXT.md` glossary,
   ADR 0001, `docs/warehouse-sources.md`.

## What may be dropped (reconciles step 8 with D1)

D1 locked "`stg` sources stay" for **paired sources being conformed into `core`**. It did not
license dropping a table merely because a `core` table now covers it. Precisely:

- **Never dropped:** either side of a pair conformed into `core` (Bucket C). `core` is derived;
  `stg` remains the per-source shred it was built from.
- **Eligible:** a pair side with **zero populated exclusive columns** — it is a strict subset of
  its partner, so dropping it loses no information. Eligibility is computed at run time by
  `verdict()`, never read from this document.
- **Eligible:** the 12 named dead payload columns below.
- **Scraper removal** follows a table drop, never precedes it.

## Result-lookahead allowlist for `fact_game`

The repo forbids result-informed data entering pre-game features untagged. Of the ten
GraphQL-only columns:

| Column | Disposition |
|---|---|
| `homeStartElo`, `awayStartElo` | pre-game — added plainly |
| `homeConferenceId`, `awayConferenceId` | pre-game — added plainly |
| `homeEndElo`, `awayEndElo` | post-kickoff — tagged `result_lookahead` |
| `homePostgameWinProb`, `awayPostgameWinProb` | post-kickoff — tagged `result_lookahead` |
| `excitement` | post-kickoff — tagged `result_lookahead` |
| `status` | post-kickoff — tagged `result_lookahead` |

Tagged columns follow the existing mechanism in `cfb_system_maker/features.py:15` and are
quarantined from model inputs. A column whose timing is unclear is treated as result-informed.

## Containment gate (formal)

A side is superseded only when, for every column it holds:

- **Normalization** — names compared case-insensitively with underscores stripped
  (`season_type` matches `seasonType`).
- **Populated** — a column with zero non-NULL values is not evidence of anything and is excluded
  from both sides of the comparison. This is why `stg.recruit` is superseded despite holding two
  exclusive columns: both are 100% NULL.
- **Tolerance** — zero. There is no partial-supersession verdict; anything else is `MERGE`.
- **Freshness** — the measurement must post-date the last load of both tables; a stale
  measurement is refused rather than used.

## The 12 dead payload columns

Dropped only after confirming no view, `core` build, or test references them:

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

The twelve 2026-week `homeScore`/`awayScore` columns are **not** in this list — those games have
not been played.

## Key decisions & tradeoffs

- **D1 — Merged tables land in `core`; `stg` sources stay.** `stg` stays a faithful per-source
  shred, `core` is where sources get conformed. Merge is non-destructive; provenance always
  recoverable. Rejected: merging inside `stg` (adds a third table per concept and makes the
  ambiguity worse) and dropping sources (provenance unrecoverable without a full re-scrape).
  See ADR 0001.
- **D2 — `fact_game` gains columns, not rows.** GraphQL `stg.game` spans 1869–2026 (112,672
  rows); REST `stg.games` spans 1992–2026 (54,264). Modern seasons match exactly (2024
  3801/3801, 2025 3831/3831, 2026 3676/3676), so the surplus is entirely pre-1992 history.
  `fact_game` keeps its 54,264-row REST spine and gains the GraphQL-only columns for the
  overlapping span; pre-1992 goes to `core.fact_game_historical`. Agreement test 1 survives
  unchanged and deep history can never silently enter model training. See ADR 0001.
- **D3 — Coach conforms on `coachId`, collisions quarantined.** `stg.coach` (GraphQL) is a clean
  dimension: 1,842 rows / 1,840 distinct names, with exactly 2 real collisions (Paul Davis, Jeff
  Horton — 2 distinct `coachId`s each). `stg.coaches` (REST) is not a dimension: 1,936 rows /
  405 distinct names. REST rows resolve to a `coachId` by name; the 2 ambiguous names go to
  `core.coach_name_conflicts`. Rejected: a plain name join, which blends two distinct coaches
  and violates `CONTEXT.md`'s "Head coaches … not file-order last-write-wins".
- **`recruitingTeam` is not mergeable — settled by evidence, not preference.** 3,901 of its
  `recruitingTeamId`s are absent from `core.dim_team` (701 rows); the "id" is a row surrogate,
  not a team id, and REST carries only a team name. No bridge exists. Deferred.
- **GraphQL is not a superset.** 10 of 13 pairs carry populated exclusive columns both ways; for
  3 pairs REST is the superset (`coach_seasons` has 61 columns `coachSeason` lacks; `recruit`'s
  2 GraphQL-only columns are 100% NULL). The scraper-drop condition failed and is not acted on
  except where measurement supports it.
- **Sequencing: repair before drop.** Fixing `coachSeason`'s relation keys changes whether it is
  droppable. Drops are gated on a re-measurement taken after the repair, computed at run time
  rather than read from this document.
- **Ordering vs the naming plan.** `2026-08-31-warehouse-naming-rationalization.md` runs first;
  its rename blast radius is 15 lines today and grows once `core` build code references
  `stg.game` / `stg.coach`. This plan's code is written against post-rename names.

## Toolchain

Skill inventory matched `deprecation-and-migration` (step 8's drops and scraper removal) and
`code-review-and-quality`. Neither is loaded automatically. Both benches share
`~/.agents/skills` via symlink, so availability is symmetric. No generator or MCP capability is
required. Codex-side skill loading under headless `codex exec` is unverified and nothing in this
plan depends on it.

## Assumptions

Verified against the live warehouse, 2026-09-01:

1. GraphQL is not a superset of REST — bidirectional column diff with fill rates.
2. `stg.coachSeason` (12,564 rows) has no coach or team column; `stg.teamTalent` (2,413) has no team.
3. `GQL_RELATION_KEYS` contains one entry, `pollRank` — `graphql_client.py:44`.
4. 308 of 332 all-NULL `stg` columns are stem-bound scaffolding — `duckdb_load.py:1565`.
5. 12 all-NULL columns are future-dated 2026 lines (keep); 12 are genuinely dead.
6. `(year, round, pick)` is unique on both draft tables — 13,080/13,080 and 3,584/3,584.
7. `meta.load_report` keys on `(schema, name)` — `duckdb_load.py:1304`.
8. `core` is entirely REST-fed today; `core.fact_game` = 54,264 = `stg.games`, built at
   `duckdb_core.py:265`, protected by 7 agreement gates incl. a bowl-lookahead tripwire.
9. `core.dim_team` has 701 rows and cannot bridge `recruitingTeamId` (3,901 unmatched).
10. DuckDB DDL is transactional — ALTER is revertible via ROLLBACK. Known bug #3127
    (ADD COLUMN + INSERT interleaved) does not apply here.

Assumed, gated by step 1:

11. The GraphQL `Coach` type exposes a selectable `id`, and `currentTeams` is reachable as
    `team { teamId }` from `coachSeason` and `teamTalent` — source
    `docs/graphql-schema-draft.md:108,119`, a draft doc, not live introspection.

Assumed, unmeasured:

12. `coachSeason`/`teamTalent` pulls are currently short due to non-total sort. The mechanism is
    confirmed (Hasura offset pagination without a stable `order_by` skips or duplicates rows)
    but the shortfall on this data is not. Step 3 measures it.

## Risks / open questions

- Step 3's row-count change cannot distinguish "pagination fixed" from "upstream data changed".
  A large increase warrants spot-checking rows against the API.
- Widening `fact_game` with GraphQL columns touches an agreement-gated table. Test 1 asserts
  row-count coverage and should be unaffected by a column-only change, but tests 2–7 must be
  re-run and any failure treated as a design problem, not a test to update.
- GraphQL applies present-day classification retroactively (79,787 rows labelled `fbs` vs REST's
  26,827). `core.fact_game_historical` must not be treated as classification-accurate for its era.
- The 2 coach name conflicts need one manual resolution pass; the plan quarantines rather than
  resolves them.
- **Single-writer assumption, stated not engineered.** This runs against a local DuckDB file on
  one workstation; DuckDB enforces single-writer access. The plan therefore does not add lock
  management, versioned build tables, or atomic swap. If this warehouse ever gains concurrent
  writers or a second operator, every destructive step here needs revisiting first.

## Out of scope

- Table renaming to `gql_<snake_case>` — the sibling naming plan owns it and runs first.
- Column casing (984 camelCase columns) — deferred.
- `recruitingTeam` / `recruiting_teams` merge — no join key exists.
- Rebuilding `core` beyond `fact_game`'s added columns, `fact_game_historical`, `dim_coach`,
  and `coach_name_conflicts`.
