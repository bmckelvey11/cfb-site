# Plan: Warehouse source rationalization (merge, prune, drop)
_Locked via claudex-loop — by Claude + mckel_

## Goal

`stg` holds 13 concept pairs, each one GraphQL table and one REST table. Repair the two
GraphQL tables that are unjoinable because their identity was never pulled, remove the 308
dead scaffolding columns, conform the complementary pairs into `core`, and drop only what
measurement proves is superseded. The premise that GraphQL is a superset of REST is false and
this plan does not act on it.

**Naming.** Every `stg` name below is the **post-migration** name. The naming plan
(`docs/superpowers/plans/2026-08-31-warehouse-naming-rationalization.md`) runs first and renames
GraphQL-sourced tables to `gql_<snake_case>`; REST names are unchanged. Step 0 aborts if that
migration is incomplete.

## Approach

0. **Preflight.** Assert the naming migration is complete — every GraphQL entity resolves to its
   `gql_` name and no camelCase `stg` table remains — and record the resolved names. A partial
   rename state aborts the run. Snapshot `data/cfb.duckdb`. Copy every `data/graphql/*.json` to a
   content-hashed path; re-scrapes write to **new versioned paths** and never overwrite the
   originals until step 9 validates.
1. **Probe the GraphQL schema.** Introspect the exact field paths for `coachSeason.coach`,
   `coachSeason.team`, and `teamTalent.team`, and confirm whether the team relation is named
   `team` or resolves via `currentTeams`. Each must be **to-one** — a to-many relation cannot
   produce a total order and is rejected outright. Then prove the *root-level* sort tuple works:
   the full `orderBy` tuple (relation keys followed by scalars) must be **non-null and unique
   across root rows**, not merely unique within the relation. Uniqueness inside the relation says
   nothing about ties between two root rows sharing the same coach, team, and season. Gates
   step 2; failure stops the run rather than guessing.
2. **Add relation keys** for `coachSeason` and `teamTalent` to `GQL_RELATION_KEYS`, using only
   paths step 1 proved to-one with a unique root-level sort tuple.
3. **Re-scrape** those two entities to versioned paths; load; confirm the FK columns landed.
   Then establish the pull is *stable*, which two live pulls cannot do on their own:
   - Record the API schema hash and pull timestamp.
   - Run the same pull **twice** and require an identical identity set. A pull that differs from
     itself is not evidence of anything and stops the run.
   - Only then diff against the old pull: report added keys, removed keys, duplicate keys, and a
     sample of changed rows. A pagination repair shows additions and no removals; removals or
     changed values on stable keys indicate upstream drift and stop the run.
   - **Version selection is explicit.** The loader reads a version manifest naming exactly which
     dump file each entity loads from; it never globs a directory that now holds two generations
     of the same entity. The new version is promoted in the manifest only after steps 5-7 pass,
     so a failed run leaves the previous version selected and the warehouse rebuildable from it.
4. **Prune scaffolding columns.** `prune_null_scaffolding` runs inside `_finish_stg_table`, so it
   is loader-level and survives rebuilds by construction. Rebuild `stg`, then rebuild a second
   time and assert the pruned set is identical — a rebuild that restores a pruned column means
   the rule is in the wrong place.
5. **Re-measure containment** against the formal gate below and record the verdicts. Hard gate on
   step 8.
6. **Prove the join before conforming.** For each pair bound for `core`: bidirectional key
   coverage, key uniqueness on each side, and a **value-conflict report** for every column both
   sides populate. No pair is conformed until its conflict report is empty or its per-column
   authority is declared in the manifest.
7. **Conform into `core`.** `fact_game` keeps its REST spine and row count, gaining only the four
   pre-game GraphQL columns. The six post-kickoff columns go to a **separate**
   `core.fact_game_postgame` (see below). Rows are routed to `core.fact_game_historical` by
   **anti-join on validated `gameId`**, never by year boundary. `core.dim_coach` is built from
   `gql_coach` alone (coach grain); REST `coaches` conforms into `core.fact_coach_season` at
   season grain, with a published match-rate and an unmatched-rows report.
8. **Drop only what step 5 proves superseded**, within the bounds of D1 (see "What may be
   dropped"). Then drop the 12 named dead payload columns after a dependent-object check. Remove
   dropped sources from the scraper.
9. **Validate and document** — agreement gates re-run, snapshot and versioned pulls released,
   `CONTEXT.md` glossary, ADR 0001, `docs/warehouse-sources.md`.

## Pair manifest

Post-rename names. Disposition is the *prior* measurement and is **not** authoritative — step 5
recomputes it at run time and step 8 obeys the recomputed value.

| Concept | GraphQL | REST | Join key | Target | Prior disposition |
|---|---|---|---|---|---|
| game | `gql_game` | `games` | `gameId` | `core.fact_game` (+`_postgame`, `_historical`) | merge |
| lines | `gql_game_lines` | `lines__lines` (exploded) | `(gameId, provider, period)` after id↔name bridge | `core.fact_game_line` | merge, see correspondence |
| draft pick | `gql_draft_picks` | `draft_picks` | `(year, round, pick)` — unique both sides | `core.dim_draft_pick` | merge |
| conference | `gql_conference` | `conferences` | `conferenceId` | `core.dim_conference` | merge |
| calendar | `gql_calendar` | `calendar` | `(season, week)` — 16/16 overlap | `core.dim_week` | merge |
| coach | `gql_coach` | — | `coachId` | `core.dim_coach` + `core.coach_name_conflicts` | dimension, D3 |
| coach season | `gql_coach_season` | `coaches`, `coach_seasons` | `(coachId, teamId, season)` after step 3 | `core.fact_coach_season` | merge at season grain |
| recruiting team | `gql_recruiting_team` | `recruiting_teams` | **none — no bridge** | — | deferred |
| draft position | `gql_draft_position` | `draft_positions` | `name` | — | drop REST |
| draft team | `gql_draft_team` | `draft_teams` | `name` | — | drop REST |
| predicted points | `gql_predicted_points` | `predicted_points` | `(down, distance, yardLine)` | — | drop REST |
| talent | `gql_team_talent` | `talent` | `(teamId, season)` after step 3 | — | drop GQL — **re-measure** |
| recruit | `gql_recruit` | `recruits` | `recruitId` | — | drop GQL |

The row marked **re-measure** (`talent`) and the coach-season row are the ones steps 1–3 repair;
their disposition is expected to change and must not be carried forward from this table.

### Grain is not assumed — it is measured

Two pairs turned out to have mismatched grain, which a `gameId`-style join would have silently
collapsed:

- **lines.** `gql_game_lines` is unique on `(gameId, linesProviderId, period)` — 63,293 of 63,293
  — across 13,743 distinct games. `lines` is unique on `gameId` — 15,384 of 15,384 — and holds
  its per-book offers in a nested `lines` list. The join is one-to-many by construction, so step
  6's uniqueness check runs at each side's **own** grain, never at a shared one.
- **coach.** REST `coaches` is unique on `(firstName, lastName, season)` — 1,935 of 1,936 — so it
  is coach-**season** grain, not coach grain, and carries `hireDate` plus a nested `seasons`
  list. Folding it into `dim_coach` would collapse ~4.8 rows per coach. It therefore pairs with
  `gql_coach_season` at season grain, while `gql_coach` alone forms the dimension.
  The one non-unique row is **Blake Anderson, 2021: two byte-identical rows** (same `hireDate`,
  same `_source_file`), so it deduplicates with `DISTINCT` and needs no quarantine. Verified, not
  assumed — a non-identical pair would have gone to `core.value_conflicts` instead.
  **`teamId` stays in the coach-season key** regardless: `coach_seasons` contains a genuine
  coach-season with two distinct `team_id`s, and `(coachId, season)` alone would silently collapse
  a real mid-season team change — the same class of error `CONTEXT.md` forbids for head coaches.

### Lines correspondence

Uniqueness at each side's own grain proves nothing about correspondence, so the merge is defined
concretely. The REST explode already exists: `stg.lines__lines`, produced by
`explode_stg_lists()`, holds 38,689 rows unique on `(gameId, lines_provider)` with
`lines_spread`, `lines_overUnder`, `lines_provider` and friends flattened out. So:

- REST offers come from `lines__lines`, not from the nested `lines` column on `lines`.
- `gql_game_lines` carries `linesProviderId` (an id); `lines__lines` carries `lines_provider`
  (a name). They join through the provider dimension — `gql_lines_provider` / the existing
  `core.dim_lines_provider`. If a provider name fails to resolve to an id, that offer is
  unmatched and reported, never dropped.
- Shared key is `(gameId, provider_key, period)`. REST offers carry no period and are treated as
  full-game; `gql_game_lines` supplies 1H/1Q rows that REST has no counterpart for, which is
  expected and is not an error.
- Unmatched offers on either side land in `core.fact_game_line` with a `_provenance` value naming
  the single source, and are counted in the step 6 report.

## What may be dropped (reconciles step 8 with D1)

D1 locked "`stg` sources stay" for **paired sources being conformed into `core`**. It did not
license dropping a table merely because a `core` table now covers it. Precisely:

- **Never dropped:** either side of a pair conformed into `core`. `core` is derived; `stg`
  remains the per-source shred it was built from.
- **Eligible:** a pair side that the containment gate proves is a strict subset — in both columns
  *and* rows.
- **Eligible:** the 12 named dead payload columns below.
- **Scraper removal** follows a table drop, never precedes it.

## Containment gate (formal)

A side is superseded only when **all four** hold. Column subsetting alone is insufficient: a
table can hold a strict column subset and still carry entity rows its partner lacks.

- **Column coverage** — every populated column it holds has a counterpart on the other side.
  Names compared case-insensitively with underscores stripped (`season_type` matches
  `seasonType`). A column with zero non-NULL values is excluded from both sides — this is why
  `gql_recruit` is superseded despite two exclusive columns: both are 100% NULL.
- **Row coverage** — every row it holds is present on the other side at equal or greater
  multiplicity, verified by `EXCEPT ALL` over the normalized shared columns. A distinct-key
  anti-join is insufficient: it passes when both sides share a key set but one holds duplicate
  records the other lacks. Measured on the concrete case — `draft_positions EXCEPT ALL
  gql_draft_position` returns **0** rows and the reverse returns 2, so REST is a strict multiset
  subset and droppable; had it returned any row, it would not be.
- **Value agreement** — for shared keys, per-column values agree, or a per-column authority is
  declared. Declaring authority never discards the loser: the disagreeing value is written to
  `core.value_conflicts` with the key, both values, both source tables, and the authority reason.
  A silently overwritten value is indistinguishable from a bug six months later.
- **Freshness** — the measurement post-dates the last load of both tables. A stale measurement is
  refused rather than used.

Tolerance is zero. There is no partial-supersession verdict; anything else is `MERGE`.

## Result-informed columns: physical separation, not tagging

Of the ten GraphQL-only columns on `gql_game`, six are post-kickoff. The repo forbids
result-informed data entering pre-game features.

**Tagging them in `core` would enforce nothing.** `result_lookahead` is a `FeatureDef` group in
the feature registry (`cfb_system_maker/features.py:15`), applied per registered feature — see
`pregame_win_prob`, already registered there as contaminated. It is not warehouse-column
metadata, and a tag on a `core.fact_game` column would be inert against an ad-hoc
`SELECT * FROM core.fact_game`.

So the separation is physical:

| Column | Destination |
|---|---|
| `homeStartElo`, `awayStartElo` | `core.fact_game` — pre-game |
| `homeConferenceId`, `awayConferenceId` | `core.fact_game` — pre-game |
| `homeEndElo`, `awayEndElo` | `core.fact_game_postgame` |
| `homePostgameWinProb`, `awayPostgameWinProb` | `core.fact_game_postgame` |
| `excitement` | `core.fact_game_postgame` |
| `status` | `core.fact_game_postgame` |

`core.fact_game_postgame` keys on `gameId`. "Never joined by feature-building code" is a claim,
so it ships with two gates rather than a promise:

1. **Static** — a test scans the feature-building modules for any reference to
   `fact_game_postgame` or the six column names, allowing registered `result_lookahead` features
   by exception.
2. **Mutation** — perturb only the `_postgame` values, rebuild the feature frame, and require
   byte-identical pregame output. The static scan alone cannot catch a helper or view that
   derives a renamed pregame column from postgame data; the mutation test catches it by
   construction, because leakage of any shape changes the output.

A feature that genuinely needs one of these columns must be registered in the `result_lookahead`
group the way `pregame_win_prob` is. A column whose timing is unclear goes to `_postgame`.

## The 12 dead payload columns

Post-rename names. Dropped only after confirming no view, `core` build, or test references them:

```
stg.plays.defenseTimeouts
stg.plays.offenseTimeouts
stg.plays.wallclock
stg.gql_game_weather.windGust
stg.gql_poll_type.abbreviation
stg.gql_recruit.overallRank
stg.gql_recruit.positionRank
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
  recoverable. Rejected: merging inside `stg` (adds a third table per concept and worsens the
  ambiguity) and dropping sources (provenance unrecoverable without a full re-scrape). ADR 0001.
- **D2 — `fact_game` gains columns, not rows.** `gql_game` spans 1869–2026 (112,672 rows);
  `games` spans 1992–2026 (54,264). Modern seasons match exactly (2024 3801/3801, 2025 3831/3831,
  2026 3676/3676), so the surplus is entirely pre-1992 history. `fact_game` keeps its 54,264-row
  REST spine; pre-1992 goes to `core.fact_game_historical`. Agreement test 1 survives unchanged
  and deep history cannot silently enter model training. ADR 0001.
- **D3 — Coach conforms on `coachId`, collisions quarantined.** `gql_coach` is a clean dimension:
  1,842 rows / 1,840 distinct names, with exactly 2 real collisions (Paul Davis, Jeff Horton — 2
  distinct `coachId`s each). `coaches` is not a dimension: 1,936 rows / 405 distinct names. REST
  rows resolve to a `coachId` by name; the 2 ambiguous names go to `core.coach_name_conflicts`.
  Rejected: a plain name join, which blends two distinct coaches and violates `CONTEXT.md`'s
  "Head coaches … not file-order last-write-wins".
  **Refined after D3 was locked, by measurement:** `coaches` is unique on
  `(firstName, lastName, season)` — 1,935 of 1,936 — so it is coach-*season* grain and cannot
  feed a coach dimension without collapsing ~4.8 rows per coach. D3's ruling stands unchanged
  (`coachId` is identity, the 2 collisions are quarantined); what changed is its target.
  `gql_coach` alone builds `core.dim_coach`; `coaches` joins `gql_coach_season` and
  `coach_seasons` at `core.fact_coach_season`.
- **`gql_recruiting_team` is not mergeable — settled by evidence.** 3,901 of its
  `recruitingTeamId`s are absent from `core.dim_team` (701 rows); the "id" is a row surrogate,
  not a team id, and REST carries only a team name. No bridge exists. Deferred.
- **GraphQL is not a superset.** 10 of 13 pairs carry populated exclusive columns both ways; for
  3 pairs REST is the superset (`coach_seasons` has 61 columns `gql_coach_season` lacks;
  `gql_recruit`'s 2 exclusive columns are 100% NULL). The scraper-drop condition failed and is
  not acted on except where measurement supports it.
- **Sequencing: repair before drop.** Fixing `gql_coach_season`'s relation keys changes whether
  it is droppable. Drops are gated on a re-measurement taken after the repair, computed at run
  time rather than read from this document.
- **Ordering vs the naming plan.** The naming plan runs first; its rename blast radius is 15
  lines today and grows once `core` build code references these tables.

## Toolchain

Skill inventory matched `deprecation-and-migration` (step 8's drops and scraper removal) and
`code-review-and-quality`. Neither loads automatically. Both benches share `~/.agents/skills` via
symlink, so availability is symmetric. No generator or MCP capability is required. Codex-side
skill loading under headless `codex exec` is unverified and nothing here depends on it.

## Assumptions

Verified against the live warehouse, 2026-09-01 (measured under pre-rename names):

1. GraphQL is not a superset of REST — bidirectional column diff with fill rates.
2. `coachSeason` (12,564 rows) has no coach or team column; `teamTalent` (2,413) has no team.
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
11. `result_lookahead` is a feature-registry group, not warehouse metadata — `features.py:15`,
    and `pregame_win_prob` is already registered in it.
12. `draftPosition` (31) and `draft_positions` (29) have identical `name` sets in both
    directions; the delta is duplicate rows, not coverage.

Assumed, gated by step 1:

13. The GraphQL `Coach` type exposes a selectable `id`, and `currentTeams` is reachable as
    `team { teamId }` from `coachSeason` and `teamTalent` — source
    `docs/graphql-schema-draft.md:108,119`, a draft doc, not live introspection.

Assumed, measured by step 3:

14. `coachSeason`/`teamTalent` pulls are currently short due to non-total sort. The mechanism is
    confirmed (Hasura offset pagination without a stable `order_by` skips or duplicates rows) but
    the shortfall on this data is not.

## Risks / open questions

- Widening `fact_game` touches an agreement-gated table. Test 1 asserts row-count coverage and
  should be unaffected by a column-only change, but tests 2–7 must be re-run and any failure
  treated as a design problem, not a test to update.
- GraphQL applies present-day classification retroactively (79,787 rows labelled `fbs` vs REST's
  26,827). `core.fact_game_historical` is not classification-accurate for its own era.
- The 2 coach name conflicts need one manual resolution pass; the plan quarantines rather than
  resolves them.
- **Single-writer assumption, stated not engineered.** This runs against a local DuckDB file on
  one workstation; DuckDB enforces single-writer access. The plan therefore does not add lock
  management, versioned build tables, or atomic swap. If this warehouse ever gains concurrent
  writers or a second operator, every destructive step needs revisiting first.

## Out of scope

- Table renaming to `gql_<snake_case>` — the sibling naming plan owns it and runs first.
- Column casing (984 camelCase columns) — deferred.
- `gql_recruiting_team` / `recruiting_teams` merge — no join key exists.
- Rebuilding `core` beyond `fact_game`'s added columns, `fact_game_postgame`,
  `fact_game_historical`, `dim_coach`, and `coach_name_conflicts`.
