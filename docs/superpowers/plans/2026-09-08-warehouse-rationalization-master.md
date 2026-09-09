# Warehouse rationalization — master plan

**Status:** plan of record, 2026-09-08. Supersedes and absorbs the documents listed in
§11. Step-level code lives in the execution appendix
(`docs/superpowers/plans/2026-09-01-warehouse-source-rationalization.md`); this document is the
authority on what is true, what is decided, and in what order it happens.

**Goal.** Make `stg` describe *what the data is* rather than *which API delivered it*: repair the
two GraphQL entities that were pulled without their identity, delete the loader scaffolding that
manufactured 308 dead columns, merge the seven genuinely complementary source pairs into `core`,
drop only what measurement proves superseded — and, as the last transport-named thing goes away,
collapse `stg_gql` back into a single `stg`.

---

## 1. What is true today (measured 2026-09-08, live `data/cfb.duckdb`)

| | |
|---|---|
| `stg` tables | 124 |
| `stg_gql` tables | 38 |
| `raw` tables | 116, of which 34 keep a `gql_` prefix |
| **Exact name collisions if `stg_gql` merged into `stg`** | **3** — `calendar`, `draft_picks`, `predicted_points` |
| `stg_gql` tables with no REST counterpart of any spelling | **28 of 38** |
| "Near-miss" plural pairs (`game`/`games`, `coach_season`/`coach_seasons`, …) | 7 — **distinct names, not collisions** |

Two migrations already landed and are not in scope to redo:

- **Naming rationalization** (2026-08-31) replaced load-order-dependent clash resolution with the
  explicit total mapping `GQL_ENTITY_TO_STG`. That mapping is the mechanism the rest of this
  plan relies on; only its *values* have changed since.
- **Schema separation** (2026-09-01, ADR-0002) moved GraphQL-sourced tables from a
  `gql_<snake_case>` prefix in `stg` to bare snake_case names in a `stg_gql` schema.

`raw` was deliberately excluded from both and stays a single schema: its GraphQL dumps keep the
`gql_` prefix (`raw.gql_game`) so they do not collide with REST dumps of the same name. **That
prefix is load-bearing — nothing in this plan strips it.**

## 2. The naming end state — one `stg`, nothing named after a transport

**Decided 2026-09-08.** The end state is a single `stg` schema. This adopts
`docs/warehouse-schema-recommendation.md` §3 and supersedes ADR-0002's remedy.

The measurement above is the argument. A schema called `stg_gql` tags all 38 tables to
disambiguate 3, and 28 of them have no counterpart of any spelling to be disambiguated from.
ADR-0002's own reasoning cuts against it: it rejected the `gql_` prefix because provenance would
be "encoded in a string a reader has to know to interpret" and the table would be "permanently
named after which API produced it rather than what it is." Both objections apply verbatim to a
*schema* named `stg_gql`, at coarser granularity.

ADR-0002 diagnosed the real bug correctly — `_stg_dest_name` resolved clashes against a `taken`
set populated as loads proceeded, so which source won a name depended on load order. But an
explicit static mapping fixes that, and one already ships. A separate schema was a
disproportionate remedy.

**Target naming:**

```
stg.athlete   stg.game_lines   stg.current_teams    # 28 tables, no tag needed
stg.game      stg.games                             # distinct already, no tag
stg.draft_picks_gql   stg.draft_picks               # 1 of 3 needing a temporary tag
stg.calendar_gql      stg.calendar                  # 2 of 3
stg.predicted_points                                # 3rd needs no tag — Bucket A drops REST
```

**The suffixes are temporary by construction, and this plan is what removes them.** All three
colliders are exactly the tables that stop existing in duplicate: `predicted_points` drops its
REST side (Bucket A), `draft_picks` and `calendar` merge into `core` (Bucket C). When
rationalization completes the suffix count is zero and no name in the schema refers to a
transport.

**Two hard conditions.** The collapse renames the qualified name of all 38 tables, and code
references them 30+ times (`stg_gql.game` 13, `stg_gql.game_lines` 12, `stg_gql.lines_provider`
6, `stg_gql.calendar` 4) — this is the exact operation that silently broke two consumers before
`tests/test_catalog_resolution.py` existed. So:

1. The collapse happens **only behind** `tests/test_catalog_resolution.py` (already shipped,
   `56a84db`).
2. **ADR-0003 supersedes ADR-0002**, recording the measurement and the explicit-mapping
   alternative. ADR-0002 is retained, not deleted; its diagnosis was right and only its remedy
   was disproportionate.

## 3. The refuted hypothesis

`stg` holds 13 concept pairs, one GraphQL table and one REST table each. The working hypothesis
was that GraphQL is a superset and REST could be dropped from the scraper. **Bidirectional
column diff with fill rates refutes it for 10 of 13 pairs, and reverses it for 3.** "Exclusive"
means a populated column the other side lacks.

### Bucket A — GraphQL is the superset; the REST side is droppable (3 pairs)

| Pair | GQL-only (fill) | REST-only |
|---|---|---|
| `draft_position` / `draft_positions` | `draftPositionId` (1.00) | none |
| `draft_team` / `draft_teams` | `draftTeamId` (1.00), `mascot` (0.97), `shortDisplayName` (1.00) | none |
| `predicted_points` / `predicted_points` | `distance` (1.00), `down` (1.00) | none |

Small lookup tables. The win is tidiness, not data volume.

### Bucket B — REST is the superset; the GraphQL side is droppable (3 pairs)

| Pair | GQL-only | REST-only |
|---|---|---|
| `coach_season` / `coach_seasons` | **none** | **61 columns** incl. `coach_id`, `team_id`, `cfp_*`, `pollResume_*` |
| `team_talent` / `talent` | **none** | `team` (1.00) |
| `recruit` / `recruits` | `overallRank` (**0.00**), `positionRank` (**0.00**) — all NULL | 10 populated incl. `athleteId`, `committedTo`, `position`, hometown geo |

The drop direction is the **opposite** of the hypothesis. `recruit`'s two exclusive columns hold
no data at all. **Bucket B is provisional** until §4's scraper defect is repaired — see §6.

### Bucket C — genuinely complementary; merge, do not drop (7 pairs)

| Pair | GQL-only highlights | REST-only highlights |
|---|---|---|
| `game` / `games` | `awayEndElo` 0.59, `homeEndElo` 0.60, `*ConferenceId` 0.92–0.97 | `completed` 1.00, `highlights` 1.00, `venue`, `awayPregameElo` 0.44 |
| `game_lines` / `lines__lines` | `linesProviderId`, `period`, `spread` 0.995, `overUnder` 0.994 | `homeTeam`/`awayTeam`, `homeScore` 0.94, `season`, classification |
| `draft_picks` / `draft_picks` | `collegeTeamId`, `grade` 0.43, `overallRank` 0.37 | `collegeAthleteId` 0.99, `nflTeam`, `position`, hometown geo |
| `coach` / `coaches` | `coachId` 1.00 | `hireDate` 0.96, `seasons` 1.00 |
| `conference` / `conferences` | `division` 1.00, `srName` 0.004 | `classification` 1.00, `memberCount` 1.00 |
| `recruiting_team` / `recruiting_teams` | `recruitingTeamId` 1.00 | `team` 1.00 |
| `calendar` / `calendar` | `year` 1.00 | `firstGameStart`, `lastGameStart` 1.00 |

`game`/`games` carry Elo under different names *and different coverage* — GraphQL `awayEndElo`
is 0.59 filled against REST `awayPostgameElo` at 0.43. Not the same column twice; neither
dominates.

## 4. The scraper defect underneath

`GQL_RELATION_KEYS` (`cfb_system_maker/graphql_client.py:44`) contains exactly one entry,
`pollRank`. `coach_season` and `team_talent` were never given entries, so both were pulled
without the relation carrying their identity:

- `stg_gql.coach_season` — 12,564 rows, **no coach, no team.** Unjoinable.
- `stg_gql.team_talent` — 2,413 rows, **no team.** Unjoinable.

`GQL_EXCLUDED` already excludes `gameMedia` for precisely this reason. These two have the same
disease and were not caught.

**It is also a pagination-correctness bug.** Relation keys are used for both selection and
ordering (`graphql_client.py:156-180`), and the code's own comment says the sort must be a total
order or "an unsorted paginated pull can skip or repeat rows between pages." Neither entity has
an `id`, so both sort on scalars alone — for `team_talent` that is `(season, year, week,
season_type, talent)`, which ties across every team sharing a talent value. **The existing row
counts may already be short.** Fixing the relation keys repairs identity and pagination in one
change.

## 5. Dead columns

332 columns in `stg` are 100% NULL. They are not 332 problems:

- **308 are loader scaffolding.** `_insert_raw_file` (`duckdb_load.py:1565-1585`) binds `season`,
  `week`, `season_type` from `parse_dump_stem(path.stem)`. A GraphQL dump (`coachSeason.json`)
  has none of the three in its stem; a REST dump (`games_2023.json`) has a season but no week.
  Distribution: `season_type` NULL in 146 tables, `week` in 114, `season` in 48. One loader
  change removes all 308.
- **12 are future-dated and must be kept** — `lines_2026_week1*` / `lines_2026_week2*`
  `homeScore`/`awayScore`. Those games have not been played.
- **12 are genuinely dead** and are the drop list:

```
stg.plays.defenseTimeouts
stg.plays.offenseTimeouts
stg.plays.wallclock
stg_gql.game_weather.windGust
stg_gql.poll_type.abbreviation
stg_gql.recruit.overallRank
stg_gql.recruit.positionRank
stg.team_stats.statValue_anyof_schema_1_validator
stg.team_stats__statValue_any_of_schemas.statValue_anyof_schema_1_validator
stg.actionnetwork_scoreboard__teams.teams_standings_overtime_losses
stg.actionnetwork_scoreboard__markets__markets_event_moneyline.markets_event_moneyline_odds_coefficient_score
stg.actionnetwork_scoreboard__markets__markets_event_core_bet_type_6_team_score.markets_event_core_bet_type_6_team_score_odds_coefficient_score
```

## 6. Merge keys and per-pair targets

Merging is per-pair, not one mechanism applied 13 times. GraphQL names are shown at their
**current** location (`stg_gql.*`); after §2's collapse they are `stg.*`.

| Concept | GraphQL | REST | Join key | Target | Disposition |
|---|---|---|---|---|---|
| game | `stg_gql.game` | `stg.games` | `gameId` | `core.fact_game` (+`_postgame`, `_historical`) | merge |
| lines | `stg_gql.game_lines` | `stg.lines__lines` | `(gameId, provider, period)` after id↔name bridge | `core.fact_game_line` | merge, see §7 |
| draft pick | `stg_gql.draft_picks` | `stg.draft_picks` | `(year, round, pick)` — unique both sides | `core.dim_draft_pick` | merge |
| conference | `stg_gql.conference` | `stg.conferences` | `conferenceId` | `core.dim_conference` | merge |
| calendar | `stg_gql.calendar` | `stg.calendar` | `(season, week)` — 16/16 overlap | `core.dim_week` | merge |
| coach | `stg_gql.coach` | — | `coachId` | `core.dim_coach` + `core.coach_name_conflicts` | dimension, D3 |
| coach season | `stg_gql.coach_season` | `stg.coaches__seasons`, `stg.coach_seasons` | `(coachId, teamId, season)` after the scraper fix | `core.fact_coach_season` | merge at season grain |
| recruiting team | `stg_gql.recruiting_team` | `stg.recruiting_teams` | **none — needs `core.dim_team` to bridge** | — | deferred |
| draft position | `stg_gql.draft_position` | `stg.draft_positions` | `name` | — | drop REST |
| draft team | `stg_gql.draft_team` | `stg.draft_teams` | `name` | — | drop REST |
| predicted points | `stg_gql.predicted_points` | `stg.predicted_points` | `(down, distance, yardLine)` | — | drop REST |
| talent | `stg_gql.team_talent` | `stg.talent` | `(teamId, season)` after the scraper fix | — | drop GQL — **re-measure first** |
| recruit | `stg_gql.recruit` | `stg.recruits` | `recruitId` | — | drop GQL |

Two pairs cannot merge on a scalar key alone and are called out as such: `coach`/`coaches`
(REST has no `coachId`, so it is a name join with collision risk) and
`recruiting_team`/`recruiting_teams` (an id against a name — no bridge exists, so it is
deferred, not merged).

**Cross-schema qualification is mandatory while `stg_gql` exists.** `draft_picks`, `calendar`
and `predicted_points` live in both schemas today; an unqualified table name in a join resolves
to the wrong source or not at all.

## 7. Lines correspondence

`stg_gql.game_lines` carries `linesProviderId` (an id); `stg.lines__lines` carries
`lines_provider` (a name). They join through the provider dimension. `stg_gql.game_lines` is
unique on `(gameId, linesProviderId, period)` — 63,293 of 63,293 — and supplies 1H/1Q rows that
REST has no counterpart for; REST is full-game only. `period` is a clean `VARCHAR` with exactly
three values and normalizes directly.

## 8. Sequencing

The order is not arbitrary. Dropping before re-measurement risks deleting the table the scraper
fix would have made canonical.

| # | Step | Depends on | Note |
|---|---|---|---|
| 0 | **Preflight** | — | Assert `stg_gql` exists with 38 bare snake_case tables, `stg` has zero `gql_`-prefixed tables, `raw` still has its 34, no camelCase `stg` table remains. Snapshot `data/cfb.duckdb`. Content-hash every `data/graphql/*.json`; re-scrapes write to **new versioned paths**. |
| 1 | **Fix relation keys**, re-scrape `coach_season` and `team_talent` | 0 | Until this lands, Bucket B's verdict on those two is measured against tables missing their identity columns and possibly rows. User-run — it hits the live CFBD GraphQL API and needs a token. |
| 2 | **Stop materializing all-NULL scaffolding columns** | 0 | Independent of everything else; removes 308 columns. |
| 3 | **Rebuild `stg`** so the pruning applies everywhere | 2 | |
| 4 | **Re-measure containment** and record the buckets | 1, 3 | Gates step 6. Bucket assignments for the two repaired entities are recomputed from re-scraped data. |
| 5 | **Merge Bucket C** into `core` | 4 | |
| 6 | **Drop** Bucket A's REST sides, Bucket B's GraphQL sides as re-confirmed by step 4, and the 12 dead columns | 4, 5 | Proof-gated — see R6. |
| 7 | **Collapse `stg_gql` into `stg`** | 6, and `tests/test_catalog_resolution.py` | By this point the three colliders are already non-duplicate, so **zero suffixes are needed**. This is why the collapse comes last rather than first. |
| 8 | **ADR-0003** superseding ADR-0002; remove scraper entries for dropped sources | 7 | Docs and config only. |

The recommendation's own sequencing table (§6) reaches the same conclusion from the other
direction: item 10, "source rationalization → suffix count goes to zero," is labelled *the real
project*.

## 9. Requirements

**R1** — `coach_season` and `team_talent` gain relation keys that materialize their FK columns
and provide a total sort order.
**R2** — Re-scraped `coach_season` carries a coach identifier and a team identifier;
`team_talent` carries a team identifier.
**R3** — Scaffolding columns (`season`, `week`, `season_type`) are not materialized in a `stg`
table when entirely NULL for that table. Payload-derived columns are never auto-dropped by this
rule.
**R4** — Containment is re-measured after R2 and recorded before any table is dropped.
**R5** — Bucket C pairs merge into one table per concept, preserving every populated column from
both sides, with a `_source` column recording provenance per row where the merge is a union
rather than a join.
**R6** — Drops are proof-gated: a table is dropped only when the surviving table demonstrably
contains every populated column and at least as many distinct keys.
**R7** — Scraper entries are removed only for sources whose tables were dropped under R6.
**R8** *(new, 2026-09-08)* — The `stg_gql` collapse runs only behind
`tests/test_catalog_resolution.py`, and only after step 6 has made the colliders non-duplicate.
No source suffix is introduced that this plan does not also remove.

## 10. Key decisions, and what is still open

**Decisions**

1. **The superset hypothesis is dead.** It is refuted for 10 of 13 pairs and reversed for 3.
   Nothing in this plan acts on it.
2. **Repair before drop.** Fixing `coach_season`'s and `team_talent`'s relation keys changes
   whether they are the droppable side, so re-measurement gates every drop.
3. **One `stg`, no transport in any name** (§2), with ADR-0003 superseding ADR-0002.
4. **`raw` is left alone**, prefix included. It is source fidelity and the prefix does real work.
5. **`recruiting_team` / `recruiting_teams` is not mergeable** — settled by evidence, no join key
   exists. Deferred, not forced.
6. **Result-informed columns get physical separation, not tagging** — post-kickoff GraphQL
   columns land in `core.fact_game_postgame`, never in `fact_game`, per the repo's no-lookahead
   rule.

**Open**

- **The plan's review loop ended in deadlock, not convergence.** Five Codex rounds, 31 findings,
  30 accepted (one rejected with reason: concurrency machinery for a single-writer local file).
  Findings narrowed from structural to specificational, but `VERDICT: APPROVED` never came.
  **Round 5's fixes are applied but were never re-reviewed** — that is the one genuinely open
  item from the loop, and it predates this synthesis.
- Step 1 is user-run against a live API and is the gate on everything downstream.

## 11. Document map — what this absorbs, what stands

**Absorbed into this document** (each now carries a banner pointing here; retained for audit
history, never cited as current):

| Document | What was carried forward |
|---|---|
| `PLAN.md` (repository root) | Goal, pair manifest, key decisions, containment gate, result-informed separation |
| `PLAN-REVIEW-LOG.md` (root) | The decisions the five rounds produced, and the deadlock's open item (§10) |
| `docs/superpowers/specs/2026-09-01-warehouse-source-rationalization.md` | Buckets, scraper defect, dead columns, merge keys, R1–R7 |
| `docs/warehouse-schema-recommendation.md` §3, §6 | The collapse decision (§2) and the sequencing it implies (§8). Its §0, §7, §8 record work already done and stay as history. |

**Execution appendix, still live:**
`docs/superpowers/plans/2026-09-01-warehouse-source-rationalization.md` — 1,373 lines of
task-level steps, code and expected output. This master is the authority on *what and why*; the
appendix is the authority on *how*. Where they disagree, this document wins and the appendix is
corrected.

**Shipped history, referenced not merged:** the naming rationalization plan and spec
(2026-08-31), the schema separation plan (2026-09-01), `docs/adr/0002-*` (to be superseded by
0003), and `CODEX-HANDOFF.md` (bannered as superseded).

**Untouched and still authoritative in its own right:** `docs/duckdb-warehouse-plan.md` —
`cfb_system_maker/CLAUDE.md` points at its MotherDuck promote runbook.

## 12. Out of scope

- Column *casing* (984 camelCase columns) — deferred, and still deferred.
- `core` layer changes beyond `fact_game`'s added columns, `fact_game_postgame`,
  `fact_game_historical`, `dim_coach`, and `coach_name_conflicts`.
- `raw` naming, in any form.
- GraphQL **entity and field** names — `coachSeason`, `teamTalent`, `gameLines` — are an upstream
  API contract. They stay camelCase everywhere and are not table names; do not sweep them into
  any rename.
- Re-scraping is user-run and never automatic.

## 13. Global constraints

- `CFB_DATA_ROOT` is required; local `data/cfb.duckdb` is source of truth, `md:cfb` is a manual
  mirror. Data is never committed.
- Do not edit `cfbd-python/`.
- No lookahead: result-informed columns are physically separated, never merely tagged.
- Run commands from the repository root. Default verification: `python -m pytest`.
