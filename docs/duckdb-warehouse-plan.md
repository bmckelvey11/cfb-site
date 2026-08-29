# CFB DuckDB warehouse plan

This folds a downloaded generic warehouse design (`college-football-duckdb-plan.md`,
saved locally, not part of this repo) into what this repo's data actually looks like
today. The source plan is solid Kimball-style practice — raw/stg/core/mart layering,
`dim_`/`fact_`/`bridge_` naming, atomic full-refresh rebuilds — but it was written with
no visibility into this project's real consumers, real table inventory, or the
correctness problems already found in the existing loader (an unreproducible artifact,
a postseason-filename parsing bug). This doc is the corrected, scoped-down version:
what to keep, what to cut, what the plan didn't know to ask about, and a phase order
grounded in what's actually built.

**Reviews folded in (2026-08-28):** DBA send-back (grain + entity-map + dual-SoT tests),
database-designer pass (CTAS vs keys, denorm labels, indexes), and schema-designer
pass (column contract). Earlier draft grains `game-book-timestamp` and
`team-season_type-week` are **struck** — see `## Corrected grains` and
`## Revised phase plan`.

**Physical DDL (sibling, not this file):** [`docs/duckdb-core-ddl.md`](duckdb-core-ddl.md)
holds Phase 1 `CREATE TABLE` / CHECKs / indexes and the locked defaults below. Keep
this plan for why / when / grain; put column changes in the DDL doc.

**Prerequisite, not part of this plan:** [`docs/duckdb-rebuild-spec.md`](duckdb-rebuild-spec.md)
specs a clean rebuild of the existing `raw`/`stg` loader and flags a bug (`_post_wk`
files silently losing their `season`) that must be fixed before anything below is built
on top of `raw`/`stg` — a `core` fact built on a season-less postseason row inherits the
same hole. Design `core` against the **post-rebuild** catalog (`raw.*` REST +
`graphql.*` GQL schemas), not the current unreproducible mix where GraphQL names sit in
`raw`.

## Verdict, up front

The schema shape (`raw → stg → core → mart → app`) and naming convention are worth
keeping. The scope is not: the downloaded plan designs for a general-purpose college
football analytics platform (players, recruiting, draft, coaching staff, plays, drives)
when this repo has three narrower, already-defined consumers, none of which touch that
depth today. Coach/athlete/play-by-play work is now named near-term intent (see
Phase 3+ below) — that moves up *when* that layer gets built, not the verdict:
it still waits behind Phase 0/1, because every one of its use cases sits on top of a
trustworthy `raw`/`stg` and a conformed `core` that don't exist yet.

**Do not write Phase 1 `core` SQL until** the entity map (`## Raw → core entity map`),
corrected grains, and agreement-test sketch below are treated as gates — not optional
polish.

## What the plan didn't have visibility into

**Three real consumers exist today, not a hypothetical web app:**

| Consumer | What it needs |
|---|---|
| `cfb_system_maker` (Bet Labs parity backtester) | Game-level spread/total records + registry features — `GameRecord`, `games.csv`, `features.json` |
| `cfb_totals_model` (totals-line CLV model) | The same games/lines data, read from the shared warehouse (`CFB_DATA_ROOT`) |
| `over_zero` (Arscott floor-bias research) | Games/lines plus its own 1H-line and ActionNetwork snapshots not shared with the other two |

(All three live in this repo as of 2026-08-28 — `consolidation.md` Phase 1 is merged;
its Phase 2 shared-data-root move is in progress.) None of the three model athletes,
coaches, recruiting, or plays today. The plan's `dim_athlete`, `dim_coach`,
`bridge_coach_team_staff_history`, `bridge_recruit_school_history`,
`fact_draft_pick`, drive/play facts, and roster-snapshot facts therefore have no
consumers yet — though coach/athlete/play-by-play now has named near-term intent
(Phase 3+). Building them is not wrong, it's just not Phase 1 — see `## Cut or
deferred` below.

**97 raw tables already exist, and they're messier than the plan assumes.** The plan's
staging list has ~30 source-shaped tables, one per entity. The live database has 97
`raw` tables because CFBD is scraped through both REST and GraphQL, and the two APIs
name the same entity differently. `explode_payloads` (the existing `stg` builder) does
**not** conform these into one table — it mirrors `raw` 1:1, one `stg` table per `raw`
table, colliding only on an exact name match (the `calendar`/`calendar_gql` case
`duckdb-rebuild-spec.md` already documents). Confirmed duplicate/near-duplicate
families sitting in `raw` right now:

| Entity | REST-shaped table(s) | GraphQL-shaped table(s) | Notes |
|---|---|---|---|
| Team | `teams`, `fbs_teams` | `currentTeams`, `historicalTeam` | `fbs_teams` = FBS filter, not a second entity. `historicalTeam` is **SCD history** (different key), not a twin of `currentTeams` — do not "pick a winner" between them. |
| Coach | `coaches` | `coach`, `coachSeason` | Deferred (Phase 3+) |
| Game | `games` | `game` | Same numeric `id` space (verified). REST winner for columns. |
| **Lines** | `lines` (nested `lines[]`) | `gameLines` (flat) | **Was missing from the first draft.** Same data after unnest. Phase 1b. |
| Game/team stats | `game_team_stats` | `gameTeam` | Deferred |
| Player game stats | `game_player_stats` | `gamePlayerStat` | Deferred |
| Draft picks | `draft_picks` | `draftPicks` | Deferred |
| Draft position | `draft_positions` | `draftPosition` | Deferred |
| Draft team | `draft_teams` | `draftTeam` | Deferred |
| Recruit | `recruits` | `recruit` | Deferred |
| Recruiting team | `recruiting_teams` | `recruitingTeam` | Deferred |
| Predicted points | `predicted_points` | `predictedPoints` | Deferred |
| Conference | `conferences` | `conference` | `conference_sp` is an **SP+ rating fact**, not this dim — do not fold it in. |
| Venue | `venues` | *(none)* | REST-only. Not a collision family. |
| Calendar | `calendar` | `calendar` → `stg.calendar_gql` on collision | Week spine: `(season, week, season_type)`. |

The plan's `stg.team`, `stg.game`, `stg.coach`, etc. assume this dedup already
happened. It hasn't — there is no code anywhere in this repo that picks a winner
between, say, `raw.games` and `raw.game`, or merges them. That reconciliation is real,
new work, and it's the actual hard part of building `core` — harder than the plan's
"flatten JSON into staging tables" framing suggests.

**A prior entity map already exists — cite it, don't restart from a blank table.**
[`docs/graphql-schema-draft.md`](graphql-schema-draft.md) already declares REST
canonical for shape, documents REST↔GQL coverage, and sets `game_lines` PK to
`(game_id, lines_provider_id)`. [`SCHEMA_AUDIT.md`](../SCHEMA_AUDIT.md) verified
`game_id` / `team_id` join spaces against real 2023 data. Phase 1's map amends those
docs for DuckDB `raw`/`graphql` schema names; it does not invent a third parallel map.
Replacing the schema-draft line PK with "game-book-timestamp" was a **regression** —
reverted below.

**A `core`-grain fact already exists, in Python, not SQL.** `GameRecord`
(`cfb_system_maker/models.py`) is one row per game with home/away already joined into
columns — closer to a collapsed game fact than a separate `fact_game` /
`fact_game_team` pair for *betting columns*. `features.json` (built by
`enrich.py`/`running_stats.py`) is the `mart.model_game_team_features` the downloaded
plan describes, already built, already serving the web UI and both other consumers.
Building `core.fact_game` and mart features in SQL is not additive — it's a second
representation of data that already has one, in Python, that three consumers already
depend on. That's a real migration decision (rewrite `normalize.py`/`enrich.py` to
read from DuckDB instead of JSON, per the "Option 2" already raised and deferred in
`docs/duckdb-rebuild-spec.md`'s companion conversation), not a free addition. Don't
build the SQL version silently alongside the Python one without deciding which is
truth.

**`md:cfb` (MotherDuck) already exists and mirrors the local file** — confirmed live,
196 tables, same `raw`/`stg`/`meta` layout. `consolidation.md` documents this as "a
MotherDuck mirror (same pattern as Greenview), not a local folder," for cross-machine
sharing. No code pushes to it; it's a manual `duckdb` CLI session against the rebuilt
file. Treat local rebuild vs `md:cfb` as a **fork until a promote runbook exists**
(see `## MotherDuck promote`). The plan's `app` schema, if built, needs that promote
story — not an assumed live mirror.

## Adopted from the plan, as-is

- Schema names and grain: `raw`, `stg`, `core`, `mart` — matches the existing
  `raw`/`stg` split already implemented, `core`/`mart` net-new.
- Naming convention: `dim_<entity>`, `fact_<grain>`, `bridge_<relationship>`, no
  `cfb_`/`cfbd_` prefix (the database is already all-college-football; a prefix on
  every table is one team down the wrong ladder rung — the database name already
  supplies that context). Kimball **singular** table names stay (`dim_team`, not
  `dim_teams`) — ignore pluralize-nits from generic schema linters.
- Raw payload preservation + typed staging before conformed modeling — this repo's
  `raw`/`stg` split already does exactly this.
- Full refresh, file-atomic — matches the existing loader's `.building` → `replace()`
  rebuild, not incremental upsert, and **not** expand-contract / zero-downtime OLTP
  migration. MotherDuck promote is a catalog copy after local rebuild, not a rolling
  schema change.
- Grain-first fact/bridge design discipline — good practice; keep the habit even where
  the entity list below is trimmed. Corrected grains are in `## Corrected grains`.

### Physical design amendment (CTAS alone is not enough)

`CREATE OR REPLACE TABLE AS SELECT` builds an unkeyed heap in DuckDB. Grain discipline
requires keys after the replace:

1. CTAS (or `CREATE TABLE` + `INSERT`) into the rebuild temp file / schema.
2. `ALTER TABLE … ADD PRIMARY KEY (…)` (and `UNIQUE` where needed) on every `core`
   table.
3. `FOREIGN KEY` declarations are documentation-plus-insert-check in DuckDB — not
   warehouse integrity. **Agreement tests** (below) are the real gate against
   `games.csv` / `features.json`.

Do not claim modeled `core` while tables remain heaps. Column-level contract:
[`duckdb-core-ddl.md`](duckdb-core-ddl.md).

## Recommended build order (2026-08-28)

Do **not** grow this plan with more column prose. Next work, in order:

1. **Phase 0** — done (`_post_wk` + `season_type` on `raw`; clean rebuild).
2. **DDL contract** — [`duckdb-core-ddl.md`](duckdb-core-ddl.md) (already stubbed; edit
   there if columns change).
3. **1-map one-pager** — amend `graphql-schema-draft.md` / entity map for DuckDB
   `raw`/`graphql` schema names (REST winners only; do not rewrite the whole draft).
4. **Phase 1a** — load `dim_week` + `fact_game` (+ Type-1 dims as needed) → agreement
   tests 1–3, 7 green on `has_line` rows vs `games.csv`.
5. **Phase 1b** — unnest lines → `fact_game_line` → test 4.
6. **Phase 1c** — `fact_game_team` → tests 5–6.
7. MotherDuck promote runbook only when something will read `md:cfb` in production.

Skip 1b/1c until 1a matches. Skip `app.*`, coach/athlete dims, and any week-level
team mart until those gates pass.

### Locked punch-list forks

| # | Decision | Locked choice |
|---|---|---|
| 1 | `fact_game` population | All REST games + `has_line` / `completed`. `upcoming` separate. |
| 2 | `fact_game_line` grain | `(game_id, provider_key)`; open/close columns; AN history later. |
| 4 | Close-book rule | Clone `_select_line` / `_select_total` (split-book totals OK). |
| 4b | Selected providers on fact | **Two** keys: `selected_spread_provider_key`, `selected_total_provider_key`. |
| 8 | Game source | REST winner. |
| 10 | `dim_week` FK | Soft spine only — week attrs degenerate on fact; **no hard FK** to `dim_week`. |
| 11 | Keys | Natural CFBD ids; DuckDB FKs soft. |
| 17 | `fact_team_week` | Cut; use `fact_game_team`. |
| 18 | CTAS | Then `ALTER` PKs (or create-constrained + insert). |
| 19–20 | Degenerate book + home spread | As in DDL doc. |
| — | `provider_key` | Canonical **lowercase**. |
| — | Line numeric type | `DOUBLE`. |

Still open (after 1a green): Type-2 affiliations, name-alias `ref`, MotherDuck promote
owner, orphan `venue_orientation*`, FK policy for null GQL relations.

## Cut or deferred, and why

| Plan item | Status | Reason |
|---|---|---|
| `ref`, `model`, `qa`, `scratch` schemas | Cut for now (with caveat) | Empty schemas are hypotheses. **Caveat on `ref`:** cutting it does *not* mean "CFBD names are consistent." `docs/data-coverage.md` already documents 246 feature drifts from upstream team/conference **renames**. `GameRecord` / `enrich` join on school **name**. Warehouse natural keys are CFBD **ids**; names are Type-1 attributes that move. Keep `ref` out of the catalog until a concrete alias table is needed, but **do not write "names are stable" as an assumption.** `model` waits for a SQL-queryable trained artifact. `qa` stays in pytest (`test_duckdb_load.py` for loader; `test_core_agreement.py` for dual SoT — new). `scratch` = ad hoc CLI. |
| `dim_athlete`, `dim_coach`, `bridge_athlete_team_history`, `bridge_coach_team_staff_history`, `bridge_recruit_school_history`, `bridge_game_athlete_availability`, `fact_draft_pick`, `fact_recruit`, `fact_coach_season` | Deferred, with named intent | No current consumer — but coach/athlete work is near-term intent (Phase 3+). Still behind Phase 0/1 and REST/GQL dedup. |
| `fact_drive`, `fact_play`, `bridge_play_athlete_participation`, `fact_roster_snapshot`, `fact_transfer_portal_entry` | Deferred (plan's own Phase 3), with named intent | Largest volume in `raw`; nothing consumes it yet. |
| `fact_team_week` | **Cut from Phase 1** | Wrong grain for this repo — see `## Corrected grains`. Week rollup is a later mart only after bye / multi-game / postseason rules are written. |
| `app` schema and app-facing views | Deferred | Flask today reads `games.csv`/`features.json`. First concrete driver: coach/athlete site pages (Phase 3+). Hosted path sketched as Flask + `md:cfb`. |

## Corrected grains

| Table | Struck (generic / first draft) | Actual source grain | **Recommended grain** |
|---|---|---|---|
| `fact_game` | 1 row / game (kept) | REST `games` / GQL `game` share `id`. `normalize` keeps only games with a usable line → `GameRecord` is a **subset**. | **`game_id`**. Include `season_type`. Population: all REST games + `has_line` / `completed` (`upcoming` separate). Selected books are **degenerate** — clone `_select_line` / `_select_total`; store **two** provider keys when totals can split. Home-relative spread. See [`duckdb-core-ddl.md`](duckdb-core-ddl.md). |
| `fact_game_line` | ~~game-book-timestamp~~ | CFBD `GameLine` has **no timestamp**. Open/close are columns on the same provider row. REST nests `lines[]` (stays a `LIST` after `explode_payloads`). GQL `gameLines` is already flat. Schema draft PK was already `(game_id, lines_provider_id)`. ActionNetwork history is a **different** tape — out of Phase 1 / separate fact later. | **`(game_id, provider_key)`**. Columns: `spread_close`, `spread_open`, `total_close`, `total_open`, moneylines, optional `formatted_spread`. Requires a dedicated **unnest** of REST `lines[]` — `explode_payloads` will not do this. Provider is a name key (`consensus`, `DraftKings`); do not invent a numeric `lines_provider_id` unless a dim needs it. |
| Entering-game stats | ~~`fact_team_week` (team–season_type–week)~~ | `running_stats.py` emits `dict[(game_id, team)]`, sorted by `startDate` then `game_id`, **inside `(team, season)`** — does not reset on `season_type`. Multi-game weeks, byes, postseason week-1 vs regular week-1, and D2/D3 playoff timing all break a week grain. | **`fact_game_team` at `(game_id, team_id)`** (or `(game_id, home_away)` unique). Measures: entering-game `games_played`, `win_pct`, `ats_*`, streaks — no lookahead. Bowls inherit regular-season history. Week-level mart only later. |
| `dim_team` | Type-1 with conference implied | REST one id space; GQL splits `currentTeams` vs `historicalTeam`. Conference at kickoff already lives on `GameRecord`. | Type-1 on REST `teams.id` + `is_fbs` from `fbs_teams`. **Do not** put current conference on the dim as truth for history. As-of conference on the **fact** (`home_conference_id` / `away_conference_id`). Type-2 affiliation = `conference_affiliations` (bridge) — later. `historicalTeam` stays a source until career facts exist. |
| `dim_week` | *(missing from first draft)* | `calendar`: `(season, week, seasonType, …)` | **`(season, week, season_type)`** spine for filters. Week attrs also **degenerate on `fact_game`**; no hard FK to `dim_week` (calendar gaps must not block load). Phase 0 must land `season_type` on `raw`. |
| `dim_venue` | Listed as collision family | REST `venues` only; GQL has no venues | Optional in early Phase 1. No merge. FK from `games.venueId`. |
| `dim_conference` | Mixed with `conference_sp` | REST `conferences` vs GQL `conference` | REST winner; keep `classification`. Exclude `conference_sp`. |

## Raw → core entity map

**Gate:** this map (or an amended `graphql-schema-draft.md` section) must exist before
any `core` SQL. REST is canonical for shape (already decided). Winner-per-entity for
Phase 1 facts — do not silent-union REST and GQL.

| Entity | REST | GQL | Merge / key |
|---|---|---|---|
| Game | `raw.games` | `graphql.game` | Same numeric `id`. REST wins columns (`completed`, `highlights`, Elo names). Assert id sets; outer-join extras (coverage differs: REST-only / GQL-only rows exist). |
| Line | `raw.lines` → unnest `lines[]` | `graphql.gameLines` | Same after unnest. REST has `formatted_spread`. Open must be book-matched to close (`enrich._build_line_move_index`). |
| Team | `raw.teams` (season-stacked), `raw.fbs_teams` | `graphql.currentTeams`, `graphql.historicalTeam` | `dim_team` ← REST latest `teams` by `id`; `is_fbs` flag. Do not union current + historical into one dim. GQL FKs split across two dims — career facts later. Natural key: CFBD `team_id`. Join `GameRecord` via name→id crosswalk (`dim_team.school`); names move. |
| Conference | `raw.conferences` | `graphql.conference` | REST winner. `conference_sp` = fact, not dim. Real Type-2: `conference_affiliations` (`startYear`/`endYear`) — not Phase 1 unless building the bridge. |
| Venue | `raw.venues` | none | No merge. Defer if `fact_game` stays thin. |
| Calendar / week | `raw.calendar` | `graphql.calendar` | Conformed `dim_week`. Needed after `_post_wk` lands. |
| Provider | nested in lines | nested / flat in `gameLines` | `dim_lines_provider (provider_key)` — name PK, ~15 books. |

**Join landmines (already in-repo):** GraphQL dumps are scalars-only — relation FKs
(`pollRank.team`, etc.) may be null on disk. Athlete ids: REST string vs GQL int. REST
stat tables are often **name-keyed** only; GQL is id-keyed — crosswalk via `dim_team`.
`upcoming.csv` is a **third** stream, not `games.csv`.

## Dual SoT and agreement tests

**Decided (2026-08-28): run alongside, not replace.** `games.csv` / `features.json`
stay SoT for all three consumers. SQL `core` is for MotherDuck / ad hoc analysis and
**must fail CI on mismatch** — not "revisit if they drift."

New file: `tests/test_core_agreement.py` (do not overload `test_duckdb_load.py`).

Minimum suite:

1. **Coverage:** `COUNT(*)` `fact_game` where `has_line` = `COUNT(*)` `games.csv`. Symmetric
   set-diff on `game_id`. Upcoming not in this set unless explicitly included.
2. **Identity columns:** `season`, `week`, `season_type`, home/away names (or resolved
   ids), points, `provider`, `spread`, `total` — exact match to `GameRecord`.
3. **Provider clone:** multi-book fixtures — SQL close equals `_select_line` /
   `_select_total` (including split-book totals).
4. **Line-move:** for each `game_id` in the enrich line-move index, `fact_game_line` for
   `GameRecord.provider` matches `spread_open` / `total_open` / moves; nulls match
   (fail-closed, no zero default).
5. **Entering-game (when `fact_game_team` exists):** running stats per `(game_id, team)`
   match `running_stats`; first game of season → `games_played = 0`, rates `NULL`.
6. **Lookahead tripwire:** adding bowls must not change regular-season
   `games_played` (same assertion already proven in data-coverage work).
7. **Postseason week:** counts for `week = 1 AND season_type = 'postseason'` match CSV;
   a bare `WHERE week = 1` without `season_type` is a failed test.
8. **Rebuild identity:** `meta.load_report` + `meta.warehouse_version` (registry hash /
   git sha / generated_at); no leftover `*_post_wk*` table names after Phase 0.

## Indexes (after PKs exist)

Hot paths: backtest slate `(season, season_type, week)` + `has_line`; team filters on
`home_team_id` / `away_team_id`; agreement by `game_id`; book-matched line by
`(game_id, provider_key)`; entering-game by `game_id` / `team_id`; name→id on
`dim_team.school`.

**Keep:** secondary indexes on `fact_game(home_team_id)`, `fact_game(away_team_id)`,
one composite for the slate filter, `dim_team(school)` (not unique across history).

**Skip:** indexes that duplicate primary keys (`game_id`, `(game_id, provider_key)`).
Do not emit nineteen single-column indexes for one composite predicate.

## MotherDuck promote

Local rebuild is file-atomic. `md:cfb` is manual and has **no code path**. Until a
promote exists, local `core.*` and cloud `raw`/`stg` can diverge.

Runbook (write before Phase 2 Flask+MotherDuck):

1. Rebuild local → verify `meta` / agreement tests.
2. Attach `md:cfb` → replace named schemas (or whole DB) → verify table counts.
3. Record `meta.warehouse_version` on both sides.
4. Never use loader `--only` as "refresh one table" — it is a **destructive full-file
   replace**. Never assume `--explode-only` updates `meta.load_report`.

## Revised phase plan

**Phase 0 — done (2026-08-28).**
`_post_wk` parser + `season_type` column shipped in `duckdb_load.py`; clean rebuild at
`$CFB_DATA_ROOT/cfb.duckdb` (`raw` 77 / `graphql` 36 / `stg` 110). Verified: no
`*_post_wk*` table names; postseason `season` non-null on `raw.game_team_stats`. Caveats:
`stg.plays` and `stg.gamePlayerStat` OOM on explode (raw intact; not Phase 1 blockers);
rebuild skipped ActionNetwork (`--skip-actionnetwork`). See
`docs/duckdb-rebuild-spec.md`.

**Phase 1-map — entity winners + keys + SCD (document gate).**
Write/amend the raw → core entity map for `team`, `conference`, `venue`, `game`,
**`lines`**, and calendar/week. Cite `graphql-schema-draft.md` + `SCHEMA_AUDIT.md`.
No `core` SQL until this exists.

**Phase 1a — `dim_week` + `fact_game` (+ optional Type-1 dims).**
- `core.dim_week` — `(season, week, season_type)`.
- `core.fact_game` — grain `game_id`; `season_type`; `has_line` / `completed`; team ids
  (and as-of conference ids); optional degenerate selected book for CSV agreement.
- Optional: `dim_team` / `dim_conference` / `dim_venue` if FKs are wanted in the same
  slice; venue is not on the critical path.
- CTAS then `ALTER` PKs / needed uniques.
- Verify: agreement tests 1–3, 7.

**Phase 1b — unnest lines → `fact_game_line`.**
- Dedicated stg/core step to unnest REST `lines[]` (arrays stay LIST today).
- Grain `(game_id, provider_key)`; open/close columns; home-relative spread.
- Verify: agreement test 4.

**Phase 1c — `fact_game_team` (entering-game).**
- Grain `(game_id, team_id)`; match `running_stats.py`; no lookahead.
- Verify: agreement tests 5–6.
- **Defer** any week-level team mart.

**Decided (2026-08-28): run alongside, not replace.** SQL `core` is a second
representation for SQL-side querying (MotherDuck, ad hoc analysis), checked by
agreement tests against JSON SoT. Revisit migration only if dual maintenance becomes
real overhead — not decided preemptively here.

**Phase 2 — `mart` + `app`, once the hosted-web-app work actually starts.**
Direction is decided (hosted, Flask + MotherDuck `md:cfb`); timing is not. Build
`mart.model_game_team_features` (if not already covered by `fact_game_team` + feature
joins) and `app.*` serving views on top of Phase 1's `core`, once something is actually
reading from DuckDB in production instead of `games.csv`. Promote runbook required
first.

**Phase 3+ — not committed, but coaches/athletes/play-by-play flagged as near-term
intent (2026-08-28).** No build yet — still waiting on Phase 0/1 and a concrete use
case. When this starts, note one thing already true: coach-level work has a Python
precedent, not a SQL one — `coach_style.py`'s `coach_style_cluster` registry feature (a
generated k-means label from `raw.coach`/advanced stats,
`docs/coach-playstyle-analysis.md` is its validity study) already ships as a
`result_lookahead`-quarantined feature, not a `core.dim_coach`. Athlete- and play-level
work has no precedent either way.

**Named use cases (2026-08-28), not yet scoped into tasks:** backtest filters,
web-app content (coach/athlete/game pages), and modeling. That's not the single-fork
choice Phase 1 faced for games — it's three consumers with different shapes:

| Use case | Likely shape | Precedent |
|---|---|---|
| Backtest filters | Python registry feature (`enrich.py`, quarantined into `result_lookahead` if it's a career-level/post-hoc label) | `coach_style_cluster` |
| Web-app content | `core.dim_coach`/`dim_athlete` + `app.*` serving views | None yet — this is the first real driver for the `app` schema this doc deferred above |
| Modeling | Feature table joinable at scale — could be either, depends on the model | `v1_fit.json` (Python-only, today) |

Same open question as the games decision: do these get built once in SQL and read by
both the web app and the Python backtest/model code, or does each consumer keep its
own shape? Not deciding here — flagging that "web-app content" is the first concrete
reason the `app` schema (deferred above) might stop being hypothetical.

## Punch list

Locked items are in `## Recommended build order` and
[`duckdb-core-ddl.md`](duckdb-core-ddl.md). Remaining before / during Phase 1 SQL:

3. **Lines unnest:** new `stg`/core step (required); do not rely on `explode_payloads`.
5. **Team natural key:** CFBD `id`; name→id via `dim_team.school` index; alias map when
   renames break names (not UNIQUE on school).
6. **`dim_team` SCD:** Type-1 now (latest season collapse — see DDL doc); Type-2 via
   `conference_affiliations` / `historicalTeam` later.
7. **`fbs_teams`:** attribute (`is_fbs`), not a table.
9. **FK policy** when ids disagree or GraphQL relation is null — still open.
10. **`season_type` on raw:** Phase 0 filename/payload; degenerate on every game fact.
12. **Nullability:** spelled in DDL doc; revisit if load hits unexpected nulls.
13. **Agreement tests** as a CI gate (`test_core_agreement.py`).
14. **MotherDuck promote** steps + `meta.warehouse_version`; who may replace `md:cfb`.
15. **Name aliases / `ref`:** warehouse is id-keyed; add alias table only when needed.
16. **Orphan `stg.venue_orientation*`:** out of rebuild scope or register a source —
    rebuild will drop them.

---

A threat model was deliberately omitted from this doc: it is planning-only, no code or
schema changes ship from it, and it crosses no trust boundary.
