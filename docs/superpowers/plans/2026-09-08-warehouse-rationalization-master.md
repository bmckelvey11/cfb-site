# Warehouse rationalization — master plan

**Status:** plan of record, 2026-09-08. **Revised 2026-09-09** against the live warehouse —
see `docs/warehouse-plan-review-2026-09-09.md` for what was wrong and how it was found.
Supersedes and absorbs the documents listed in §11. Step-level code lives in the execution
appendix (`docs/superpowers/plans/2026-09-01-warehouse-source-rationalization.md`); this
document is the authority on what is true, what is decided, and in what order it happens.

**Every measured claim below is reproduced by `python scripts/verify_warehouse_plan.py`**
(exit code = failed checks) and `--coverage` for per-pair year span. Re-run it before acting on
any number here. The 2026-09-08 draft carried a column census taken before the ActionNetwork
rename, and it survived into a drop list that would have deleted 6.4 M populated values; prose
is not a substitute for a run.

**Goal.** Make `stg` describe *what the data is* rather than *which API delivered it*: repair the
two GraphQL entities that were pulled without their identity, merge the genuinely complementary
source pairs into `core`, drop only what measurement proves superseded — and, as the last
transport-named thing goes away, collapse `stg_gql` back into a single `stg`.

---

## 1. What is true today (measured 2026-09-08, re-verified 2026-09-09, live `data/cfb.duckdb`)

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
references them about 50 times (measured 2026-09-09, excluding worktrees and docs:
`stg_gql.game` 20, `stg_gql.game_lines` 12, `stg_gql.lines_provider` 6, `stg_gql.calendar` 6,
`stg_gql.game_lines__backfill` 3, `stg_gql.game__away_line_scores` 2, `stg_gql.current_teams` 1)
— this is the exact operation that silently broke two consumers before
`tests/test_catalog_resolution.py` existed. Re-count before step 5; the figure has grown once
already. So:

1. The collapse happens **only behind** `tests/test_catalog_resolution.py` (already shipped,
   `56a84db`). That test is also a constraint, not only a net — see §8 step 5.
2. **ADR-0003 supersedes ADR-0002**, recording the measurement and the explicit-mapping
   alternative. ADR-0002 is retained, not deleted; its diagnosis was right and only its remedy
   was disproportionate. *(Landed 2026-09-08:
   `docs/adr/0003-one-stg-schema-suffix-only-the-colliders.md`, with ADR-0002 marked
   superseded.)*

## 3. The refuted hypothesis

`stg` holds 13 concept pairs, one GraphQL table and one REST table each. The working hypothesis
was that GraphQL is a superset and REST could be dropped from the scraper. **Bidirectional
column diff with fill rates refutes it for 10 of 13 pairs, and reverses the column direction for
3.** "Exclusive" means a populated column the other side lacks.

**Columns are half the test.** R6 gates a drop on the survivor holding every populated column
**and at least as many distinct keys**, and on year coverage the three column-reversed pairs all
fail it — the GraphQL side carries 12 to 126 more seasons. Only Bucket A is droppable.
`scripts/audit_canonical_sources.py` cannot see this: it reads year span from a column named
`season`, and every GraphQL table spells it `year`. Use
`scripts/verify_warehouse_plan.py --coverage`.

### Bucket A — GraphQL is the superset; the REST side is droppable (3 pairs)

| Pair | GQL-only (fill) | REST-only |
|---|---|---|
| `draft_position` / `draft_positions` | `draftPositionId` (1.00) | none |
| `draft_team` / `draft_teams` | `draftTeamId` (1.00), `mascot` (0.97), `shortDisplayName` (1.00) | none |
| `predicted_points` / `predicted_points` | `distance` (1.00), `down` (1.00) | none |

Small lookup tables. The win is tidiness, not data volume.

### Bucket B — REST is the *column* superset, GraphQL the *coverage* superset (2 pairs)

| Pair | GQL-only | REST-only |
|---|---|---|
| `coach_season` / `coach_seasons` | **none** | **61 columns** incl. `coach_id`, `team_id`, `cfp_*`, `pollResume_*` |
| `team_talent` / `talent` | **none** | `team` (1.00) |

The column direction is the **opposite** of the hypothesis — but that does not make the GraphQL
side droppable, because it carries the years:

| Pair | GraphQL | REST | Lost if GQL dropped |
|---|---|---|---|
| `coach_season` / `coach_seasons` | 12,564 rows, **1886–2026** | 1,961 rows, 2012–2025 | **126 seasons** |
| `team_talent` / `talent` | 2,413 rows, **2015–2026** | 2,278 rows, 2015–2025 | 2026 |

Both fail R6's distinct-key half. **So both merge, and neither is dropped** — the REST side
supplies the identity columns the GraphQL side lost to §4's defect, the GraphQL side supplies
the history. Bucket B is provisional in one direction only: §4's repair may add the FK columns
that make the merge a clean join rather than a union, but it cannot make either side droppable.
Re-measure at step 2 regardless.

`recruit` / `recruits` was in this bucket in the 2026-09-08 draft, marked droppable with no
provisional caveat and untouched by §4's defect. It is a Bucket C merge; see below.

### Bucket C — genuinely complementary; merge, do not drop (8 pairs)

| Pair | GQL-only highlights | REST-only highlights |
|---|---|---|
| `game` / `games` | `awayEndElo` 0.59, `homeEndElo` 0.60, `*ConferenceId` 0.92–0.97 | `completed` 1.00, `highlights` 1.00, `venue`, `awayPregameElo` 0.45 |
| `game_lines` / `lines__lines` | `linesProviderId`, `period`, `spread` 0.995, `overUnder` 0.994 | `homeTeam`/`awayTeam`, `homeScore` 0.94, `season`, classification |
| `draft_picks` / `draft_picks` | `collegeTeamId`, `grade` 0.43, `overallRank` 0.37 | `collegeAthleteId` 0.99, `nflTeam`, `position`, hometown geo |
| `coach` / `coaches` | `coachId` 1.00 | `hireDate` 0.96, `seasons` 1.00 |
| `conference` / `conferences` | `division` 1.00, `srName` 0.004 | `classification` 1.00, `memberCount` 1.00 |
| `recruiting_team` / `recruiting_teams` | `recruitingTeamId` 1.00 | `team` 1.00 |
| `calendar` / `calendar` | `year` 1.00 | `firstGameStart`, `lastGameStart` 1.00 |
| `recruit` / `recruits` | 28 seasons (2000–2027) against REST's 14 | 10 populated incl. `athleteId`, `committedTo`, `position`, hometown geo |

`game`/`games` carry Elo under different names *and different coverage* — GraphQL `awayEndElo`
is 0.591 filled against REST `awayPostgameElo` at 0.432. Not the same column twice; neither
dominates.

`recruit`/`recruits` is the same shape. Its two GraphQL-exclusive columns (`overallRank`,
`positionRank`) are 0.00 filled across 93,363 rows and go on §5's drop list — but the table does
not, because REST holds 45,927 rows over 2012–2025 against GraphQL's 93,363 over 2000–2027.
Dropping the GraphQL side loses 14 seasons of recruiting. Merge on `recruitId`.

**Bucket C merges are full outer unions, not left joins.** GraphQL out-rows REST on every pair
measured — `draft_picks` 13,080 to 3,584, `calendar` 424 to 258, `recruit` 93,363 to 45,927 —
so a join anchored on the REST side silently truncates. R5's `_source` column is what records
which side each row came from.

## 4. The scraper defect underneath

`GQL_RELATION_KEYS` (`cfb_system_maker/graphql_client.py:70`) contains exactly one entry,
`pollRank`. `coach_season` and `team_talent` were never given entries, so both were pulled
without the relation carrying their identity:

- `stg_gql.coach_season` — 12,564 rows, **no coach, no team.** Unjoinable.
- `stg_gql.team_talent` — 2,413 rows, **no team.** Unjoinable.

`GQL_EXCLUDED` already excludes `gameMedia` for precisely this reason. These two have the same
disease and were not caught.

**It is also a pagination-correctness bug.** Relation keys are used for both selection and
ordering (`graphql_client.py:194-206`), and the code's own comment says the sort must be a total
order or "an unsorted paginated pull can skip or repeat rows between pages." Neither entity has
an `id`, so both sort on `table.scalars` alone — the GraphQL scalar fields, not the
`season`/`week`/`season_type` spine, which is bound at load time from the dump filename and
never sent to the API. So `teamTalent` sorts on **`(year, talent)`**: 2,413 rows over 12
seasons, tying across every team sharing a talent value in a year. `coachSeason` sorts on
`(year, games, losses, postseasonRank, preseasonRank, ties, wins)`, which cannot separate two
coaches with identical records in the same year. **The existing row counts may already be
short.** Fixing the relation keys repairs identity and pagination in one change.

## 5. Dead columns

**11 columns** in `stg` + `stg_gql` are 100% NULL (measured 2026-09-09). The count itself moves
— a played 2026 game fills two of them, a new weekly `lines_*` dump adds more — so the verifier
prints it rather than asserting it, and gates on the two things that are actually invariant: no
listed dead column may be populated, and no spine column may be all-NULL. They are not 11
problems:

- **0 are loader scaffolding.** `_insert_json_file` (`duckdb_load.py:1928`) binds `season`,
  `week`, `season_type` from `parse_dump_stem(path.stem)`, but it inserts into **`raw`**, not
  `stg` — and `raw` is out of scope (§10 decision 5, §12). The spine reaches `stg` through
  `_RAW_SPINE` (`duckdb_load.py:480`) and `explode_payloads`, which already materializes a spine
  column only where the source has one (the
  `"season_type" if "season_type" in cols else NULL` pattern at `duckdb_load.py:1386`). Result:
  `season` exists in 112 of 162 `stg`/`stg_gql` tables, `week` in 44, `season_type` in 15, and
  **none of the three is all-NULL anywhere**. There is no loader change to make. See R3.
- **4 are future-dated and must be kept** — `stg.lines_2026_week2_20260908` and its `__lines`
  child, `homeScore`/`awayScore`. Those games have not been played.
- **7 are genuinely dead** and are the drop list:

```
stg.an_team.overtime_losses
stg.team_stats.statValue_anyof_schema_1_validator
stg.team_stats__statValue_any_of_schemas.statValue_anyof_schema_1_validator
stg_gql.game_weather.windGust
stg_gql.poll_type.abbreviation
stg_gql.recruit.overallRank
stg_gql.recruit.positionRank
```

**What the 2026-09-08 draft got wrong, and why it matters.** That version claimed 332 all-NULL
columns, 308 of them scaffolding removable by "one loader change," with a distribution
(`season_type` NULL in 146 tables, `week` in 114, `season` in 48) describing a warehouse that no
longer exists — `season_type` appears in 15 tables in total. Its 12-column drop list named three
`stg.plays` columns holding **6.4 M populated values** (`defenseTimeouts` 2,377,621,
`offenseTimeouts` 2,376,124, `wallclock` 1,628,388) and three `actionnetwork_scoreboard__*`
tables that the ActionNetwork rename replaced with `an_*`. One survivor of that rename,
`stg.an_team.overtime_losses`, is genuinely dead and is now on the list above.

The census predated the `raw` → ingest/staging split and the AN rename, and nothing re-ran it.
`scripts/verify_warehouse_plan.py` exists so that cannot happen twice: it re-derives this whole
section and exits non-zero on any entry that has gone live or gone missing.

## 6. Merge keys and per-pair targets

Merging is per-pair, not one mechanism applied 13 times. GraphQL names are shown at their
**current** location (`stg_gql.*`); after §2's collapse they are `stg.*`.

| Concept | GraphQL | REST | Join key | Target | Disposition |
|---|---|---|---|---|---|
| game | `stg_gql.game` | `stg.games` | `gameId` | `core.fact_game` (+`_postgame`, `_historical`) | merge |
| lines | `stg_gql.game_lines` | `stg.lines__lines` | `(gameId, provider, period)` after id↔name bridge | `core.fact_game_line` | merge, see §7 |
| draft pick | `stg_gql.draft_picks` | `stg.draft_picks` | `(year, round, pick)` — unique both sides, 13,080 / 3,584 | `core.dim_draft_pick` | merge |
| conference | `stg_gql.conference` | `stg.conferences` | `conferenceId` | `core.dim_conference` | merge |
| calendar | `stg_gql.calendar` | `stg.calendar` | `(season, week, seasonType)`, GraphQL spelling `year` for `season` | `core.dim_week` | merge |
| coach | `stg_gql.coach` | — | `coachId` | `core.dim_coach` + `core.coach_name_conflicts` | dimension, D3 |
| coach season | `stg_gql.coach_season` | `stg.coaches__seasons`, `stg.coach_seasons` | `(coachId, teamId, season)` after the scraper fix | `core.fact_coach_season` | merge at season grain |
| recruiting team | `stg_gql.recruiting_team` | `stg.recruiting_teams` | **none — needs `core.dim_team` to bridge** | — | deferred |
| draft position | `stg_gql.draft_position` | `stg.draft_positions` | `name` | — | drop REST |
| draft team | `stg_gql.draft_team` | `stg.draft_teams` | `name` | — | drop REST |
| predicted points | `stg_gql.predicted_points` | `stg.predicted_points` | `(down, distance, yardLine)` | — | drop REST |
| talent | `stg_gql.team_talent` | `stg.talent` | `(teamId, season)` after the scraper fix; union on `(year)` until then | `core.fact_team_talent` | merge — **re-measure first** |
| recruit | `stg_gql.recruit` | `stg.recruits` | `recruitId` | `core.dim_recruit` | merge |

Two pairs cannot merge on a scalar key alone and are called out as such: `coach`/`coaches`
(REST has no `coachId`, so it is a name join with collision risk) and
`recruiting_team`/`recruiting_teams` (an id against a name — no bridge exists, so it is
deferred, not merged).

**`calendar`'s key needs all three columns.** `(season, week)` is not unique on either side —
424 rows to 387 distinct on the GraphQL side, 258 to 231 on REST — because `seasonType` splits
regular from postseason. With `seasonType` both sides are fully unique. The GraphQL table has no
`season` column at all (`year`, `week`, `seasonType`, `startDate`, `endDate`), so the merge
renames rather than joins straight. All 258 REST keys are contained in the GraphQL side's 424;
REST spans 2012–2026, GraphQL 2002–2026.

**Cross-schema qualification is mandatory while `stg_gql` exists.** `draft_picks`, `calendar`
and `predicted_points` live in both schemas today; an unqualified table name in a join resolves
to the wrong source or not at all.

## 7. Lines correspondence

`stg_gql.game_lines` carries `linesProviderId` (an id); `stg.lines__lines` carries
`lines_provider` (a name). They join through the provider dimension. `stg_gql.game_lines` is
unique on `(gameId, linesProviderId, period)` — 63,730 of 63,730 as of 2026-09-09 — and supplies
1H/1Q rows that REST has no counterpart for; REST is full-game only. `period` is a clean
`VARCHAR` with exactly three values (`game` 47,202, `firsthalf` 8,274, `firstquarter` 8,254) and
normalizes directly. The row count grows with every refresh; the uniqueness is the invariant,
and `scripts/verify_warehouse_plan.py` is what asserts it.

## 8. Sequencing

The order is not arbitrary. Dropping before re-measurement risks deleting the table the scraper
fix would have made canonical.

| # | Step | Depends on | Note |
|---|---|---|---|
| 0 | **Preflight** | — | `python scripts/verify_warehouse_plan.py` must exit 0. It asserts the §1 counts, the three colliders, `raw`'s 34 `gql_` tables, §5's drop list and §6–7's merge keys. Then snapshot `data/cfb.duckdb` and content-hash every `data/graphql/*.json`; re-scrapes write to **new versioned paths**. |
| 1 | **Fix relation keys**, re-scrape `coach_season` and `team_talent` | 0 | Until this lands, Bucket B's merge on those two is a union on `year` rather than a join on FKs, and the row counts may be short (§4). User-run — it hits the live CFBD GraphQL API and needs a token. **This is the only gate on everything downstream.** |
| 2 | **Re-measure containment** and record the buckets | 1 | Gates step 4. Bucket assignments for the two repaired entities are recomputed from re-scraped data. `verify_warehouse_plan.py --coverage` plus `audit_canonical_sources.py`. |
| 3 | **Merge Bucket C** into `core` | 2 | Full outer unions with R5's `_source`, not left joins — GraphQL out-rows REST on every pair. |
| 4 | **Drop** Bucket A's REST sides and the 7 dead columns | 2, 3 | Proof-gated — see R6. **No Bucket B table is dropped**; both fail R6 on year coverage. |
| 5 | **Collapse `stg_gql` into `stg`** | 4, and `tests/test_catalog_resolution.py` | By this point the three colliders are already non-duplicate, so **zero suffixes are needed**. This is why the collapse comes last rather than first. Must land in one commit — see below. |
| 6 | **Remove scraper entries** for dropped sources | 5 | Config only. ADR-0003 already landed 2026-09-08. |

**Step 5 cannot be incremental.** `tests/test_catalog_resolution.py` asserts that *every*
non-docstring `<schema>.<table>` literal under `cfb_system_maker/`, `models/`, `research/` and
`scripts/` resolves against the live catalog. So the rename, all ~50 `stg_gql.*` literals, and
the test's own `ALLOW` entry for `("stg_gql", "game_lines__backfill")` move together in a single
commit, or the suite goes red between them. R8 is a constraint on how step 5 lands, not only a
safety net under it.

**Two steps from the 2026-09-08 draft are gone.** "Stop materializing all-NULL scaffolding
columns" removed zero columns and "rebuild `stg` so the pruning applies everywhere" had nothing
to apply — see §5 and R3. Their removal takes a multi-hour rebuild off the critical path and
leaves step 1, the user-run re-scrape, as the sole gate.

The recommendation's own sequencing table (§6) reaches the same conclusion from the other
direction: item 10, "source rationalization → suffix count goes to zero," is labelled *the real
project*.

## 9. Requirements

**R1** — `coach_season` and `team_talent` gain relation keys that materialize their FK columns
and provide a total sort order.
**R2** — Re-scraped `coach_season` carries a coach identifier and a team identifier;
`team_talent` carries a team identifier.
**R3** — ~~Scaffolding columns (`season`, `week`, `season_type`) are not materialized in a `stg`
table when entirely NULL for that table.~~ **Satisfied 2026-09-09, no work required.**
`explode_payloads` already materializes a spine column only where the source carries one, and no
spine column is all-NULL in any `stg`/`stg_gql` table (§5). Kept as a standing invariant:
`scripts/verify_warehouse_plan.py` reports the count, and a non-zero one is a regression.
**R4** — Containment is re-measured after R2 and recorded before any table is dropped.
**R5** — Bucket C pairs merge into one table per concept, preserving every populated column from
both sides, with a `_source` column recording provenance per row where the merge is a union
rather than a join. Merges are full outer unions unless one side's keys are proven contained in
the other's.
**R6** — Drops are proof-gated: a table is dropped only when the surviving table demonstrably
contains every populated column and at least as many distinct keys. **Column containment alone
is not sufficient** — year coverage is what disqualified Bucket B (§3).
**R7** — Scraper entries are removed only for sources whose tables were dropped under R6.
**R8** *(new, 2026-09-08; sharpened 2026-09-09)* — The `stg_gql` collapse runs only behind
`tests/test_catalog_resolution.py`, and only after step 4 has made the colliders non-duplicate.
Because that test scans every `<schema>.<table>` literal in the repo, the rename and every
reference to it land in **one commit**. No source suffix is introduced that this plan does not
also remove.

## 10. Key decisions, and what is still open

**Decisions**

1. **The superset hypothesis is dead.** It is refuted for 10 of 13 pairs and reversed for 3.
   Nothing in this plan acts on it.
2. **Only Bucket A is droppable — 3 pairs, not 6** *(2026-09-09)*. R6's distinct-key half
   disqualifies every column-reversed pair on year coverage; `recruit` moved to Bucket C. Ten of
   thirteen pairs merge.
3. **Repair before drop.** Fixing `coach_season`'s and `team_talent`'s relation keys changes the
   shape of their merge, so re-measurement still gates every drop.
4. **One `stg`, no transport in any name** (§2), with ADR-0003 superseding ADR-0002 — landed
   2026-09-08.
5. **`raw` is left alone**, prefix included. It is source fidelity and the prefix does real work.
   The loader scaffolding lives there (§5) and is not touched.
6. **`recruiting_team` / `recruiting_teams` is not mergeable** — settled by evidence, no join key
   exists. Deferred, not forced.
7. **Result-informed columns get physical separation, not tagging** — post-kickoff GraphQL
   columns land in `core.fact_game_postgame`, never in `fact_game`, per the repo's no-lookahead
   rule.
8. **Measured claims cite a run, not a date** *(2026-09-09)*. §1, §3, §5, §6 and §7 are
   reproduced by `scripts/verify_warehouse_plan.py`. §5 is why: it sat as prose through two
   migrations and went silently wrong.

**Open**

- **The plan's review loop ended in deadlock, not convergence.** Five Codex rounds, 31 findings,
  30 accepted (one rejected with reason: concurrency machinery for a single-writer local file).
  Findings narrowed from structural to specificational, but `VERDICT: APPROVED` never came.
  **Round 5's fixes are applied but were never re-reviewed** — that is the one genuinely open
  item from the loop, and it predates this synthesis. The 2026-09-09 review
  (`docs/warehouse-plan-review-2026-09-09.md`) is not that re-review: it checked this document
  against the live warehouse and the code, not the loop's findings against each other.
- Step 1 is user-run against a live API and is the gate on everything downstream.
- **Bucket C's five unre-measured pairs.** The 2026-09-09 review re-derived Buckets A and B and
  `game`/`games`' Elo fill rates, but not the column diffs for `game_lines`, `coach`,
  `conference`, `recruiting_team` or `draft_picks`. Step 2 covers them.

## 11. Document map — what this absorbs, what stands

**Absorbed into this document** (each now carries a banner pointing here; retained for audit
history, never cited as current):

| Document | What was carried forward |
|---|---|
| `PLAN.md` (repository root) | Goal, pair manifest, key decisions, containment gate, result-informed separation |
| `PLAN-REVIEW-LOG.md` (root) | The decisions the five rounds produced, and the deadlock's open item (§10) |
| `docs/superpowers/specs/2026-09-01-warehouse-source-rationalization.md` | Buckets, scraper defect, dead columns, merge keys, R1–R7. Its dead-column census and Bucket B drop verdicts were carried forward unchecked and are corrected here; see §5, §3. |
| `docs/warehouse-schema-recommendation.md` §3, §6 | The collapse decision (§2) and the sequencing it implies (§8). Its §0, §7, §8 record work already done and stay as history. |

**Execution appendix, still live:**
`docs/superpowers/plans/2026-09-01-warehouse-source-rationalization.md` — 1,373 lines of
task-level steps, code and expected output. This master is the authority on *what and why*; the
appendix is the authority on *how*. Where they disagree, this document wins and the appendix is
corrected.

**Shipped history, referenced not merged:** the naming rationalization plan and spec
(2026-08-31), the schema separation plan (2026-09-01), `docs/adr/0002-*` (superseded by
`0003-one-stg-schema-suffix-only-the-colliders.md`, 2026-09-08), and `CODEX-HANDOFF.md`
(bannered as superseded).

**Review of this document:** `docs/warehouse-plan-review-2026-09-09.md`, with
`scripts/verify_warehouse_plan.py` as its reproducible half.

**Untouched and still authoritative in its own right:** `docs/duckdb-warehouse-plan.md` —
`cfb_system_maker/CLAUDE.md` points at its MotherDuck promote runbook.

## 12. Out of scope

- Column *casing* (984 camelCase columns) — deferred, and still deferred.
- `core` layer changes beyond the targets named in §6's disposition table, plus
  `core.coach_name_conflicts`. *(The 2026-09-08 draft enumerated a shorter list here that §6
  already contradicted; §6 is the one place that decides targets.)*
- `raw` naming, in any form — **and `raw`'s loader scaffolding**, which is where `season`,
  `week` and `season_type` are bound (§5).
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
